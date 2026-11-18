"""菜品图生成：MiniMax image-01（默认，有 MINIMAX_API_KEY 时）或阿里云百炼（DashScope）。

流程：agent 工具调用 → 写一行 pending → 后台线程请求生图服务 → 拿到图片字节存到本地
（两家返回的 URL 都只有 24 小时有效；MiniMax 直接要 base64，省一次下载）→ 更新为 ready / failed。
前端轮询 /api/images/<id>。两个客户端接口一致：generate(prompt) -> bytes，失败抛 ImageError(code)。
"""
import base64
import binascii
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from config import logger
from db import connect
from health import ValidationError

STYLE = ("美食摄影，真实质感，盛放在白色瓷盘中，木质餐桌，柔和自然窗光，浅景深，俯拍约 45 度，"
         "构图干净，色彩自然诱人，画面中不要出现任何文字、水印或人物")
# MiniMax image-01 实测对中文菜名理解不可靠（2026-11-18：「番茄炒蛋」中文描述两次都画成了番茄拌面，
# 英文描述一次就对），所以它用英文风格词；agent 也被要求用英文写画面描述
STYLE_EN = ("food photography, realistic texture, served on a white porcelain plate on a wooden table, soft natural "
            "window light, shallow depth of field, 45-degree overhead angle, clean composition, natural appetizing "
            "colors, no text, no watermark, no people")
MAX_BYTES = 12 * 1024 * 1024

# 百炼错误码 → 给用户看的说明（上游原始报错只进日志的 code，不进响应）
ERROR_TEXT = {
    "Arrearage": "图片服务所在的阿里云账户欠费，充值后即可恢复",
    "InvalidApiKey": "图片服务的密钥无效，请检查 DASHSCOPE_API_KEY",
    "DataInspectionFailed": "这段描述没有通过内容安全审核，换个说法试试",
    "Throttling": "图片服务有点忙，稍后再试",
    "limit_requests": "图片服务调用太频繁或额度受限，稍后再试",
    "InsufficientBalance": "图片服务账户余额不足，充值后即可恢复",
    "InvalidParameter": "图片服务参数有误，请检查生图模型配置",
}

# MiniMax base_resp.status_code → 统一的错误码（见 platform.minimax.cn 文生图接口文档）
MINIMAX_CODES = {1002: "Throttling", 1004: "InvalidApiKey", 2049: "InvalidApiKey", 1008: "InsufficientBalance",
                 1026: "DataInspectionFailed", 2013: "InvalidParameter"}


