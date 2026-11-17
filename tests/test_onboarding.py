"""新手引导（第 3 期）回归测试：进度从真实数据推导、老用户不被打扰、情境提示只出现一次。

运行：python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

import kitchen  # noqa: E402
import onboarding  # noqa: E402
import prefs  # noqa: E402
from health import ValidationError  # noqa: E402
from test_kitchen import NOW, TODAY, DbCase, JsonLLM, recipe  # noqa: E402
from test_server import make_settings  # noqa: E402


class TourTests(DbCase):
    def test_steps_follow_real_actions(self):
        s = onboarding.state(self.conn, 1, TODAY)
        self.assertEqual((s["tour"], s["current"]), ("active", "pantry"))
        self.add("鸡蛋", "番茄")
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["current"], "pantry")   # 还不够 3 样
        self.add("洋葱")
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["current"], "recommend")
        r = kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("番茄炒蛋", [("番茄", "2个", False), ("鸡蛋", "2个", False)])]}),
                              "m", 1, NOW)
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["current"], "open")
        onboarding.update(self.conn, 1, {"opened_recipe": True}, TODAY)
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["current"], "cook")
        kitchen.set_saved(self.conn, 1, r["recipes"][0]["id"], True)              # 收藏也算完成第 3 步
        s = onboarding.state(self.conn, 1, TODAY)
        self.assertIsNone(s["current"])
        self.assertEqual(s["tour"], "active")                                     # 等用户看完完成提示
        s = onboarding.update(self.conn, 1, {"tour": "done"}, TODAY)
        self.assertEqual(s["tour"], "done")

    def test_using_up_food_does_not_undo_step_one(self):
        items = self.add("鸡蛋", "番茄", "洋葱")
        for item in items:
            kitchen.remove_item(self.conn, 1, item["id"], "used")
        self.assertTrue(onboarding.state(self.conn, 1, TODAY)["steps"]["pantry"])

    def test_veteran_skips_tour_and_users_are_isolated(self):
        self.add("鸡蛋")
        r = kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}), "m", 1, NOW)
        kitchen.cook(self.conn, 1, r["recipes"][0]["id"], NOW, [])
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["tour"], "done")    # 已经做过菜的老用户
        self.assertEqual(onboarding.state(self.conn, 2, TODAY)["tour"], "active")
        self.assertFalse(onboarding.state(self.conn, 2, TODAY)["steps"]["recommend"])

    def test_checklist_counts_questionnaire(self):
        s = onboarding.state(self.conn, 1, TODAY)
        self.assertEqual((s["checklist_done"], len(s["checklist"])), (0, 5))
        prefs.save(self.conn, 1, {}, status="skipped")
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["checklist_done"], 0)  # 跳过不算完成
        prefs.save(self.conn, 1, {}, status="done")
        self.assertEqual(onboarding.state(self.conn, 1, TODAY)["checklist_done"], 1)

    def test_bad_updates(self):
        with self.assertRaises(ValidationError):
            onboarding.update(self.conn, 1, {"tour": "active"}, TODAY)
        with self.assertRaises(ValidationError):
            onboarding.update(self.conn, 1, {"seen_tip": "nope"}, TODAY)


class TipTests(DbCase):
    def setUp(self):
        super().setUp()
        onboarding.update(self.conn, 1, {"tour": "skipped"}, TODAY)

    def tips(self, today=TODAY):
        return onboarding.state(self.conn, 1, today)["tips"]

    def test_no_tips_while_tour_is_running(self):
        onboarding.state(self.conn, 2, TODAY)
        kitchen.add_items(self.conn, 2, [{"name": "菠菜", "expires_on": "2026-11-18"}], TODAY)
        self.assertEqual(onboarding.state(self.conn, 2, TODAY)["tips"], [])

    def test_expiring_tip_shows_once(self):
        self.add("鸡蛋")
        self.assertNotIn("expiring", self.tips())
        self.add({"name": "菠菜", "expires_on": "2026-11-18"})
        self.assertEqual(self.tips()[0], "expiring")
        onboarding.update(self.conn, 1, {"seen_tip": "expiring"}, TODAY)
        self.assertNotIn("expiring", self.tips())

    def test_skipped_questions_asked_after_first_recommendation(self):
        prefs.save(self.conn, 1, {}, status="skipped", skipped=["equipment", "body", "staples"])
        self.add("鸡蛋")
        self.assertEqual(self.tips(), [])                                     # 还没见过推荐，先不问
        kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}), "m", 1, NOW)
        self.assertEqual(self.tips(), ["ask_equipment", "ask_staples"])       # body 不在这里问
        prefs.save(self.conn, 1, {"equipment": ["wok"]})                      # 回答了就不再问
        self.assertEqual(self.tips(), ["ask_staples"])

    def test_several_tips_can_be_dismissed_at_once(self):
        prefs.save(self.conn, 1, {}, status="skipped", skipped=list(prefs.QUESTIONS))
        self.add("鸡蛋")
        kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}), "m", 1, NOW)
        asks = [t for t in self.tips() if t.startswith("ask_")]
        self.assertEqual(len(asks), 7)
        onboarding.update(self.conn, 1, {"seen_tip": asks}, TODAY)
        self.assertEqual([t for t in self.tips() if t.startswith("ask_")], [])
        with self.assertRaises(ValidationError):
            onboarding.update(self.conn, 1, {"seen_tip": []}, TODAY)

    def test_expiry_dates_tip_when_everything_is_estimated(self):
        self.add("鸡蛋", "番茄", "洋葱", "土豆", "胡萝卜")
        self.assertIn("expiry_dates", self.tips())
        self.add({"name": "牛奶", "expires_on": "2026-11-25"})                # 有一样填了真实日期
        self.assertNotIn("expiry_dates", self.tips())

    def test_health_tip_after_a_week_only_if_not_already_in_nav(self):
        self.add("鸡蛋")
        r = kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}), "m", 1, NOW)
        kitchen.cook(self.conn, 1, r["recipes"][0]["id"], NOW, [])
        created = date.fromisoformat(self.conn.execute("SELECT created_at FROM users WHERE id=1").fetchone()[0][:10])
        self.assertNotIn("health", self.tips(created + timedelta(days=6)))
        self.assertIn("health", self.tips(created + timedelta(days=7)))
        prefs.save(self.conn, 1, {"goals": ["healthy"]})
        self.assertNotIn("health", self.tips(created + timedelta(days=7)))


class OnboardingApiTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.client = create_app(make_settings(self.tmp.name)).test_client()
        self.client.post("/api/auth/register", json={"username": "newbie", "password": "password-123"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        s = self.client.get("/api/onboarding").get_json()
        self.assertEqual((s["tour"], s["current"]), ("active", "pantry"))
        self.client.post("/api/pantry", json={"items": [{"name": "鸡蛋"}, {"name": "番茄"}, {"name": "洋葱"}]})
        self.assertEqual(self.client.get("/api/onboarding").get_json()["current"], "recommend")
        s = self.client.post("/api/onboarding", json={"tour": "skipped", "checklist_dismissed": True}).get_json()
        self.assertEqual((s["tour"], s["checklist_dismissed"]), ("skipped", True))
        self.assertEqual(self.client.post("/api/onboarding", json={"seen_tip": "x"}).status_code, 400)
        self.client.post("/api/auth/logout", json={})
        self.assertEqual(self.client.get("/api/onboarding").status_code, 401)


if __name__ == "__main__":
    unittest.main()
