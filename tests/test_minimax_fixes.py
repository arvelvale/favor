"""MiniMax 生图接入 + 真实模型实测（2026-11-18）暴露问题的回归测试。

- MiniMax 客户端：请求格式、base64 解码、错误码映射（用 httpx.MockTransport，不访问网络）
- 生图服务选择：自动 / 指定 / 都没配；识图默认走 DeepSeek（不受生图开关影响）
- 放冰箱工具如实区分「新放的」和「合并到已有的」（真实模型曾编出「之前那盒」「现在有 4 根」）
- 冰箱里没有的小料（小米辣、葱姜蒜、香菜）不挡「现在就能做」；豆瓣酱这类酱料仍算缺料
运行：python -m unittest discover -s tests -v
"""
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

import kitchen  # noqa: E402
from agent import tools  # noqa: E402
from images import ImageError, ImageService, MiniMaxImageClient  # noqa: E402
from test_kitchen import NOW, TODAY, DbCase, JsonLLM, recipe  # noqa: E402
from test_server import make_settings  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def mock_client(handler):
    return MiniMaxImageClient("mm-test-key", "https://api.minimax.cn/v1", http=httpx.Client(transport=httpx.MockTransport(handler)))


class MiniMaxClientTests(unittest.TestCase):
    def test_success_request_shape_and_decode(self):
        seen = {}

        def handler(request: httpx.Request):
            seen["url"] = str(request.url)
            seen["auth"] = request.headers["authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "t1", "data": {"image_base64": [base64.b64encode(PNG).decode()]},
                                             "metadata": {"success_count": 1, "failed_count": 0},
                                             "base_resp": {"status_code": 0, "status_msg": "success"}})

        self.assertEqual(mock_client(handler).generate("番茄炒蛋，" * 400), PNG)
        self.assertEqual(seen["url"], "https://api.minimax.cn/v1/image_generation")
        self.assertEqual(seen["auth"], "Bearer mm-test-key")
        body = seen["body"]
        self.assertEqual((body["model"], body["response_format"], body["n"], body["aspect_ratio"]),
                         ("image-01", "base64", 1, "1:1"))
        self.assertLessEqual(len(body["prompt"]), 1500)                       # 文档上限 1500 字

    def test_error_codes(self):
        cases = [(1008, "InsufficientBalance"), (1026, "DataInspectionFailed"), (1004, "InvalidApiKey"),
                 (2049, "InvalidApiKey"), (1002, "Throttling"), (2013, "InvalidParameter"), (9999, "MiniMax9999")]
        for status, code in cases:
            client = mock_client(lambda r, s=status: httpx.Response(200, json={"base_resp": {"status_code": s, "status_msg": "x"}}))
            with self.assertRaises(ImageError) as ctx:
                client.generate("x")
            self.assertEqual(ctx.exception.code, code, status)

    def test_blocked_empty_and_broken_responses(self):
        blocked = mock_client(lambda r: httpx.Response(200, json={"data": {"image_base64": []}, "metadata": {"failed_count": 1},
                                                                  "base_resp": {"status_code": 0}}))
        with self.assertRaises(ImageError) as ctx:
            blocked.generate("x")
        self.assertEqual(ctx.exception.code, "DataInspectionFailed")
        for handler, code in ((lambda r: httpx.Response(502, text="<html>bad gateway</html>"), "HTTP502"),
                              (lambda r: httpx.Response(200, json={"data": {"image_base64": ["@@@"]}, "base_resp": {"status_code": 0}}), "BadResponse")):
            with self.assertRaises(ImageError) as ctx:
                mock_client(handler).generate("x")
            self.assertEqual(ctx.exception.code, code)

        def timeout(request):
            raise httpx.ReadTimeout("slow", request=request)
        with self.assertRaises(ImageError) as ctx:
            mock_client(timeout).generate("x")
        self.assertEqual(ctx.exception.code, "Timeout")

    def test_image_service_saves_minimax_result(self):
        from db import connect, init_db
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "i.sqlite3"
            init_db(db)
            conn = connect(db)
            conn.execute("INSERT INTO users (username, password_hash) VALUES ('u', 'x')")
            conn.commit()
            client = mock_client(lambda r: httpx.Response(200, json={"data": {"image_base64": [base64.b64encode(PNG).decode()]},
                                                                     "base_resp": {"status_code": 0}}))
            svc = ImageService(client, db, Path(tmp) / "images", daily_limit=5, run_async=False)
            img = svc.start(conn, 1, "番茄炒蛋", "一盘番茄炒蛋")
            row = conn.execute("SELECT status, file, prompt FROM images WHERE id=?", (img["id"],)).fetchone()
            self.assertIn("food photography", row[2])                          # MiniMax 用英文风格词
            self.assertNotIn("美食摄影", row[2])
            self.assertEqual(row[0], "ready")
            self.assertTrue(row[1].endswith(".png") and (Path(tmp) / "images" / row[1]).exists())
            conn.close()