class ImageError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class DashScopeImageClient:
    def __init__(self, api_key: str, base_url: str, model: str, size: str, timeout: float = 120):
        self.api_key, self.model, self.size = api_key, model, size
        self.url = base_url.rstrip("/") + "/services/aigc/multimodal-generation/generation"
        self.http = httpx.Client(timeout=timeout)

    def generate(self, prompt: str) -> bytes:
        # 只用 qwen-image 与 z-image 都支持的参数：z-image 不支持 n（固定 1 张）
        body = {"model": self.model,
                "input": {"messages": [{"role": "user", "content": [{"text": prompt[:780]}]}]},
                "parameters": {"size": self.size, "prompt_extend": False}}
        try:
            res = self.http.post(self.url, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.TimeoutException:
            raise ImageError("Timeout") from None
        except httpx.HTTPError:
            raise ImageError("NetworkError") from None
        data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        if res.status_code != 200:
            raise ImageError(str(data.get("code") or data.get("error", {}).get("code") or f"HTTP{res.status_code}"))
        try:
            content = data["output"]["choices"][0]["message"]["content"]
            url = next(c["image"] for c in content if c.get("image"))
        except (KeyError, IndexError, StopIteration, TypeError):
            raise ImageError("BadResponse") from None
        img = self.http.get(url)
        if img.status_code != 200 or len(img.content) > MAX_BYTES:
            raise ImageError("DownloadFailed")
        return img.content


class MiniMaxImageClient:
    """MiniMax 文生图（image-01）。中国区默认 https://api.minimax.cn/v1，国际版换成 https://api.minimax.io/v1。"""
    style = STYLE_EN

    def __init__(self, api_key: str, base_url: str, model: str = "image-01", aspect_ratio: str = "1:1",
                 timeout: float = 120, http: httpx.Client | None = None):
        self.api_key, self.model, self.aspect_ratio = api_key, model, aspect_ratio
        self.url = base_url.rstrip("/") + "/image_generation"
        self.http = http or httpx.Client(timeout=timeout)

    def generate(self, prompt: str) -> bytes:
        body = {"model": self.model, "prompt": prompt[:1500], "aspect_ratio": self.aspect_ratio,
                "response_format": "base64", "n": 1, "prompt_optimizer": False}
        try:
            res = self.http.post(self.url, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.TimeoutException:
            raise ImageError("Timeout") from None
        except httpx.HTTPError:
            raise ImageError("NetworkError") from None
        try:
            data = res.json()
        except ValueError:
            raise ImageError(f"HTTP{res.status_code}") from None
        status = (data.get("base_resp") or {}).get("status_code")
        if res.status_code != 200 or status not in (0, None):
            raise ImageError(MINIMAX_CODES.get(status, f"MiniMax{status}" if status is not None else f"HTTP{res.status_code}"))
        images = (data.get("data") or {}).get("image_base64") or []
        if not images:
            # 成功返回但一张没有：被内容安全拦了（metadata.failed_count > 0）
            failed = int((data.get("metadata") or {}).get("failed_count") or 0)
            raise ImageError("DataInspectionFailed" if failed else "BadResponse")
        try:
            raw = base64.b64decode(images[0], validate=True)
        except (binascii.Error, ValueError):
            raise ImageError("BadResponse") from None
        if not raw or len(raw) > MAX_BYTES:
            raise ImageError("DownloadFailed")
        return raw


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class ImageService:
    def __init__(self, client, db_path: Path, image_dir: Path, daily_limit: int, run_async: bool = True):
        self.client, self.db_path, self.dir = client, db_path, image_dir
        self.daily_limit, self.run_async = daily_limit, run_async
        self.dir.mkdir(parents=True, exist_ok=True)

    def start(self, conn, user_id: int, title: str, description: str) -> dict:
        title = str(title or "").strip()[:30] or "菜品"
        description = str(description or "").strip()[:400]
        if not description:
            raise ValidationError("需要描述画面里的菜品")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used = conn.execute("SELECT COUNT(*) FROM images WHERE user_id=? AND substr(created_at,1,10)=? "
                            "AND status != 'failed'", (user_id, today)).fetchone()[0]
        if used >= self.daily_limit:
            raise ValidationError(f"今天的配图次数（{self.daily_limit} 张）用完了，明天再来")
        # 风格词跟着生图服务走：MiniMax 用英文，其余（百炼、测试替身）用中文
        style = getattr(self.client, "style", STYLE)
        body = description.rstrip("。.！!，, ")  # 描述自带句号时别拼出「..」
        prompt = f"{body}. {style}" if style is STYLE_EN else f"{body}。{style}"
        cur = conn.execute("INSERT INTO images (user_id, title, prompt, status) VALUES (?, ?, ?, 'pending')",
                           (user_id, title, prompt))
        conn.commit()
        image_id = cur.lastrowid
        if self.run_async:
            threading.Thread(target=self._run, args=(image_id, prompt), daemon=True, name=f"image-{image_id}").start()
        else:
            self._run(image_id, prompt)
        return {"id": image_id, "title": title, "status": "pending"}

    def _run(self, image_id: int, prompt: str) -> None:
        conn = connect(self.db_path)  # 后台线程用独立连接
        try:
            try:
                data = self.client.generate(prompt)
                ext = _sniff(data)
                if not ext:
                    raise ImageError("NotAnImage")
                name = f"{image_id}_{uuid.uuid4().hex[:12]}.{ext}"
                (self.dir / name).write_bytes(data)
                conn.execute("UPDATE images SET status='ready', file=? WHERE id=?", (name, image_id))
            except ImageError as exc:
                logger.warning("image %s failed: %s", image_id, exc.code)
                conn.execute("UPDATE images SET status='failed', error=? WHERE id=?", (exc.code, image_id))
            except Exception as exc:  # 意外错误同样落到 failed，避免卡片永远停在“生成中”
                logger.exception("image %s crashed", image_id)
                conn.execute("UPDATE images SET status='failed', error=? WHERE id=?", (type(exc).__name__, image_id))
            conn.commit()
        finally:
            conn.close()


def public_image(row) -> dict:
    code = row["error"]
    return {"id": row["id"], "title": row["title"], "status": row["status"],
            "error": (ERROR_TEXT.get(code, "图片生成失败了，稍后再试") if code else None)}
