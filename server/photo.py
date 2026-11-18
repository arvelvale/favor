"""拍冰箱照片识别食材（第 4 期）。

原则：
- 照片只转给视觉模型识别，服务端不落盘、不入库，用完即丢
- 识别结果只是预览，前端让用户确认（不确定的默认不勾）后再走 POST /api/pantry 入库，避免识别错误污染库存
- 视觉模型走 DeepSeek OpenAI 兼容接口（默认 deepseek-flash，复用对话密钥），每人每天限额控制费用
"""
import base64
import binascii
import json
import re
from datetime import date, datetime

import health
import kitchen
from health import ValidationError

MAX_BYTES = 3 * 1024 * 1024
MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_ITEMS = 30

PHOTO_PROMPT = """识别照片里能看到的食材（冰箱里、购物袋里、桌上都行），只输出 JSON，不要解释。
格式：{"items": [{"name": "简短通用名，如 番茄、鸡蛋、五花肉", "quantity": 数字或 null, "unit": "单位，如 个、盒、根，没有就空字符串",
"storage": "fridge|freezer|pantry", "sure": true 或 false}], "note": "看不清或拍得不全时一句话说明，否则空字符串"}
规则：
1. 只列食材和饮料，忽略容器、电器、杂物；调料瓶能认出就写（如 酱油、番茄酱）。
2. 同一种合并成一行并估个数（3 个番茄 → quantity 3, unit 个）；数不清 quantity 为 null。
3. 只看到包装、认不出里面是什么的，不要写；能认出但不太确定的，sure 为 false。
4. 在冷冻室或明显是冻品的，storage 为 freezer；冰箱外常温放的为 pantry；其余为 fridge。
5. 最多 30 样。"""

_SIGNATURES = (("image/jpeg", lambda b: b[:3] == b"\xff\xd8\xff"),
               ("image/png", lambda b: b[:8] == b"\x89PNG\r\n\x1a\n"),
               ("image/webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"))


def decode_image(data_url) -> tuple[bytes, str]:
    """校验前端传来的 data URL：类型、大小、文件头都要对得上，返回 (原始字节, mime)。"""
    if not isinstance(data_url, str):
        raise ValidationError("请上传一张照片")
    m = re.match(r"^data:(image/[a-z]+);base64,(.+)$", data_url, re.S)
    if not m or m.group(1) not in MIMES:
        raise ValidationError("只支持 JPG、PNG、WebP 格式的照片")
    if len(m.group(2)) > MAX_BYTES * 4 // 3 + 4:
        raise ValidationError("照片太大了，请换一张或重新拍")
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise ValidationError("照片数据不完整，请重新选择") from None
    if not raw or len(raw) > MAX_BYTES:
        raise ValidationError("照片太大了，请换一张或重新拍")
    real = next((mime for mime, ok in _SIGNATURES if ok(raw)), None)
    if real is None:
        raise ValidationError("这不像是一张照片，请重新选择")
    return raw, real


def used_today(conn, user_id: int, kind: str = "photo") -> int:
    return conn.execute("SELECT COUNT(*) FROM usage_log WHERE user_id=? AND kind=? AND date(created_at)=?",
                        (user_id, kind, datetime.utcnow().date().isoformat())).fetchone()[0]


def recognize(conn, client, model: str | None, user_id: int, data_url, today: date, daily_limit: int = 20) -> dict:
    """识别一张照片，返回 {items: 预览列表, note}。不入库。调用方负责提交（限额计数要落库）。"""
    if client is None or not model:
        raise ValidationError("还没有配置识图服务，先用勾选或说一句话吧")
    raw, mime = decode_image(data_url)
    used = used_today(conn, user_id)
    if used >= daily_limit:
        raise ValidationError(f"今天已经拍照识别了 {used} 次，明天再来吧（每天最多 {daily_limit} 次）")
    # 先记一次再调用：模型失败也算一次，避免反复重试刷费用
    conn.execute("INSERT INTO usage_log (user_id, kind) VALUES (?, 'photo')", (user_id,))
    conn.commit()

    url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": PHOTO_PROMPT},
                  {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}},
                                               {"type": "text", "text": "这张照片里有哪些食材？"}]}],
        response_format={"type": "json_object"}, temperature=0.2, max_tokens=4000, stream=False)
    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("模型返回的不是 JSON 对象")

    merged: dict[str, dict] = {}
    for rawitem in (data.get("items") or [])[:MAX_ITEMS * 2]:
        if not isinstance(rawitem, dict):
            continue
        try:
            clean = kitchen._clean_item(rawitem, today)
        except ValidationError:
            continue
        sure = rawitem.get("sure") is not False  # 模型没给就当确定
        key = kitchen.normalize_name(clean["name"])
        if key in merged:  # 模型偶尔把同一种拆成两行：合并，数量单位一致时相加，有一行确定就算确定
            prev = merged[key]
            if prev["quantity"] is not None and clean["quantity"] is not None and prev["unit"] == clean["unit"]:
                prev["quantity"] += clean["quantity"]
            prev["sure"] = prev["sure"] or sure
            continue
        merged[key] = clean | {"sure": sure, "days_left": kitchen._days_left(clean["expires_on"], today),
                               "category_label": kitchen.CATEGORIES[clean["category"]],
                               "storage_label": kitchen.STORAGES[clean["storage"]]}
    items = list(merged.values())[:MAX_ITEMS]
    items.sort(key=lambda i: not i["sure"])  # 确定的排前面
    return {"items": items, "note": health._text(data.get("note"), 80)}
