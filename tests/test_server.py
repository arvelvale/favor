"""后端回归测试：配置安全、账号、记录与目标计算、agent 工具循环（用假模型客户端，不访问网络）。

运行：python -m unittest discover -s tests -v
"""
import json
import os
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import health  # noqa: E402
from config import Settings  # noqa: E402


def make_settings(folder, **extra):
    env = {"SECRET_KEY": secrets.token_urlsafe(48), "DATABASE_PATH": str(Path(folder) / "t.sqlite3"),
           "WEB_DIST": str(Path(folder) / "dist"), **extra}
    with patch.dict(os.environ, env, clear=True), patch("config.load_dotenv"):
        return Settings()


# ---------------------------------------------------------------- 假模型

def chunk(content=None, tool_calls=None):
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tool_calls))])


def tool_chunk(index, call_id, name, args):
    # 模拟流式分片：名字和参数拆成两段到达
    half = len(args) // 2
    return [chunk(tool_calls=[NS(index=index, id=call_id, function=NS(name=name, arguments=args[:half]))]),
            chunk(tool_calls=[NS(index=index, id=None, function=NS(name=None, arguments=args[half:]))])]


class FakeLLM:
    """按脚本依次返回每次 create() 的流；记录收到的 messages 供断言。"""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.scripts.pop(0))


