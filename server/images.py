"""菜品图生成：阿里云百炼（DashScope）multimodal-generation 同步接口。

流程：agent 工具调用 → 写一行 pending → 后台线程请求百炼 → 立即下载图片存到本地
（百炼返回的 URL 只有 24 小时有效）→ 更新为 ready / failed。前端轮询 /api/images/<id>。
"""
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
MAX_BYTES = 12 * 1024 * 1024

# 百炼错误码 → 给用户看的说明（上游原始报错只进日志的 code，不进响应）
ERROR_TEXT = {
    "Arrearage": "图片服务所在的阿里云账户欠费，充值后即可恢复",
    "InvalidApiKey": "图片服务的密钥无效，请检查 DASHSCOPE_API_KEY",
    "DataInspectionFailed": "这段描述没有通过内容安全审核，换个说法试试",
    "Throttling": "图片服务有点忙，稍后再试",
    "limit_requests": "图片服务调用太频繁或额度受限，稍后再试",
}


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
        prompt = f"{description}。{STYLE}"
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
