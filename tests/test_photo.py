"""拍照识别食材（第 4 期）回归测试：图片校验、识别结果规整、只预览不入库、每日限额、上传大小只对这一个接口放宽。

用假视觉模型，不访问网络。运行：python -m unittest discover -s tests -v
"""
import base64
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

import photo  # noqa: E402
from health import ValidationError  # noqa: E402
from test_kitchen import TODAY, DbCase, JsonLLM  # noqa: E402
from test_server import make_settings  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 64


def data_url(raw: bytes, mime="image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


FRIDGE = {"items": [
    {"name": "鸡蛋", "quantity": 6, "unit": "个", "storage": "fridge", "sure": True},
    {"name": "番茄", "quantity": 2, "unit": "个", "sure": True},
    {"name": "番茄", "quantity": 1, "unit": "个", "sure": False},          # 重复一行：应合并成 3 个
    {"name": "可能是豆腐", "quantity": None, "unit": "", "sure": False},
    {"name": "饺子", "quantity": 1, "unit": "袋", "storage": "freezer"},  # 没给 sure：当确定
    {"name": "", "quantity": 1},                                          # 垃圾行：丢掉
    "不是对象",
], "note": "右下角有点暗"}


class DecodeTests(unittest.TestCase):
    def test_accepts_real_image_headers(self):
        for raw, mime in ((JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")):
            self.assertEqual(photo.decode_image(data_url(raw, mime)), (raw, mime))

    def test_trusts_file_header_not_declared_type(self):
        # 声明是 jpeg、实际是 png：按实际文件头转给模型
        self.assertEqual(photo.decode_image(data_url(PNG, "image/jpeg"))[1], "image/png")

    def test_rejects_bad_input(self):
        bad = [None, 123, "hello", "data:image/gif;base64,R0lGOD", "data:image/jpeg;base64,@@@",
               data_url(b"just some text, not an image"), data_url(b"")]
        for value in bad:
            with self.assertRaises(ValidationError, msg=str(value)[:40]):
                photo.decode_image(value)
        with self.assertRaisesRegex(ValidationError, "太大"):
            photo.decode_image(data_url(JPEG + b"\x00" * photo.MAX_BYTES))


class RecognizeTests(DbCase):
    def test_result_is_cleaned_merged_and_sorted(self):
        llm = JsonLLM(FRIDGE)
        result = photo.recognize(self.conn, llm, "vl", 1, data_url(JPEG), TODAY)
        by = {i["name"]: i for i in result["items"]}
        self.assertEqual(set(by), {"鸡蛋", "番茄", "可能是豆腐", "饺子"})
        self.assertEqual((by["番茄"]["quantity"], by["番茄"]["sure"]), (3, True))
        self.assertFalse(by["可能是豆腐"]["sure"])
        self.assertEqual(result["items"][-1]["name"], "可能是豆腐")              # 不确定的排最后
        self.assertEqual(by["饺子"]["storage"], "freezer")
        self.assertTrue(by["饺子"]["sure"])
        self.assertTrue(by["鸡蛋"]["expires_estimated"])
        self.assertEqual(result["note"], "右下角有点暗")
        # 图片以 data URL 发给视觉模型，模型名透传
        call = llm.calls[0]
        self.assertEqual(call["model"], "vl")
        part = call["messages"][1]["content"][0]
        self.assertEqual(part["type"], "image_url")
        self.assertTrue(part["image_url"]["url"].startswith("data:image/jpeg;base64,/9j/"))

    def test_preview_only_does_not_touch_pantry(self):
        photo.recognize(self.conn, JsonLLM(FRIDGE), "vl", 1, data_url(JPEG), TODAY)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM pantry_items").fetchone()[0], 0)

    def test_daily_limit_counts_failed_calls_too(self):
        with self.assertRaises(Exception):
            photo.recognize(self.conn, JsonLLM("不是 JSON"), "vl", 1, data_url(JPEG), TODAY, daily_limit=2)
        photo.recognize(self.conn, JsonLLM(FRIDGE), "vl", 1, data_url(JPEG), TODAY, daily_limit=2)
        with self.assertRaisesRegex(ValidationError, "今天已经拍照识别了 2 次"):
            photo.recognize(self.conn, JsonLLM(FRIDGE), "vl", 1, data_url(JPEG), TODAY, daily_limit=2)
        photo.recognize(self.conn, JsonLLM(FRIDGE), "vl", 2, data_url(JPEG), TODAY, daily_limit=2)  # 别人不受影响

    def test_bad_image_does_not_use_quota(self):
        with self.assertRaises(ValidationError):
            photo.recognize(self.conn, JsonLLM(FRIDGE), "vl", 1, data_url(b"nope"), TODAY, daily_limit=1)
        self.assertEqual(photo.used_today(self.conn, 1), 0)

    def test_not_configured(self):
        with self.assertRaisesRegex(ValidationError, "还没有配置识图服务"):
            photo.recognize(self.conn, None, None, 1, data_url(JPEG), TODAY)


class PhotoApiTests(unittest.TestCase):
    def make(self, vision):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        client = create_app(make_settings(self.tmp.name), vision_client=vision).test_client()
        client.post("/api/auth/register", json={"username": "snap", "password": "password-123"})
        return client

    def test_round_trip_and_size_limit_only_for_this_route(self):
        vision = JsonLLM(FRIDGE, FRIDGE)
        c = self.make(vision)
        self.assertTrue(c.get("/api/meta").get_json()["vision_enabled"])
        big = data_url(JPEG + b"\x00" * (1024 * 1024))           # 约 1.4MB 的 data URL：超过全局 256KB 上限
        r = c.post("/api/pantry/photo", json={"image": big})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()["items"]), 4)
        self.assertEqual(c.get("/api/pantry").get_json()["items"], [])            # 只预览
        # 其他接口的上限不变
        self.assertEqual(c.post("/api/pantry/parse", json={"text": "x" * 300 * 1024}).status_code, 413)

    def test_model_failure_is_502_with_friendly_message(self):
        c = self.make(JsonLLM("<<垃圾>>"))
        r = c.post("/api/pantry/photo", json={"image": data_url(JPEG)})
        self.assertEqual(r.status_code, 502)
        self.assertIn("再拍一张", r.get_json()["error"])

    def test_disabled_and_login(self):
        c = self.make(None)
        self.assertFalse(c.get("/api/meta").get_json()["vision_enabled"])
        self.assertEqual(c.post("/api/pantry/photo", json={"image": data_url(JPEG)}).status_code, 400)
        c.post("/api/auth/logout", json={})
        self.assertEqual(c.post("/api/pantry/photo", json={"image": data_url(JPEG)}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
