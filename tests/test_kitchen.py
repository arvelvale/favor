"""厨房闭环回归测试：库存、保质期估算、AI 菜谱校验与排序、做好了（扣库存 + 记一餐）、越权隔离。

用假模型客户端（非流式 JSON），不访问网络。运行：python -m unittest discover -s tests -v
"""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

import kitchen  # noqa: E402
from db import connect, init_db  # noqa: E402
from health import ValidationError  # noqa: E402
from test_server import make_settings  # noqa: E402

TODAY = date(2026, 11, 17)
NOW = datetime(2026, 11, 17, 18, 30)


class JsonLLM:
    """非流式假模型：按顺序返回预设 JSON；记录每次收到的 messages。"""

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return NS(choices=[NS(message=NS(content=text))])


def recipe(title, ingredients, minutes=15, kcal=450, **extra):
    return {"title": title, "summary": "", "minutes": minutes, "difficulty": 1, "servings": 1,
            "kcal_per_serving": kcal, "steps": ["备料", "下锅", "出锅"],
            "ingredients": [{"name": n, "amount": a, "optional": o} for n, a, o in ingredients], **extra}


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "k.sqlite3"
        init_db(path)
        self.conn = connect(path)
        for name in ("u1", "u2"):
            self.conn.execute("INSERT INTO users (username, password_hash) VALUES (?, 'x')", (name,))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def add(self, *items, user=1):
        return kitchen.add_items(self.conn, user, [i if isinstance(i, dict) else {"name": i} for i in items], TODAY)


class ShelfLifeTests(unittest.TestCase):
    def days(self, name, storage=None):
        cat = kitchen.guess_category(name)
        st = storage or kitchen.default_storage(name, cat)
        e = kitchen.estimate_expiry(name, cat, st, TODAY)
        return None if e is None else (e - TODAY).days

    def test_specific_items_override_category(self):
        self.assertEqual(self.days("菠菜"), 3)      # 叶菜比一般蔬菜短
        self.assertEqual(self.days("洋葱"), 21)     # 耐放蔬菜
        self.assertEqual(self.days("鸡蛋"), 30)
        self.assertEqual(self.days("五花肉"), 2)
        self.assertEqual(self.days("五花肉", "freezer"), 90)

    def test_default_storage_by_name(self):
        self.assertEqual(self.days("米饭"), 2)      # 剩饭默认冷藏，不是常温不提醒
        self.assertEqual(self.days("饺子"), 90)     # 默认冷冻

    def test_condiments_and_dry_staples_not_tracked(self):
        self.assertIsNone(self.days("酱油"))
        self.assertIsNone(self.days("大米"))

    def test_name_matching(self):
        self.assertTrue(kitchen.names_match("西红柿", "番茄"))
        self.assertTrue(kitchen.names_match("葱花", "葱"))
        self.assertTrue(kitchen.names_match("猪肉末", "肉末"))
        self.assertFalse(kitchen.names_match("蛋", "鸡蛋"))     # 单字不做包含匹配，避免误判
        self.assertTrue(kitchen.is_staple("生抽"))
        self.assertFalse(kitchen.is_staple("蚝油"))