class ProviderSelectionTests(unittest.TestCase):
    def settings(self, **env):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        return make_settings(self.tmp.name, **env)

    def test_auto_prefers_minimax_and_vision_uses_deepseek(self):
        s = self.settings(MINIMAX_API_KEY="m" * 20, DASHSCOPE_API_KEY="d" * 20, LLM_API_KEY="l" * 20)
        self.assertEqual(s.image_backend, "minimax")
        self.assertTrue(s.vision_enabled)                                       # 识图默认复用 DeepSeek
        s = self.settings(DASHSCOPE_API_KEY="d" * 20)
        self.assertEqual(s.image_backend, "dashscope")
        self.assertFalse(s.vision_enabled)
        s = self.settings(MINIMAX_API_KEY="m" * 20)
        self.assertEqual(s.image_backend, "minimax")
        self.assertFalse(s.vision_enabled)
        self.assertIsNone(self.settings().image_backend)

    def test_explicit_provider(self):
        s = self.settings(MINIMAX_API_KEY="m" * 20, DASHSCOPE_API_KEY="d" * 20, IMAGE_PROVIDER="dashscope")
        self.assertEqual(s.image_backend, "dashscope")
        s = self.settings(DASHSCOPE_API_KEY="d" * 20, IMAGE_PROVIDER="minimax")
        self.assertIsNone(s.image_backend)                                      # 指定了 MiniMax 但没 key：不偷偷换百炼
        with self.assertRaises(RuntimeError):
            self.settings(IMAGE_PROVIDER="midjourney")
        # off：生图关闭时，只要有 LLM_API_KEY（DeepSeek），拍照识图仍启用
        s = self.settings(MINIMAX_API_KEY="m" * 20, DASHSCOPE_API_KEY="d" * 20, LLM_API_KEY="l" * 20, IMAGE_PROVIDER="off")
        self.assertIsNone(s.image_backend)
        self.assertTrue(s.vision_enabled)

    def test_app_builds_minimax_client(self):
        from app import create_app
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(make_settings(tmp, MINIMAX_API_KEY="m" * 20))
            self.assertTrue(app.test_client().get("/api/meta").get_json()["image_enabled"])


class PantryToolHonestyTests(DbCase):
    def test_tool_says_new_vs_merged(self):
        self.add({"name": "胡萝卜", "quantity": 2, "unit": "根"})
        ctx = tools.ToolContext(conn=self.conn, user_id=1, now=NOW)
        result, cards = tools.execute(ctx, "add_pantry_items",
                                      json.dumps({"items": [{"name": "牛奶", "quantity": 1, "unit": "盒"},
                                                            {"name": "胡萝卜", "quantity": 2, "unit": "根"}]}))
        self.assertEqual(len(result["newly_added"]), 1)
        self.assertTrue(result["newly_added"][0].startswith("牛奶 1盒"))
        self.assertTrue(result["merged_into_existing"][0].startswith("胡萝卜 4根"))  # 2 + 2，由服务端算好
        self.assertIn("不要说「之前那盒」", result["note_for_reply"])
        self.assertEqual(cards[0]["names"], ["牛奶", "胡萝卜"])


class GarnishTests(DbCase):
    def test_missing_garnish_does_not_block_cook_now(self):
        self.add("番茄", "鸡蛋", "五花肉")
        llm = JsonLLM({"recipes": [
            recipe("微辣番茄蛋汤", [("番茄", "2个", False), ("鸡蛋", "2个", False), ("小米辣", "1根", False), ("葱花", "少许", False)]),
            recipe("回锅肉", [("五花肉", "200g", False), ("豆瓣酱", "1勺", False)]),
        ]})
        result = kitchen.recommend(self.conn, llm, "m", 1, NOW)
        by = {r["title"]: r for r in result["recipes"]}
        soup = by["微辣番茄蛋汤"]
        self.assertEqual(soup["missing"], [])                                   # 小料缺了也能做
        chili = next(i for i in soup["ingredients"] if i["name"] == "小米辣")
        self.assertTrue(chili["optional"] and chili["auto_optional"])
        self.assertEqual(by["回锅肉"]["missing"], ["豆瓣酱"])                     # 酱料决定味道，仍算缺
        self.assertIn("口味偏好（如微辣）不要变成必需的配料", llm.calls[0]["messages"][0]["content"])
        self.assertTrue(kitchen.is_garnish("葱") and not kitchen.is_garnish("洋葱") and not kitchen.is_garnish("蚝油"))


if __name__ == "__main__":
    unittest.main()