class ConfigTests(unittest.TestCase):
    def test_secret_key_required_and_long(self):
        with patch.dict(os.environ, {}, clear=True), patch("config.load_dotenv"):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                Settings()
        with patch.dict(os.environ, {"SECRET_KEY": "short"}, clear=True), patch("config.load_dotenv"):
            with self.assertRaisesRegex(RuntimeError, "at least 32"):
                Settings()

    def test_llm_optional_and_legacy_alias(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(make_settings(d).llm_enabled)
            self.assertTrue(make_settings(d, DEEPSEEK_API_KEY="x" * 20).llm_enabled)


class TargetTests(unittest.TestCase):
    def test_mifflin_and_goal_direction(self):
        profile = {"sex": "male", "birth_year": 2000, "height_cm": 175, "weight_kg": 70,
                   "activity_level": "moderate", "goal": "lose"}
        from datetime import date
        t = health.compute_targets(profile, date(2026, 1, 1))
        bmr = 10 * 70 + 6.25 * 175 - 5 * 26 + 5          # 1668.75
        self.assertEqual(t["bmr"], round(bmr))
        # 减脂 = 15% 缺口：目标应低于 TDEE，约为 TDEE×0.85
        self.assertLess(t["calories"], t["tdee"])
        self.assertAlmostEqual(t["calories"], bmr * 1.55 * 0.85, delta=10)
        self.assertEqual(t["protein_g"], 112)              # 1.6 g/kg
        self.assertEqual(t["water_ml"], 2300)              # 33 ml/kg → 2310 → 取整到 50

    def test_safety_floor(self):
        from datetime import date
        tiny = {"sex": "female", "birth_year": 1960, "height_cm": 150, "weight_kg": 42,
                "activity_level": "sedentary", "goal": "lose"}
        self.assertGreaterEqual(health.compute_targets(tiny, date(2026, 1, 1))["calories"], 1200)

    def test_incomplete_profile_defaults(self):
        from datetime import date
        t = health.compute_targets({}, date(2026, 1, 1))
        self.assertFalse(t["complete"])
        self.assertEqual(t["calories"], 2000)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from app import create_app
        self.fake = FakeLLM([])
        self.app = create_app(make_settings(self.tmp.name), llm_client=self.fake)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def register(self, name="alice"):
        res = self.client.post("/api/auth/register", json={"username": name, "password": "correct-horse"})
        self.assertEqual(res.status_code, 201, res.get_json())

    def test_auth_flow_and_isolation(self):
        self.assertEqual(self.client.get("/api/summary").status_code, 401)
        self.register()
        rec = self.client.post("/api/records", json={"kind": "water", "data": {"ml": 300}}).get_json()["record"]
        self.client.post("/api/auth/logout", json={})
        self.register("bob")
        self.assertEqual(self.client.delete(f"/api/records/{rec['id']}").status_code, 404)
        self.assertEqual(self.client.get("/api/summary").get_json()["totals"]["water_ml"], 0)
        bad = self.client.post("/api/auth/login", json={"username": "alice", "password": "wrong-password"})
        self.assertEqual(bad.status_code, 401)

    def test_json_required_for_writes(self):
        self.register()
        res = self.client.post("/api/records", data="kind=water", content_type="application/x-www-form-urlencoded")
        self.assertEqual(res.status_code, 415)

    def test_records_summary_and_weight_sync(self):
        self.register()
        self.client.post("/api/records", json={"kind": "meal", "data": {"meal_type": "lunch", "items": [
            {"name": "牛肉面", "calories": 550, "protein": 25}, {"name": "卤蛋", "calories": 80, "protein": 6}]}})
        self.client.post("/api/records", json={"kind": "exercise",
                                               "data": {"activity": "跑步", "minutes": 30, "intensity": "high"}})
        self.client.post("/api/records", json={"kind": "weight", "data": {"kg": 65.2}})
        s = self.client.get("/api/summary").get_json()
        self.assertEqual(s["totals"]["calories_in"], 630)
        self.assertEqual(s["totals"]["protein"], 31)
        self.assertGreater(s["totals"]["exercise_kcal"], 0)
        self.assertEqual(self.client.get("/api/profile").get_json()["profile"]["weight_kg"], 65.2)
        bad = self.client.post("/api/records", json={"kind": "water", "data": {"ml": -5}})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("饮水量", bad.get_json()["error"])

    def test_chat_unavailable_without_key(self):
        from app import create_app
        app = create_app(make_settings(self.tmp.name))
        c = app.test_client()
        c.post("/api/auth/register", json={"username": "carol", "password": "correct-horse"})
        conv = c.post("/api/conversations", json={}).get_json()["conversation"]
        res = c.post(f"/api/conversations/{conv['id']}/chat", json={"message": "你好"})
        self.assertEqual(res.status_code, 503)

    def chat(self, conv_id, text):
        res = self.client.post(f"/api/conversations/{conv_id}/chat", json={"message": text})
        self.assertEqual(res.status_code, 200)
        return [json.loads(line[6:]) for line in res.get_data(as_text=True).splitlines() if line.startswith("data: ")]

    def test_agent_tool_loop_end_to_end(self):
        self.register()
        conv = self.client.post("/api/conversations", json={}).get_json()["conversation"]
        meal = json.dumps({"meal_type": "breakfast", "items": [
            {"name": "肉包", "amount": "2个", "calories": 420, "protein": 16},
            {"name": "豆浆", "amount": "1杯", "calories": 90, "protein": 7}]}, ensure_ascii=False)
        run = json.dumps({"activity": "跑步", "minutes": 20, "intensity": "moderate"}, ensure_ascii=False)
        self.fake.scripts = [
            # 第 1 次：模型先说一句，再并行调用两个工具（参数分片到达）
            [chunk("好的，"), *tool_chunk(0, "c1", "log_meal", meal), *tool_chunk(1, "c2", "log_exercise", run)],
            # 第 2 次：看到工具结果后给最终回复
            [chunk("已帮你记下早餐 510 kcal"), chunk("和 20 分钟跑步。")],
        ]
        events = self.chat(conv["id"], "早饭两个肉包一杯豆浆，跑了20分钟")
        types = [e["type"] for e in events]
        self.assertEqual(types.count("card"), 2)
        self.assertEqual(types[-1], "done")
        self.assertEqual(events[-1]["title"], "早饭两个肉包一杯豆浆，跑了20分钟")

        # 第二次调用模型时，历史里应有配对完整的 tool 消息
        second = self.fake.calls[1]["messages"]
        tool_msgs = [m for m in second if m["role"] == "tool"]
        self.assertEqual({m["tool_call_id"] for m in tool_msgs}, {"c1", "c2"})
        self.assertIn("今日概况", second[0]["content"])

        totals = self.client.get("/api/summary").get_json()["totals"]
        self.assertEqual(totals["calories_in"], 510)
        self.assertEqual(totals["exercise_min"], 20)

        # 历史回放：一个 user 气泡 + 一个带两张卡片的 assistant 气泡
        msgs = self.client.get(f"/api/conversations/{conv['id']}/messages").get_json()["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        self.assertEqual(len(msgs[1]["cards"]), 2)
        self.assertIn("510 kcal", msgs[1]["content"])

        # 第二轮：历史回放给模型时 tool 配对仍然完整
        self.fake.scripts = [[chunk("不客气")]]
        self.chat(conv["id"], "谢谢")
        replay = self.fake.calls[-1]["messages"]
        ids = [tc["id"] for m in replay if m.get("tool_calls") for tc in m["tool_calls"]]
        self.assertEqual(ids, ["c1", "c2"])

    def test_agent_tool_validation_error_goes_back_to_model(self):
        self.register()
        conv = self.client.post("/api/conversations", json={}).get_json()["conversation"]
        self.fake.scripts = [[*tool_chunk(0, "c1", "log_water", '{"ml": 99999}')], [chunk("这个量好像不对")]]
        events = self.chat(conv["id"], "喝了 99999ml 水")
        self.assertEqual(events[-1]["type"], "done")
        tool_msg = [m for m in self.fake.calls[1]["messages"] if m["role"] == "tool"][0]
        self.assertFalse(json.loads(tool_msg["content"])["ok"])
        self.assertEqual(self.client.get("/api/summary").get_json()["totals"]["water_ml"], 0)

    def test_model_failure_yields_error_event(self):
        self.register()
        conv = self.client.post("/api/conversations", json={}).get_json()["conversation"]

        class Boom(Exception):
            pass

        def explode(**_):
            raise Boom("upstream detail with secret")
        self.fake.chat.completions.create = explode
        events = self.chat(conv["id"], "你好")
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn("secret", events[-1]["message"])


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- 菜品配图（百炼）

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class FakeImages:
    def __init__(self, result=PNG, error=None):
        self.result, self.error, self.prompts = result, error, []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            from images import ImageError
            raise ImageError(self.error)
        return self.result


class ImageTests(unittest.TestCase):
    def make(self, images=None, **env):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeLLM([])
        self.images = images
        app = create_app(make_settings(self.tmp.name, **env), llm_client=self.fake,
                         image_client=images, images_async=False)
        self.client = app.test_client()
        res = self.client.post("/api/auth/register", json={"username": "ivy", "password": "correct-horse"})
        self.assertEqual(res.status_code, 201)
        self.conv = self.client.post("/api/conversations", json={}).get_json()["conversation"]["id"]

    def chat(self, text):
        res = self.client.post(f"/api/conversations/{self.conv}/chat", json={"message": text})
        return [json.loads(l[6:]) for l in res.get_data(as_text=True).splitlines() if l.startswith("data: ")]

    def image_call(self, call_id="i1", title="香煎鸡胸", desc="香煎鸡胸肉切片配西兰花"):
        args = json.dumps({"title": title, "description": desc}, ensure_ascii=False)
        return tool_chunk(0, call_id, "generate_food_image", args)

    def test_tool_hidden_without_image_service(self):
        self.make(images=None)
        self.fake.scripts = [[chunk("好")]]
        self.chat("帮我配个晚餐")
        names = [t["function"]["name"] for t in self.fake.calls[0]["tools"]]
        self.assertNotIn("generate_food_image", names)
        self.assertNotIn("generate_food_image", self.fake.calls[0]["messages"][0]["content"])
        self.assertFalse(self.client.get("/api/meta").get_json()["image_enabled"])

    def test_image_generated_stored_and_served_to_owner_only(self):
        self.make(images=FakeImages())
        self.fake.scripts = [[*self.image_call()], [chunk("这是晚餐建议")]]
        events = self.chat("帮我配个晚餐，想看看成品")
        card = next(e["card"] for e in events if e["type"] == "card")
        self.assertEqual(card["type"], "image")
        self.assertIn("generate_food_image", [t["function"]["name"] for t in self.fake.calls[0]["tools"]])
        # 风格词由后端统一追加，模型只描述菜品
        self.assertIn("香煎鸡胸肉切片配西兰花", self.images.prompts[0])
        self.assertIn("美食摄影", self.images.prompts[0])

        meta = self.client.get(f"/api/images/{card['image_id']}").get_json()["image"]
        self.assertEqual(meta["status"], "ready")
        file = self.client.get(f"/api/images/{card['image_id']}/file")
        self.assertEqual(file.status_code, 200)
        self.assertEqual(file.data, PNG)
        self.assertIn("private", file.headers["Cache-Control"])
        file.close()

        # 历史回放里保留图片卡片
        msgs = self.client.get(f"/api/conversations/{self.conv}/messages").get_json()["messages"]
        self.assertEqual(msgs[-1]["cards"][0]["image_id"], card["image_id"])

        # 别的用户拿不到
        self.client.post("/api/auth/logout", json={})
        self.client.post("/api/auth/register", json={"username": "mallory", "password": "correct-horse"})
        self.assertEqual(self.client.get(f"/api/images/{card['image_id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/images/{card['image_id']}/file").status_code, 404)

    def test_one_image_per_turn(self):
        self.make(images=FakeImages())
        second = tool_chunk(1, "i2", "generate_food_image", json.dumps({"title": "b", "description": "番茄炒蛋"}, ensure_ascii=False))
        self.fake.scripts = [[*self.image_call(), *second], [chunk("ok")]]
        events = self.chat("两道菜都来张图")
        self.assertEqual(sum(1 for e in events if e["type"] == "card"), 1)
        tool_results = [json.loads(m["content"]) for m in self.fake.calls[1]["messages"] if m["role"] == "tool"]
        self.assertEqual([r["ok"] for r in tool_results], [True, False])
        self.assertEqual(len(self.images.prompts), 1)

    def test_daily_limit(self):
        self.make(images=FakeImages(), IMAGE_DAILY_LIMIT="1")
        self.fake.scripts = [[*self.image_call("a")], [chunk("1")], [*self.image_call("b")], [chunk("2")]]
        self.chat("第一张")
        self.chat("第二张")
        result = json.loads([m for m in self.fake.calls[3]["messages"] if m["role"] == "tool"][-1]["content"])
        self.assertFalse(result["ok"])
        self.assertIn("用完", result["error"])
        self.assertEqual(len(self.images.prompts), 1)

    def test_upstream_arrears_becomes_friendly_failure(self):
        self.make(images=FakeImages(error="Arrearage"))
        self.fake.scripts = [[*self.image_call()], [chunk("ok")]]
        card = next(e["card"] for e in self.chat("来张图") if e["type"] == "card")
        meta = self.client.get(f"/api/images/{card['image_id']}").get_json()["image"]
        self.assertEqual(meta["status"], "failed")
        self.assertIn("欠费", meta["error"])
        self.assertEqual(self.client.get(f"/api/images/{card['image_id']}/file").status_code, 404)
        # 失败的不计入每日额度
        from db import connect
        conn = connect(Path(self.tmp.name) / "t.sqlite3")
        self.assertEqual(conn.execute("SELECT error FROM images").fetchone()[0], "Arrearage")
        conn.close()

    def test_non_image_payload_rejected(self):
        self.make(images=FakeImages(result=b"<html>not an image</html>"))
        self.fake.scripts = [[*self.image_call()], [chunk("ok")]]
        card = next(e["card"] for e in self.chat("来张图") if e["type"] == "card")
        self.assertEqual(self.client.get(f"/api/images/{card['image_id']}").get_json()["image"]["status"], "failed")