class PantryTests(DbCase):
    def test_add_merges_same_item_and_sums_quantity(self):
        self.add({"name": "鸡蛋", "quantity": 6, "unit": "个"})
        merged = self.add({"name": "鸡蛋", "quantity": 4, "unit": "个"})[0]
        self.assertEqual(merged["quantity"], 10)
        self.assertEqual(len(kitchen.list_pantry(self.conn, 1, TODAY)), 1)

    def test_quantity_is_optional(self):
        item = self.add("番茄")[0]
        self.assertIsNone(item["quantity"])
        self.assertTrue(item["expires_estimated"])
        self.assertEqual(item["days_left"], 5)

    def test_list_sorted_by_expiry_nulls_last(self):
        self.add("酱油", "洋葱", "菠菜", "五花肉")
        names = [i["name"] for i in kitchen.list_pantry(self.conn, 1, TODAY)]
        self.assertEqual(names, ["五花肉", "菠菜", "洋葱", "酱油"])

    def test_moving_to_freezer_reestimates_only_estimated_dates(self):
        meat = self.add("五花肉")[0]
        moved = kitchen.update_item(self.conn, 1, meat["id"], {"storage": "freezer"}, TODAY)
        self.assertEqual(moved["days_left"], 90)
        fish = self.add({"name": "鱼", "expires_on": "2026-11-20"})[0]
        moved = kitchen.update_item(self.conn, 1, fish["id"], {"storage": "freezer"}, TODAY)
        self.assertEqual(moved["expires_on"], "2026-11-20")   # 用户填的日期不被覆盖
        self.assertFalse(moved["expires_estimated"])

    def test_user_isolation(self):
        item = self.add("番茄", user=1)[0]
        self.assertIsNone(kitchen.update_item(self.conn, 2, item["id"], {"quantity": 1}, TODAY))
        self.assertFalse(kitchen.remove_item(self.conn, 2, item["id"]))
        self.assertEqual(kitchen.list_pantry(self.conn, 2, TODAY), [])

    def test_parse_falls_back_without_model(self):
        items = kitchen.parse_text(None, None, "冰箱里有鸡蛋、番茄，还有半颗洋葱")
        self.assertEqual([i["name"] for i in items][:2], ["鸡蛋", "番茄"])

    def test_quantity_split_from_name(self):
        self.assertEqual(kitchen.split_quantity("6个鸡蛋"), (6.0, "个", "鸡蛋"))
        self.assertEqual(kitchen.split_quantity("两盒豆腐"), (2, "盒", "豆腐"))
        self.assertEqual(kitchen.split_quantity("半颗洋葱"), (0.5, "颗", "洋葱"))
        for name in ("五花肉", "三文鱼", "八角", "四季豆", "番茄"):   # 中文数字后面不是单位，不拆
            self.assertEqual(kitchen.split_quantity(name), (None, "", name))
        item = self.add({"name": "6个鸡蛋"})[0]
        self.assertEqual((item["name"], item["quantity"], item["unit"]), ("鸡蛋", 6, "个"))
        self.assertEqual(item["days_left"], 30)                     # 拆出名称后保质期也按鸡蛋算

    def test_parse_uses_model_and_survives_bad_json(self):
        llm = JsonLLM({"items": [{"name": "洋葱", "quantity": 0.5, "unit": "颗"}]})
        self.assertEqual(kitchen.parse_text(llm, "m", "半颗洋葱")[0]["quantity"], 0.5)
        self.assertEqual(kitchen.parse_text(JsonLLM("不是 JSON"), "m", "鸡蛋、番茄")[0]["name"], "鸡蛋")


