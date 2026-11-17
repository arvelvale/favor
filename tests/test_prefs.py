"""问卷与偏好（第 2 期）回归测试。

完成标准：不同问卷答案得到可见不同的推荐。这里用同一份假模型输出、不同的答案，
断言服务端的硬过滤（厨具、饮食方式、忌口、过敏）、缺料计算（常备调料）、排序（目标、时间）
和提示词都按答案变化。运行：python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

import kitchen  # noqa: E402
import prefs  # noqa: E402
from health import ValidationError  # noqa: E402
from test_kitchen import NOW, DbCase, JsonLLM, recipe  # noqa: E402
from test_server import make_settings  # noqa: E402


def same_four():
    """每次都返回同样 4 道菜的「模型」。"""
    return {"recipes": [
        recipe("烤土豆", [("土豆", "2个", False)], minutes=40, equipment=["烤箱"]),
        recipe("菠菜炒蛋", [("菠菜", "1把", False), ("鸡蛋", "2个", False), ("蚝油", "1勺", False)], minutes=10),
        recipe("土豆炖五花肉", [("土豆", "1个", False), ("五花肉", "200g", False), ("香菜", "少许", True)],
               minutes=45, equipment=["炒锅"]),
        recipe("蒸蛋", [("鸡蛋", "2个", False)], minutes=10, equipment=["锅"]),
    ]}


class PrefsStoreTests(DbCase):
    def test_new_user_gets_defaults_then_skip_is_remembered(self):
        got = prefs.get(self.conn, 1)
        self.assertEqual(got["status"], "new")
        self.assertEqual(got["prefs"]["equipment"], ["wok", "rice_cooker", "microwave"])
        prefs.save(self.conn, 1, {}, status="skipped", skipped=list(prefs.QUESTIONS))
        got = prefs.get(self.conn, 1)
        self.assertEqual((got["status"], got["prefs"]["household"]), ("skipped", "solo"))
        self.assertEqual(len(got["skipped"]), 8)
        # 之后单独回答某题：这题不再算跳过，其他照旧
        prefs.save(self.conn, 1, {"equipment": ["mini_pot"]})
        got = prefs.get(self.conn, 1)
        self.assertNotIn("equipment", got["skipped"])
        self.assertIn("skill", got["skipped"])
        self.assertEqual(got["status"], "skipped")

    def test_validation(self):
        for bad in ({"household": "dorm"}, {"minutes": 45}, {"equipment": []}, {"spice": "x"},
                    {"family_size": 30}):
            with self.assertRaises(ValidationError, msg=bad):
                prefs.save(self.conn, 1, bad)
        clean = prefs.normalize({"goals": ["nope"], "equipment": ["oven", "spaceship"], "unknown": 1})
        self.assertEqual(clean, {"goals": ["what_to_cook"], "equipment": ["oven"]})

    def test_every_option_code_survives_a_round_trip(self):
        # 回归：列表项曾被截到 10 个字符，rice_cooker（11 位）被截断后当成未知值悄悄丢掉
        all_codes = {"equipment": [e for e in prefs.EQUIPMENT if e != "mini_pot"],
                     "goals": list(prefs.GOALS), "family_flags": list(prefs.FAMILY_FLAGS)}
        prefs.save(self.conn, 1, all_codes, status="done", skipped=list(prefs.QUESTIONS))
        got = prefs.get(self.conn, 1)
        for key, codes in all_codes.items():
            self.assertEqual(got["prefs"][key], codes, key)
        self.assertEqual(got["skipped"], list(prefs.QUESTIONS))

    def test_servings_staples_and_caps(self):
        p = prefs.load(self.conn, 1)
        self.assertEqual(prefs.servings(p), 1)
        self.assertTrue(kitchen.is_staple("生抽", prefs.staple_names(p)))     # 勾「酱油」= 生抽、老抽也算
        self.assertFalse(kitchen.is_staple("蚝油", prefs.staple_names(p)))
        p.update(household="family", family_size=4, skill="beginner", goals=["learn"])
        self.assertEqual(prefs.servings(p), 4)
        self.assertEqual(prefs.difficulty_cap(p), 2)                           # 新手 1，想学做饭 +1


class DifferentAnswersTests(DbCase):
    """同一份模型输出，不同问卷答案 → 推荐结果不同。"""

    def setUp(self):
        super().setUp()
        for user in (1, 2):
            self.add({"name": "菠菜", "expires_on": "2026-11-18"}, "鸡蛋", "土豆", "五花肉", user=user)

    def run_for(self, user):
        llm = JsonLLM(same_four())
        return kitchen.recommend(self.conn, llm, "m", user, NOW), llm.calls[0]["messages"][1]["content"]

    def test_defaults_vs_custom_answers(self):
        # 用户 1：跳过问卷（默认：炒锅/电饭煲/微波炉，基础调料，30 分钟）
        prefs.save(self.conn, 1, {}, status="skipped")
        # 用户 2：有烤箱、常备蚝油、不吃香菜、不赶时间、最怕食材放坏
        prefs.save(self.conn, 2, {"equipment": ["wok", "oven"], "staples": ["盐", "油", "酱油", "蚝油"],
                                  "dislikes": ["香菜"], "minutes": 0, "goals": ["waste"]}, status="done")
        r1, prompt1 = self.run_for(1)
        r2, prompt2 = self.run_for(2)
        t1 = [r["title"] for r in r1["recipes"]]
        t2 = [r["title"] for r in r2["recipes"]]

        # 默认没有烤箱 → 烤土豆被剔除；菠菜炒蛋缺蚝油 → 排最后；炖五花肉超 30 分钟 → 排在蒸蛋后面并标注
        self.assertEqual(t1, ["蒸蛋", "土豆炖五花肉", "菠菜炒蛋"])
        self.assertEqual(r1["dropped"], [{"title": "烤土豆", "reason": "需要烤箱"}])
        by1 = {r["title"]: r for r in r1["recipes"]}
        self.assertEqual(by1["菠菜炒蛋"]["missing"], ["蚝油"])
        self.assertIn("比你设的 30 分钟久", by1["土豆炖五花肉"]["fit"][0])

        # 用户 2：蚝油是常备 → 菠菜炒蛋能马上做，又用掉临期菠菜 → 第一；香菜（可省略）被去掉并标注
        self.assertEqual(t2[0], "菠菜炒蛋")
        by2 = {r["title"]: r for r in r2["recipes"]}
        self.assertEqual(by2["菠菜炒蛋"]["missing"], [])
        self.assertEqual(by2["土豆炖五花肉"]["stripped"], ["香菜"])
        self.assertNotIn("香菜", [i["name"] for i in by2["土豆炖五花肉"]["ingredients"]])
        self.assertEqual(by2["土豆炖五花肉"]["fit"], [])
        self.assertEqual(r2["dropped"], [])
        self.assertNotEqual(t1, t2)

        self.assertIn("常备调料（不算缺料）：盐、油、酱油、醋、糖", prompt1)
        self.assertIn("蚝油", prompt2.split("常备调料（不算缺料）：")[1].splitlines()[0])
        self.assertIn("烤箱", prompt2)
        self.assertIn("不吃（绝对不能出现在用料里）：香菜", prompt2)

    def test_only_mini_pot_is_a_hard_filter(self):
        prefs.save(self.conn, 1, {"equipment": ["mini_pot"]}, status="done")
        result, prompt = self.run_for(1)
        self.assertEqual([r["title"] for r in result["recipes"]], ["蒸蛋", "菠菜炒蛋"])  # 后者缺蚝油
        reasons = {d["title"]: d["reason"] for d in result["dropped"]}
        self.assertEqual(reasons, {"烤土豆": "需要烤箱", "土豆炖五花肉": "需要炒锅"})
        self.assertIn("只有一个小电锅", prompt)

    def test_equipment_found_in_steps_even_if_not_declared(self):
        self.add("鸡翅")
        wings = recipe("空气炸锅鸡翅", [("鸡翅", "6个", False)])
        wings["steps"] = ["腌 10 分钟", "放进空气炸锅 200 度 15 分钟"]
        result = kitchen.recommend(self.conn, JsonLLM({"recipes": [wings, recipe("蒸蛋", [("鸡蛋", "2个", False)])]}),
                                   "m", 1, NOW)
        self.assertEqual(result["dropped"], [{"title": "空气炸锅鸡翅", "reason": "需要空气炸锅"}])

    def test_vegetarian_and_dislikes(self):
        prefs.save(self.conn, 1, {"diet": "vegetarian", "dislikes": ["葱"]}, status="done")
        llm = JsonLLM({"recipes": [
            recipe("洋葱炒蛋", [("洋葱", "1个", False), ("鸡蛋", "2个", False), ("葱花", "少许", True)]),
            recipe("菠菜虾皮汤", [("菠菜", "1把", False), ("虾皮", "1小把", True)]),
            recipe("五花肉炒土豆", [("五花肉", "100g", False), ("土豆", "1个", False)]),
        ]})
        result = kitchen.recommend(self.conn, llm, "m", 1, NOW)
        by = {r["title"]: r for r in result["recipes"]}
        self.assertEqual(set(by), {"洋葱炒蛋", "菠菜虾皮汤"})                  # 不吃葱 ≠ 不吃洋葱
        self.assertEqual(by["洋葱炒蛋"]["stripped"], ["葱花"])
        self.assertEqual(by["菠菜虾皮汤"]["stripped"], ["虾皮"])              # 素食：可省略的虾皮去掉
        self.assertEqual(result["dropped"][0]["reason"], "用到「五花肉」（素食（蛋奶素））")
        self.assertIn("饮食方式：素食（蛋奶素）", llm.calls[0]["messages"][1]["content"])

    def test_halal_and_allergy_groups(self):
        prefs.save(self.conn, 1, {"diet": "halal"}, status="done")
        self.conn.execute("INSERT INTO profiles (user_id, allergies) VALUES (1, '海鲜')")
        llm = JsonLLM({"recipes": [
            recipe("虾仁滑蛋", [("虾仁", "100g", False), ("鸡蛋", "2个", False)]),
            recipe("红烧土豆", [("土豆", "2个", False), ("料酒", "1勺", False)]),
            recipe("蒸蛋", [("鸡蛋", "2个", False)]),
        ]})
        result = kitchen.recommend(self.conn, llm, "m", 1, NOW)
        self.assertEqual([r["title"] for r in result["recipes"]], ["蒸蛋"])
        reasons = {d["title"]: d["reason"] for d in result["dropped"]}
        self.assertEqual(reasons["虾仁滑蛋"], "含过敏原「海鲜」")             # 「海鲜」展开成虾、蟹、贝……
        self.assertEqual(reasons["红烧土豆"], "用到「料酒」（清真）")

    def test_everything_filtered_says_why(self):
        prefs.save(self.conn, 1, {"equipment": ["mini_pot"]}, status="done")
        llm = JsonLLM({"recipes": [recipe("烤土豆", [("土豆", "2个", False)], equipment=["烤箱"])]})
        with self.assertRaisesRegex(ValidationError, "都不符合你的设置（需要烤箱）"):
            kitchen.recommend(self.conn, llm, "m", 1, NOW)

    def test_household_and_skill_change_the_prompt(self):
        prefs.save(self.conn, 1, {"household": "family", "family_size": 4, "family_flags": ["elderly"],
                                  "skill": "beginner", "spice": "none"}, status="done")
        _, prompt = self.run_for(1)
        for text in ("做 4 人份", "两菜一汤", "少盐少油", "用括号解释", "不吃辣"):
            self.assertIn(text, prompt)
        _, prompt2 = self.run_for(2)
        self.assertIn("做 1 人份", prompt2)
        self.assertNotIn("两菜一汤", prompt2)

    def test_staples_change_is_applied_when_reopening_a_recipe(self):
        result, _ = self.run_for(1)
        stir = next(r for r in result["recipes"] if r["title"] == "菠菜炒蛋")
        self.assertEqual(stir["missing"], ["蚝油"])
        prefs.save(self.conn, 1, {"staples": ["盐", "油", "蚝油"]})
        again = kitchen.recipe_payload(self.conn, 1, stir["id"], NOW.date())
        self.assertEqual(again["missing"], [])


class RankByGoalTests(unittest.TestCase):
    """Q7 改变排序规则：三道都能马上做，差别只在临期、缺料、是否符合时间。"""

    def make(self, title, expiring=0, missing=0, fit=False, minutes=10):
        return {"title": title, "missing": ["x"] * missing, "uses_expiring": ["e"] * expiring, "uses_count": 1,
                "minutes": minutes, "fit": ["超时"] if fit else []}

    def order(self, goals, *recipes):
        return [r["title"] for r in sorted(recipes, key=lambda r: kitchen.rank_key(r, goals))]

    def test_waste_puts_expiring_before_time_fit(self):
        slow_saver = self.make("慢但用掉临期", expiring=2, fit=True, minutes=50)
        quick = self.make("快手菜")
        self.assertEqual(self.order(["what_to_cook"], slow_saver, quick), ["快手菜", "慢但用掉临期"])
        self.assertEqual(self.order(["waste"], slow_saver, quick), ["慢但用掉临期", "快手菜"])

    def test_save_money_puts_fewer_purchases_first(self):
        a = self.make("缺 2 样但用临期", expiring=1, missing=2)
        b = self.make("只缺 1 样", missing=1)
        self.assertEqual(self.order([], a, b), ["缺 2 样但用临期", "只缺 1 样"])
        self.assertEqual(self.order(["save_money"], a, b), ["只缺 1 样", "缺 2 样但用临期"])

    def test_can_cook_now_always_first(self):
        ready = self.make("能马上做", fit=True, minutes=60)
        needs = self.make("要去买", expiring=3, missing=1)
        for goals in ([], ["waste"], ["save_money"]):
            self.assertEqual(self.order(goals, needs, ready)[0], "能马上做")


class HealthyGoalTests(DbCase):
    def test_kcal_over_budget_is_flagged_only_when_healthy_chosen(self):
        self.add("鸡蛋")
        self.conn.execute("INSERT INTO profiles (user_id, sex, birth_year, height_cm, weight_kg, activity_level, goal) "
                          "VALUES (1, 'female', 2000, 160, 55, 'light', 'maintain')")
        big = recipe("芝士焗蛋", [("鸡蛋", "3个", False)], kcal=5000)
        r = kitchen.recommend(self.conn, JsonLLM({"recipes": [big]}), "m", 1, NOW)
        self.assertEqual(r["recipes"][0]["fit"], [])
        prefs.save(self.conn, 1, {"goals": ["healthy"]}, status="done")
        r = kitchen.recommend(self.conn, JsonLLM({"recipes": [dict(big)]}), "m", 1, datetime(2026, 11, 17, 19))
        self.assertIn("超过今天还能吃的", r["recipes"][0]["fit"][0])


class PrefsApiTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(make_settings(self.tmp.name))
        self.client = self.app.test_client()
        r = self.client.post("/api/auth/register", json={"username": "cook2", "password": "password-123"})
        self.assertEqual(r.get_json()["user"]["prefs_status"], "new")

    def tearDown(self):
        self.tmp.cleanup()

    def test_questionnaire_round_trip(self):
        self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["prefs_status"], "new")
        r = self.client.put("/api/preferences", json={
            "prefs": {"household": "two", "goals": ["healthy", "waste"]}, "allergies": ["花生", "海鲜"],
            "profile": {"height_cm": 170, "weight_kg": 60, "goal": "lose"},
            "status": "done", "skipped": ["staples"]})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual((data["status"], data["servings"], data["health_in_nav"]), ("done", 2, True))
        self.assertEqual(data["allergies"], ["花生", "海鲜"])
        self.assertEqual(data["skipped"], ["staples"])
        profile = self.client.get("/api/profile").get_json()["profile"]
        self.assertEqual((profile["allergies"], profile["goal"], profile["height_cm"]), ("花生、海鲜", "lose", 170))
        self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["prefs_status"], "done")

    def test_skip_all_and_bad_input(self):
        r = self.client.put("/api/preferences", json={"status": "skipped", "skipped": list(prefs.QUESTIONS)})
        self.assertEqual(r.get_json()["status"], "skipped")
        self.assertFalse(r.get_json()["health_in_nav"])
        self.assertEqual(self.client.put("/api/preferences", json={"prefs": {"minutes": 999}}).status_code, 400)
        # 失败的请求不能把档案改了一半
        self.client.put("/api/preferences", json={"allergies": ["花生"], "prefs": {"minutes": 999}})
        self.assertEqual(self.client.get("/api/profile").get_json()["profile"]["allergies"], "")

    def test_agent_prompt_includes_preferences(self):
        from agent.prompts import build_system_prompt
        from db import connect
        self.client.put("/api/preferences", json={"prefs": {"equipment": ["mini_pot"], "dislikes": ["香菜"]},
                                                  "status": "done"})
        conn = connect(self.app.config["SETTINGS"].database_path)
        try:
            text = build_system_prompt(conn, 1, NOW)
        finally:
            conn.close()
        self.assertIn("厨具：小电锅", text)
        self.assertIn("不吃：香菜", text)

    def test_requires_login(self):
        self.client.post("/api/auth/logout", json={})
        self.assertEqual(self.client.get("/api/preferences").status_code, 401)


if __name__ == "__main__":
    unittest.main()
