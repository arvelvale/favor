"""越用越准（第 5 期）回归测试：做过/收藏/跳过/不想吃 怎样改变下一次推荐，过期食材清点。

用假模型，每次返回同样几道菜，看服务端的剔除、标注、排序和提示词怎么随用户行为变化。
运行：python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

import kitchen  # noqa: E402
import onboarding  # noqa: E402
import taste  # noqa: E402
from health import ValidationError  # noqa: E402
from test_kitchen import NOW, TODAY, DbCase, JsonLLM, recipe  # noqa: E402
from test_server import make_settings  # noqa: E402


def three():
    return {"recipes": [
        recipe("番茄炒蛋", [("番茄", "2个", False), ("鸡蛋", "2个", False)], minutes=12),
        recipe("蒸蛋", [("鸡蛋", "2个", False)], minutes=10),
        recipe("番茄蛋汤", [("番茄", "1个", False), ("鸡蛋", "1个", False)], minutes=15),
    ]}


class TasteCase(DbCase):
    def setUp(self):
        super().setUp()
        self.add("番茄", "鸡蛋")

    def rec(self, now=NOW):
        llm = JsonLLM(three())
        result = kitchen.recommend(self.conn, llm, "m", 1, now)
        self.last_prompt = llm.calls[0]["messages"][1]["content"]
        return result

    def by_title(self, result):
        return {r["title"]: r for r in result["recipes"]}


class TitleKeyTests(unittest.TestCase):
    def test_aliases_and_spaces(self):
        self.assertEqual(taste.title_key("西红柿 炒蛋"), taste.title_key("番茄炒蛋"))
        self.assertNotEqual(taste.title_key("番茄炒蛋"), taste.title_key("番茄蛋汤"))


class SkipTests(TasteCase):
    def test_untouched_recipes_count_as_skipped_when_asking_again(self):
        first = self.by_title(self.rec())
        taste.record_open(self.conn, 1, first["番茄炒蛋"]["id"], NOW)
        kitchen.set_saved(self.conn, 1, first["蒸蛋"]["id"], True)
        self.rec()                                                         # 换一批：只有番茄蛋汤没被碰过
        skips = [r["title"] for r in self.conn.execute("SELECT title FROM recipe_feedback WHERE kind='skip'")]
        self.assertEqual(skips, ["番茄蛋汤"])
        third = self.by_title(self.rec())                                  # 再换：第二批三道都没碰 → 番茄蛋汤第 2 次
        soup = third["番茄蛋汤"]
        self.assertIn("最近跳过了 2 次", soup["fit"])
        self.assertEqual(list(third)[-1], "番茄蛋汤")                      # 排到最后
        self.assertIn("多次跳过，不要推荐", self.last_prompt)
        self.assertIn("番茄蛋汤", self.last_prompt.split("多次跳过")[1].splitlines()[0])

    def test_skipped_then_cooked_is_not_a_dislike(self):
        for _ in range(3):
            last = self.rec()
        self.assertIn("最近跳过了", " ".join(self.by_title(self.rec())["番茄蛋汤"]["fit"]))
        soup = self.by_title(self.rec())["番茄蛋汤"]
        kitchen.cook(self.conn, 1, soup["id"], NOW + timedelta(minutes=5), [])   # 后来又做了
        p = taste.profile(self.conn, 1, NOW + timedelta(minutes=10))
        self.assertNotIn(taste.title_key("番茄蛋汤"), p["skipped"])
        self.assertIsNotNone(last)

    def test_opened_counts_for_onboarding_too(self):
        r = self.rec()["recipes"][0]
        onboarding.state(self.conn, 1, TODAY)
        taste.record_open(self.conn, 1, r["id"], NOW)
        taste.record_open(self.conn, 1, r["id"], NOW)                       # 重复调用不重复记
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM recipe_feedback WHERE kind='open'").fetchone()[0], 1)
        self.assertTrue(onboarding.state(self.conn, 1, TODAY)["steps"]["open"])
        self.assertFalse(taste.record_open(self.conn, 2, r["id"], NOW))    # 别人的菜


class DislikeTests(TasteCase):
    def test_not_like_is_dropped_until_forgotten(self):
        egg = self.by_title(self.rec())["蒸蛋"]
        taste.dislike(self.conn, 1, egg["id"], "not_like", NOW)
        result = self.rec()
        self.assertNotIn("蒸蛋", self.by_title(result))
        self.assertIn({"title": "蒸蛋", "reason": "你说过不爱吃"}, result["dropped"])
        self.assertIn("不爱吃或多次跳过", self.last_prompt)
        self.assertEqual(taste.forget(self.conn, 1, "蒸 蛋"), 1)
        self.assertIn("蒸蛋", self.by_title(self.rec()))

    def test_too_hard_and_recent_are_soft(self):
        r = self.by_title(self.rec())
        taste.dislike(self.conn, 1, r["番茄炒蛋"]["id"], "too_hard", NOW)
        taste.dislike(self.conn, 1, r["蒸蛋"]["id"], "recent", NOW)
        again = self.by_title(self.rec())
        self.assertIn("你说过这道太麻烦", again["番茄炒蛋"]["fit"])
        self.assertIn("你说最近吃过", again["蒸蛋"]["fit"])
        self.assertIn("倾向步骤更少", self.last_prompt)
        later = self.by_title(self.rec(NOW + timedelta(days=8)))           # 「最近吃过」7 天后失效，「太麻烦」还在
        self.assertNotIn("你说最近吃过", later["蒸蛋"]["fit"])
        self.assertIn("你说过这道太麻烦", later["番茄炒蛋"]["fit"])

    def test_bad_reason(self):
        r = self.rec()["recipes"][0]
        with self.assertRaises(ValidationError):
            taste.dislike(self.conn, 1, r["id"], "meh", NOW)
        self.assertIsNone(taste.dislike(self.conn, 2, r["id"], "not_like", NOW))


class CookedTests(TasteCase):
    def test_recently_cooked_is_demoted_and_liked_is_remembered(self):
        egg = self.by_title(self.rec())["番茄炒蛋"]
        kitchen.cook(self.conn, 1, egg["id"], NOW - timedelta(days=2), [{"item_id": i["pantry_id"], "used_up": False}
                                                                          for i in egg["ingredients"] if i.get("pantry_id")])
        result = self.rec()
        titles = [r["title"] for r in result["recipes"]]
        self.assertEqual(titles[-1], "番茄炒蛋")
        self.assertIn("前天刚做过", self.by_title(result)["番茄炒蛋"]["fit"])
        self.assertIn("最近刚吃过，这次别再推荐：番茄炒蛋", self.last_prompt)
        self.assertIn("做过、收藏过的菜", self.last_prompt)
        later = self.by_title(self.rec(NOW + timedelta(days=3)))           # 5 天前做的：不再算「最近」，但还算「喜欢」
        self.assertEqual(later["番茄炒蛋"]["fit"], [])
        self.assertIn("番茄炒蛋", taste.summary(self.conn, 1, NOW + timedelta(days=3))["liked"])


class ReviewTests(DbCase):
    def test_expired_items_are_left_out_until_confirmed(self):
        old, fresh = self.add({"name": "菠菜", "expires_on": "2026-11-15"}, "鸡蛋")
        llm = JsonLLM({"recipes": [recipe("菠菜炒蛋", [("菠菜", "1把", False), ("鸡蛋", "2个", False)])]})
        r = kitchen.recommend(self.conn, llm, "m", 1, NOW)["recipes"][0]
        self.assertNotIn("菠菜", llm.calls[0]["messages"][1]["content"].split("常备调料")[0])
        self.assertEqual(r["missing"], ["菠菜"])                            # 过期的不算「有」
        done = kitchen.review_items(self.conn, 1, [{"id": old["id"], "action": "keep"}], TODAY)
        self.assertEqual(done["keep"], 1)
        spinach = next(p for p in kitchen.list_pantry(self.conn, 1, TODAY) if p["name"] == "菠菜")
        self.assertEqual((spinach["days_left"], spinach["expires_estimated"]), (2, True))
        self.assertEqual(kitchen.recipe_payload(self.conn, 1, r["id"], TODAY)["missing"], [])
        self.assertTrue(fresh)

    def test_all_expired_gives_a_hint_and_review_removes(self):
        a, b = self.add({"name": "菠菜", "expires_on": "2026-11-10"}, {"name": "牛奶", "expires_on": "2026-11-12"})
        with self.assertRaisesRegex(ValidationError, "先在首页清点"):
            kitchen.recommend(self.conn, JsonLLM(), "m", 1, NOW)
        done = kitchen.review_items(self.conn, 1, [{"id": a["id"], "action": "used"}, {"id": b["id"], "action": "discarded"},
                                                  {"id": 99999, "action": "used"}], TODAY)
        self.assertEqual(done, {"keep": 0, "used": 1, "discarded": 1})
        self.assertEqual(kitchen.list_pantry(self.conn, 1, TODAY), [])
        for bad in ([], [{"id": a["id"], "action": "eat"}], [{"id": "1", "action": "used"}], None):
            with self.assertRaises(ValidationError):
                kitchen.review_items(self.conn, 1, bad, TODAY)

    def test_cannot_review_someone_elses_item(self):
        (item,) = self.add({"name": "菠菜", "expires_on": "2026-11-10"}, user=2)
        self.assertEqual(kitchen.review_items(self.conn, 1, [{"id": item["id"], "action": "discarded"}], TODAY)["discarded"], 0)
        self.assertEqual(len(kitchen.list_pantry(self.conn, 2, TODAY)), 1)


class LearningTipTests(DbCase):
    def test_learning_tip_after_three_active_days(self):
        onboarding.update(self.conn, 1, {"tour": "skipped"}, TODAY)
        self.add("鸡蛋")
        for day in range(3):
            kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}), "m", 1, NOW)
            self.conn.execute("UPDATE recipes SET created_at=? WHERE id=(SELECT MAX(id) FROM recipes)",
                              (f"2026-11-{10 + day} 12:00:00",))
            if day < 2:
                self.assertNotIn("learning", onboarding.state(self.conn, 1, TODAY)["tips"])
        self.assertIn("learning", onboarding.state(self.conn, 1, TODAY)["tips"])


class TasteApiTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.llm = JsonLLM()
        self.client = create_app(make_settings(self.tmp.name, LLM_API_KEY="x" * 20), llm_client=self.llm).test_client()
        self.client.post("/api/auth/register", json={"username": "taster", "password": "password-123"})
        self.client.post("/api/pantry", json={"items": [{"name": "番茄"}, {"name": "鸡蛋"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        self.llm.payloads.append(three())
        recs = self.client.post("/api/recipes/recommend", json={}).get_json()["recipes"]
        egg = next(r for r in recs if r["title"] == "蒸蛋")
        self.assertEqual(self.client.post(f"/api/recipes/{egg['id']}/opened", json={}).status_code, 200)
        self.assertTrue(self.client.get("/api/onboarding").get_json()["steps"]["open"])
        self.assertEqual(self.client.post(f"/api/recipes/{egg['id']}/dislike", json={"reason": "x"}).status_code, 400)
        r = self.client.post(f"/api/recipes/{egg['id']}/dislike", json={"reason": "not_like"}).get_json()
        self.assertEqual(r["reason_label"], "不爱吃")
        summary = self.client.get("/api/taste").get_json()
        self.assertEqual(summary["less"], [{"title": "蒸蛋", "why": "不爱吃，不再推荐"}])
        after = self.client.post("/api/taste/forget", json={"title": "蒸蛋"}).get_json()
        self.assertEqual((after["removed"], after["less"]), (1, []))
        self.assertEqual(self.client.post("/api/recipes/99999/opened", json={}).status_code, 404)

    def test_review_endpoint(self):
        item = self.client.post("/api/pantry", json={"items": [{"name": "菠菜", "expires_on": "2020-01-01"}]}).get_json()["items"][0]
        r = self.client.post("/api/pantry/review", json={"items": [{"id": item["id"], "action": "discarded"}]})
        self.assertEqual(r.get_json()["discarded"], 1)
        self.assertEqual(self.client.post("/api/pantry/review", json={"items": []}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