class RecommendTests(DbCase):
    def test_server_computes_missing_and_ranking_rule(self):
        self.add({"name": "菠菜", "expires_on": "2026-11-18"}, "鸡蛋", "洋葱", "五花肉")
        llm = JsonLLM({"recipes": [
            recipe("洋葱炒蛋", [("洋葱", "1个", False), ("鸡蛋", "2个", False), ("盐", "少许", False)]),
            recipe("回锅肉", [("五花肉", "200g", False), ("青蒜", "2根", False), ("豆瓣酱", "1勺", False)], minutes=30),
            recipe("菠菜蛋汤", [("菠菜", "1把", False), ("鸡蛋", "1个", False), ("香油", "几滴", True)], minutes=10),
        ]})
        result = kitchen.recommend(self.conn, llm, "m", 1, NOW)
        titles = [r["title"] for r in result["recipes"]]
        # 规则：能马上做的优先；同样能做时用到临期食材的优先；
        # 回锅肉虽然用掉临期五花肉，但缺 2 样料，排最后
        self.assertEqual(titles, ["菠菜蛋汤", "洋葱炒蛋", "回锅肉"])
        soup, pork = result["recipes"][0], result["recipes"][2]
        self.assertEqual(soup["uses_expiring"], ["菠菜"])
        self.assertEqual(soup["missing"], [])                      # 香油可省略，不算缺料
        self.assertEqual(sorted(pork["missing"]), ["豆瓣酱", "青蒜"])  # 模型没说缺，服务端照样算出来
        statuses = {i["name"]: i["status"] for i in result["recipes"][1]["ingredients"]}
        self.assertEqual(statuses["盐"], "staple")
        prompt = llm.calls[0]["messages"][1]["content"]
        self.assertIn("【临期】五花肉", prompt)

    def test_allergen_recipes_dropped_in_code(self):
        self.add("鸡蛋", "虾")
        self.conn.execute("INSERT INTO profiles (user_id, allergies) VALUES (1, '虾、花生')")
        llm = JsonLLM({"recipes": [recipe("虾仁炒蛋", [("虾仁", "100g", False), ("鸡蛋", "2个", False)]),
                                   recipe("蒸蛋", [("鸡蛋", "2个", False)])]})
        result = kitchen.recommend(self.conn, llm, "m", 1, NOW)
        self.assertEqual([r["title"] for r in result["recipes"]], ["蒸蛋"])
        self.assertEqual(result["dropped"][0]["reason"], "含过敏原「虾」")
        self.assertIn("过敏，绝对不能用：虾、花生", llm.calls[0]["messages"][1]["content"])

    def test_empty_pantry_and_no_model_are_friendly_errors(self):
        with self.assertRaisesRegex(ValidationError, "先加几样"):
            kitchen.recommend(self.conn, JsonLLM(), "m", 1, NOW)
        with self.assertRaisesRegex(ValidationError, "没有配置模型"):
            kitchen.recommend(self.conn, None, None, 1, NOW)

    def test_daily_limit(self):
        self.add("鸡蛋")
        payload = {"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}
        kitchen.recommend(self.conn, JsonLLM(payload), "m", 1, NOW, daily_limit=1)
        with self.assertRaisesRegex(ValidationError, "明天再来"):
            kitchen.recommend(self.conn, JsonLLM(payload), "m", 1, NOW, daily_limit=1)

    def test_latest_batch_marks_stale_after_pantry_change(self):
        self.add("鸡蛋")
        kitchen.recommend(self.conn, JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)])]}), "m", 1, NOW)
        self.assertFalse(kitchen.latest_batch(self.conn, 1, TODAY)["stale"])
        self.conn.execute("UPDATE pantry_items SET quantity=3")
        self.assertTrue(kitchen.latest_batch(self.conn, 1, TODAY)["stale"])


class CookTests(DbCase):
    def setUp(self):
        super().setUp()
        self.add({"name": "鸡蛋", "quantity": 6, "unit": "个"}, "番茄", "葱")
        llm = JsonLLM({"recipes": [recipe("番茄炒蛋", [("番茄", "2个", False), ("鸡蛋", "2个", False),
                                                      ("葱", "1根", True)], kcal=380)]})
        self.recipe_id = kitchen.recommend(self.conn, llm, "m", 1, NOW)["recipes"][0]["id"]

    def pantry(self):
        return {i["name"]: i for i in kitchen.list_pantry(self.conn, 1, TODAY)}

    def test_preview_suggestions(self):
        usage = {u["name"]: u for u in kitchen.cook_preview(self.conn, 1, self.recipe_id, NOW)["usage"]}
        self.assertEqual(usage["鸡蛋"]["remaining"], 4)    # 6 个 - 2 个，按数量扣
        self.assertFalse(usage["鸡蛋"]["used_up"])
        self.assertTrue(usage["番茄"]["used_up"])          # 没填数量的蔬菜默认用完
        self.assertFalse(usage["葱"]["used_up"])           # 葱姜蒜默认还有剩

    def test_cook_deducts_pantry_and_logs_meal(self):
        result = kitchen.cook(self.conn, 1, self.recipe_id, NOW, usage=[], eaten_servings=1)
        pantry = self.pantry()
        self.assertEqual(pantry["鸡蛋"]["quantity"], 4)
        self.assertNotIn("番茄", pantry)
        self.assertIn("葱", pantry)
        record = self.conn.execute("SELECT * FROM records WHERE id=?", (result["record"]["id"],)).fetchone()
        data = json.loads(record["data"])
        self.assertEqual(record["source"], "cook")
        self.assertEqual(data["meal_type"], "dinner")      # 18:30 → 晚餐
        self.assertEqual(data["calories"], 380)
        log = self.conn.execute("SELECT * FROM cook_logs").fetchone()
        self.assertEqual(log["record_id"], result["record"]["id"])

    def test_user_overrides_and_servings(self):
        tomato = self.pantry()["番茄"]["id"]
        kitchen.cook(self.conn, 1, self.recipe_id, NOW, usage=[{"item_id": tomato, "used_up": False}],
                     eaten_servings=2)
        self.assertIn("番茄", self.pantry())                # 用户说还有剩，就不扣
        data = json.loads(self.conn.execute("SELECT data FROM records").fetchone()["data"])
        self.assertEqual(data["calories"], 760)            # 吃了 2 份

    def test_says_leftover_when_count_hits_zero(self):
        """按数量算已用光但用户说还有剩：数量改为未知，不存 0。"""
        eggs = self.pantry()["鸡蛋"]["id"]
        self.conn.execute("UPDATE pantry_items SET quantity=2 WHERE id=?", (eggs,))
        kitchen.cook(self.conn, 1, self.recipe_id, NOW, usage=[{"item_id": eggs, "used_up": False}])
        self.assertIsNone(self.pantry()["鸡蛋"]["quantity"])

    def test_macros_carried_into_meal_only_when_given(self):
        data = json.loads(self.conn.execute("SELECT data FROM recipes WHERE id=?", (self.recipe_id,)).fetchone()["data"])
        self.assertIsNone(data["macros"])                     # 这道菜模型没给营养素
        kitchen.cook(self.conn, 1, self.recipe_id, NOW, usage=[])
        meal = json.loads(self.conn.execute("SELECT data FROM records").fetchone()["data"])
        self.assertEqual(meal["protein"], 0)                  # 不编造
        llm = JsonLLM({"recipes": [recipe("蒸蛋", [("鸡蛋", "2个", False)], kcal=200,
                                         protein_g=13, carbs_g=2, fat_g=10)]})
        rid = kitchen.recommend(self.conn, llm, "m", 1, NOW)["recipes"][0]["id"]
        kitchen.cook(self.conn, 1, rid, NOW, usage=[], eaten_servings=2)
        meal = json.loads(self.conn.execute("SELECT data FROM records ORDER BY id DESC").fetchone()["data"])
        self.assertEqual((meal["protein"], meal["carbs"], meal["fat"], meal["calories"]), (26, 4, 20, 400))

    def test_no_meal_when_not_eaten_and_isolation(self):
        result = kitchen.cook(self.conn, 1, self.recipe_id, NOW, usage=[], eaten_servings=0)
        self.assertIsNone(result["record"])
        self.assertIsNone(kitchen.cook(self.conn, 2, self.recipe_id, NOW, usage=[]))
        self.assertIsNone(kitchen.recipe_payload(self.conn, 2, self.recipe_id, TODAY))


class ApiTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.llm = JsonLLM()
        app = create_app(make_settings(self.tmp.name, LLM_API_KEY="x" * 20), llm_client=self.llm)
        self.client = app.test_client()
        self.client.post("/api/auth/register", json={"username": "cook1", "password": "password-123"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_loop_over_http(self):
        r = self.client.post("/api/pantry", json={"items": [{"name": "鸡蛋", "quantity": 3, "unit": "个"}, {"name": "番茄"}]})
        self.assertEqual(r.status_code, 201)
        self.llm.payloads.append({"recipes": [recipe("番茄炒蛋", [("番茄", "2个", False), ("鸡蛋", "2个", False)])]})
        rec = self.client.post("/api/recipes/recommend", json={}).get_json()["recipes"][0]
        self.assertEqual(rec["missing"], [])
        self.assertEqual(self.client.get("/api/recipes/latest").get_json()["recipes"][0]["id"], rec["id"])
        preview = self.client.get(f"/api/recipes/{rec['id']}/cook").get_json()
        self.assertEqual(len(preview["usage"]), 2)
        done = self.client.post(f"/api/recipes/{rec['id']}/cook", json={"usage": [], "eaten_servings": 1}).get_json()
        self.assertIn("番茄炒蛋", done["record"]["text"])
        items = {i["name"]: i for i in self.client.get("/api/pantry").get_json()["items"]}
        self.assertEqual(items["鸡蛋"]["quantity"], 1)
        self.assertTrue(self.client.get("/api/recipes/latest").get_json()["stale"])
        self.client.post(f"/api/recipes/{rec['id']}/save", json={"saved": True})
        saved = self.client.get("/api/recipes").get_json()
        self.assertEqual(saved["saved"][0]["id"], rec["id"])
        self.assertEqual(saved["cooked"][0]["title"], "番茄炒蛋")

    def test_model_garbage_returns_502_not_500(self):
        self.client.post("/api/pantry", json={"items": [{"name": "鸡蛋"}]})
        self.llm.payloads.append("模型抽风了")
        r = self.client.post("/api/recipes/recommend", json={})
        self.assertEqual(r.status_code, 502)

    def test_parse_preview_does_not_write(self):
        self.llm.payloads.append({"items": [{"name": "排骨", "quantity": 2, "unit": "斤"}]})
        items = self.client.post("/api/pantry/parse", json={"text": "买了两斤排骨"}).get_json()["items"]
        self.assertEqual(items[0]["category"], "meat")
        self.assertEqual(self.client.get("/api/pantry").get_json()["items"], [])

    def test_agent_adds_pantry_then_recommends(self):
        """对话链路：模型调 add_pantry_items → recommend_recipes（工具内部再走一次非流式 JSON），产出卡片。"""
        from test_server import chunk, tool_chunk

        class MixedLLM:
            def __init__(self, streams, jsons):
                self.streams, self.jsons = list(streams), list(jsons)
                self.chat = NS(completions=NS(create=self.create))

            def create(self, **kw):
                if kw.get("stream"):
                    return iter(self.streams.pop(0))
                return NS(choices=[NS(message=NS(content=json.dumps(self.jsons.pop(0), ensure_ascii=False)))])

        from app import create_app
        llm = MixedLLM(
            streams=[
                [*tool_chunk(0, "a1", "add_pantry_items", json.dumps({"items": [{"name": "鸡蛋"}, {"name": "番茄"}]}, ensure_ascii=False))],
                [*tool_chunk(0, "r1", "recommend_recipes", "{}")],
                [chunk("推荐你做番茄炒蛋。")],
            ],
            jsons=[{"recipes": [recipe("番茄炒蛋", [("番茄", "2个", False), ("鸡蛋", "2个", False)])]}])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        client = create_app(make_settings(tmp.name, LLM_API_KEY="x" * 20), llm_client=llm).test_client()
        client.post("/api/auth/register", json={"username": "agent1", "password": "password-123"})
        conv = client.post("/api/conversations", json={}).get_json()["conversation"]
        raw = client.post(f"/api/conversations/{conv['id']}/chat", json={"message": "冰箱有鸡蛋番茄，吃啥"}).get_data(as_text=True)
        events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
        cards = [e["card"] for e in events if e["type"] == "card"]
        self.assertEqual([c["type"] for c in cards], ["pantry", "recipes"])
        self.assertEqual(cards[1]["recipes"][0]["title"], "番茄炒蛋")
        self.assertEqual(cards[1]["recipes"][0]["missing"], [])
        self.assertEqual(len(client.get("/api/pantry").get_json()["items"]), 2)

    def test_requires_login(self):
        self.client.post("/api/auth/logout", json={})
        self.assertEqual(self.client.get("/api/pantry").status_code, 401)


if __name__ == "__main__":
    unittest.main()
