"""厨房领域逻辑：冰箱库存、保质期估算、AI 菜谱推荐与校验、做菜闭环。

REST 接口与 agent 工具共用这一层。原则：
- 库存数量可选，不强制精确；到期日没填就按分类估算并标注「估算」
- 菜谱由 AI 生成，但「缺什么、用到哪些临期食材、有没有过敏原」一律由服务端对照库存计算，不信任模型自报
- 推荐排序是显式规则（见 rank_key），写进测试
"""
import json
import re
import uuid
from datetime import date, datetime, timedelta

import health
import prefs as prefs_mod
import taste
from health import ValidationError

# ---------------------------------------------------------------- 分类与保质期

CATEGORIES = {
    "veg": "蔬菜", "fruit": "水果", "meat": "肉禽", "seafood": "水产", "egg_dairy": "蛋奶",
    "tofu": "豆制品", "staple": "主食", "condiment": "调料", "other": "其他",
}
STORAGES = {"fridge": "冷藏", "freezer": "冷冻", "pantry": "常温"}
STATUSES = ("active", "used", "discarded")

# 分类默认存放位置
DEFAULT_STORAGE = {"veg": "fridge", "fruit": "fridge", "meat": "fridge", "seafood": "fridge",
                   "egg_dairy": "fridge", "tofu": "fridge", "staple": "pantry", "condiment": "pantry",
                   "other": "fridge"}

# 分类 × 存放位置 的默认保质天数（家庭常见经验值，偏保守）。None 表示不估算（如调料、米面）。
SHELF_DAYS = {
    "veg": {"fridge": 5, "freezer": 60, "pantry": 3},
    "fruit": {"fridge": 7, "freezer": 90, "pantry": 4},
    "meat": {"fridge": 2, "freezer": 90, "pantry": 1},
    "seafood": {"fridge": 1, "freezer": 90, "pantry": 1},
    "egg_dairy": {"fridge": 10, "freezer": 30, "pantry": 3},
    "tofu": {"fridge": 3, "freezer": 30, "pantry": 1},
    "staple": {"fridge": 5, "freezer": 60, "pantry": None},
    "condiment": {"fridge": None, "freezer": None, "pantry": None},
    "other": {"fridge": 5, "freezer": 60, "pantry": 7},
}

# 具体食材的覆盖值（比分类更准的常见情况）：关键词 → (分类, {存放: 天数})
ITEM_RULES: list[tuple[tuple[str, ...], str, dict]] = [
    (("菠菜", "生菜", "小白菜", "青菜", "油麦菜", "空心菜", "韭菜", "香菜", "豆芽", "菜心", "茼蒿"), "veg",
     {"fridge": 3, "pantry": 1}),
    (("土豆", "洋葱", "胡萝卜", "南瓜", "红薯", "山药", "冬瓜"), "veg", {"fridge": 21, "pantry": 14}),
    (("番茄", "西红柿", "黄瓜", "茄子", "青椒", "辣椒", "西兰花", "花菜", "包菜", "卷心菜", "白菜", "芹菜",
      "蘑菇", "香菇", "金针菇", "豆角", "四季豆", "莴笋", "丝瓜", "苦瓜", "玉米", "葱", "姜", "蒜", "大蒜"), "veg", {}),
    (("鸡蛋", "鸭蛋", "鹌鹑蛋"), "egg_dairy", {"fridge": 30, "pantry": 10}),
    (("牛奶", "鲜奶"), "egg_dairy", {"fridge": 5}),
    (("酸奶",), "egg_dairy", {"fridge": 14}),
    (("奶酪", "芝士", "黄油"), "egg_dairy", {"fridge": 30}),
    (("豆腐", "豆皮", "腐竹", "千张", "豆干"), "tofu", {}),
    (("鸡胸", "鸡腿", "鸡翅", "鸡肉", "猪肉", "五花肉", "排骨", "里脊", "肉末", "肉馅", "牛肉", "羊肉", "鸭",
      "培根", "火腿", "香肠", "午餐肉"), "meat", {}),
    (("培根", "火腿", "香肠", "午餐肉"), "meat", {"fridge": 7}),
    (("虾", "鱼", "蟹", "贝", "鱿鱼", "蛤蜊", "带鱼", "三文鱼"), "seafood", {}),
    (("面条", "挂面", "大米", "米", "面粉", "馒头", "面包", "饺子", "汤圆", "年糕", "意面", "方便面", "粉丝", "米粉"),
     "staple", {"fridge": 5, "freezer": 60}),
    (("面包",), "staple", {"pantry": 3, "fridge": 7}),
    (("米饭", "剩饭"), "staple", {"fridge": 2}),
    (("饺子", "汤圆", "馄饨"), "staple", {"freezer": 90}),
    (("苹果", "香蕉", "橙", "梨", "葡萄", "草莓", "西瓜", "桃", "芒果", "柠檬", "猕猴桃", "蓝莓"), "fruit", {}),
    (("香蕉",), "fruit", {"pantry": 4, "fridge": 5}),
    (("盐", "糖", "酱油", "生抽", "老抽", "醋", "料酒", "蚝油", "豆瓣酱", "番茄酱", "淀粉", "胡椒", "花椒", "八角",
      "香油", "芝麻油", "食用油", "辣椒酱", "味精", "鸡精", "咖喱"), "condiment", {}),
]

# 具体食材的默认存放位置（比分类默认更贴近实际）
STORAGE_BY_NAME = {"米饭": "fridge", "剩饭": "fridge", "饺子": "freezer", "汤圆": "freezer", "馄饨": "freezer",
                   "冻": "freezer"}

# 常见同义名：统一成一个写法，方便匹配库存与菜谱用料
SYNONYMS = {"西红柿": "番茄", "马铃薯": "土豆", "洋芋": "土豆", "鸡子": "鸡蛋", "卷心菜": "包菜",
            "圆白菜": "包菜", "花椰菜": "花菜", "青红椒": "青椒", "大蒜": "蒜", "蒜头": "蒜", "生姜": "姜",
            "小葱": "葱", "大葱": "葱", "香葱": "葱", "葱花": "葱", "蒜末": "蒜", "姜丝": "姜", "姜片": "姜",
            "鸡胸肉": "鸡胸", "猪肉末": "肉末", "肉馅": "肉末", "白米饭": "米饭", "剩米饭": "米饭"}

# 默认常备调料：菜谱里出现这些不算「缺料」，做完也不扣库存。第 2 期起由问卷决定。
DEFAULT_STAPLES = ("盐", "油", "食用油", "植物油", "花生油", "酱油", "生抽", "老抽", "醋", "糖", "白糖",
                   "水", "清水", "开水", "温水")

# 做完菜后默认「还有剩」的分类：一次通常用不完（其余分类默认「用完了」，用户可在确认时改）
USUALLY_LEFTOVER = {"egg_dairy", "staple", "condiment"}
LEFTOVER_NAMES = ("葱", "姜", "蒜", "辣椒", "香菜")

EXPIRING_DAYS = 2  # 剩余天数 ≤ 2 视为「临期」，推荐时优先消耗


def normalize_name(name: str) -> str:
    text = re.sub(r"[（(].*?[)）]", "", str(name or "")).strip().lower()
    text = re.sub(r"\s+", "", text)
    return SYNONYMS.get(text, text)


def _rule_for(name: str):
    key = normalize_name(name)
    found_cat, overrides = None, {}
    for words, cat, days in ITEM_RULES:
        if any(w in key for w in words):
            if found_cat is None:
                found_cat = cat
            if cat == found_cat:
                overrides.update(days)  # 越靠后的规则越具体，覆盖前面的
    return found_cat, overrides


def guess_category(name: str) -> str:
    return _rule_for(name)[0] or "other"


def default_storage(name: str, category: str) -> str:
    key = normalize_name(name)
    return next((st for word, st in STORAGE_BY_NAME.items() if word in key), DEFAULT_STORAGE[category])


def estimate_expiry(name: str, category: str, storage: str, today: date) -> date | None:
    """按「具体食材覆盖值 → 分类默认值」估算到期日；调料、常温米面等返回 None（不提醒）。"""
    _, overrides = _rule_for(name)
    days = overrides.get(storage, SHELF_DAYS.get(category, SHELF_DAYS["other"]).get(storage))
    return today + timedelta(days=days) if days is not None else None


def is_staple(name: str, staples=DEFAULT_STAPLES) -> bool:
    key = normalize_name(name)
    return key in {normalize_name(s) for s in staples}


def names_match(a: str, b: str) -> bool:
    """菜谱用料与库存名是否指同一样东西：统一写法后相等，或一方（≥2 字）包含另一方。"""
    x, y = normalize_name(a), normalize_name(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = (x, y) if len(x) <= len(y) else (y, x)
    return len(short) >= 2 and short in long_


# ---------------------------------------------------------------- 库存

def _days_left(expires_on: str | None, today: date):
    if not expires_on:
        return None
    return (date.fromisoformat(expires_on) - today).days


def item_to_dict(row, today: date) -> dict:
    item = dict(row)
    item["days_left"] = _days_left(item["expires_on"], today)
    item["expires_estimated"] = bool(item["expires_estimated"])
    item["category_label"] = CATEGORIES.get(item["category"], "其他")
    item["storage_label"] = STORAGES.get(item["storage"], "冷藏")
    return item


def describe_item(item: dict) -> str:
    qty = ""
    if item.get("quantity") is not None:
        q = item["quantity"]
        qty = f" {int(q) if float(q).is_integer() else q}{item.get('unit') or ''}"
    left = item.get("days_left")
    when = "" if left is None else ("（已过期）" if left < 0 else "（今天到期）" if left == 0 else f"（还剩 {left} 天）")
    return f"{item['name']}{qty}{when}"


def list_pantry(conn, user_id: int, today: date) -> list[dict]:
    """在用的库存，按到期日从近到远排（没有到期日的排最后）。"""
    rows = conn.execute(
        "SELECT * FROM pantry_items WHERE user_id=? AND status='active' "
        "ORDER BY expires_on IS NULL, expires_on, id", (user_id,)).fetchall()
    return [item_to_dict(r, today) for r in rows]


def get_item(conn, user_id: int, item_id: int, today: date) -> dict | None:
    row = conn.execute("SELECT * FROM pantry_items WHERE id=? AND user_id=?", (item_id, user_id)).fetchone()
    return item_to_dict(row, today) if row else None


CN_NUM = {"半": 0.5, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
UNITS = ("个", "颗", "只", "根", "把", "斤", "克", "g", "kg", "盒", "袋", "瓶", "包", "块", "条", "片", "罐", "升",
         "ml", "L", "枚", "棵", "颗", "串", "碗", "杯", "盘", "份", "听", "提", "打")
_QTY_RE = re.compile(r"^(\d+(?:\.\d+)?|[半一二两三四五六七八九十])\s*(" + "|".join(sorted(UNITS, key=len, reverse=True))
                     + r")?\s*(.+)$", re.I)


def split_quantity(text: str):
    """「6个鸡蛋」「半颗洋葱」→ (数量, 单位, 名称)。
    中文数字必须跟单位才拆，避免把「五花肉」「三文鱼」「八角」拆成数字 + 名称。拆不了返回 (None, '', 原文)。"""
    text = str(text or "").strip()
    m = _QTY_RE.match(text)
    if not m or not m.group(3).strip():
        return None, "", text
    num, unit, name = m.group(1), m.group(2) or "", m.group(3).strip()
    if num in CN_NUM:
        if not unit:
            return None, "", text
        return CN_NUM[num], unit, name
    return float(num), unit, name


def _clean_item(raw: dict, today: date) -> dict:
    if not isinstance(raw, dict):
        raise ValidationError("食材格式不对")
    name = health._text(raw.get("name"), 30)
    if not name:
        raise ValidationError("食材名称不能为空")
    quantity = health._num(raw.get("quantity"), f"{name}的数量", 0, 100000, required=False)
    unit = health._text(raw.get("unit"), 8)
    # 兜底：名称里还带着数量（规则粗分或模型偶尔这样返回），拆出来，否则「6个鸡蛋」匹配不上菜谱里的「鸡蛋」
    q, u, bare = split_quantity(name)
    if bare != name and bare:
        name = bare
        if quantity is None:
            quantity, unit = q, u or unit
    category = raw.get("category") if raw.get("category") in CATEGORIES else guess_category(name)
    storage = raw.get("storage") if raw.get("storage") in STORAGES else default_storage(name, category)
    expires_on, estimated = None, True
    if raw.get("expires_on"):
        expires_on = health.parse_day(raw.get("expires_on"), today)
        estimated = False
    else:
        expires_on = estimate_expiry(name, category, storage, today)
    return {"name": name, "category": category, "storage": storage, "quantity": quantity, "unit": unit,
            "expires_on": expires_on.isoformat() if expires_on else None, "expires_estimated": int(estimated)}


def add_items(conn, user_id: int, raw_items: list, today: date, source: str = "manual") -> list[dict]:
    """加入库存。已有同名在用食材时合并：数量同单位相加，否则以新数量为准；到期日按新买的刷新。"""
    if not isinstance(raw_items, list) or not raw_items:
        raise ValidationError("至少加一样食材")
    if len(raw_items) > 40:
        raise ValidationError("一次最多加 40 样")
    out = []
    for raw in raw_items:
        item = _clean_item(raw, today)
        existing = None
        for row in conn.execute("SELECT * FROM pantry_items WHERE user_id=? AND status='active' AND storage=?",
                                (user_id, item["storage"])).fetchall():
            if normalize_name(row["name"]) == normalize_name(item["name"]):
                existing = row
                break
        if existing is not None:
            quantity = item["quantity"]
            if quantity is not None and existing["quantity"] is not None and (existing["unit"] or "") == item["unit"]:
                quantity = round(existing["quantity"] + quantity, 2)
            elif quantity is None:
                quantity = existing["quantity"]
            unit = item["unit"] if item["quantity"] is not None else existing["unit"]
            conn.execute("UPDATE pantry_items SET quantity=?, unit=?, expires_on=?, expires_estimated=?, "
                         "updated_at=datetime('now') WHERE id=?",
                         (quantity, unit, item["expires_on"], item["expires_estimated"], existing["id"]))
            item_id = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO pantry_items (user_id, name, category, quantity, unit, storage, expires_on, "
                "expires_estimated, source) VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, item["name"], item["category"], item["quantity"], item["unit"], item["storage"],
                 item["expires_on"], item["expires_estimated"], source))
            item_id = cur.lastrowid
        out.append(get_item(conn, user_id, item_id, today))
    return out


def update_item(conn, user_id: int, item_id: int, changes: dict, today: date) -> dict | None:
    """修改一样在用的食材。到期日规则：
    - 显式传了 expires_on：以它为准（传空表示改回估算）
    - 只改了存放位置且原到期日是估算值：按新位置重新估算（如冷藏改冷冻，保质期变长）
    - 其他情况：保留原到期日和「是否估算」标记
    """
    current = get_item(conn, user_id, item_id, today)
    if current is None or current["status"] != "active":
        return None
    merged = {k: current[k] for k in ("name", "category", "storage", "quantity", "unit")}
    merged.update({k: changes[k] for k in ("name", "category", "storage", "quantity", "unit") if k in changes})
    keep_expiry = "expires_on" not in changes and not ("storage" in changes and current["expires_estimated"])
    if "expires_on" in changes:
        merged["expires_on"] = changes["expires_on"]
    clean = _clean_item(merged, today)
    if keep_expiry:
        clean["expires_on"], clean["expires_estimated"] = current["expires_on"], int(current["expires_estimated"])
    conn.execute("UPDATE pantry_items SET name=?, category=?, storage=?, quantity=?, unit=?, expires_on=?, "
                 "expires_estimated=?, updated_at=datetime('now') WHERE id=? AND user_id=?",
                 (clean["name"], clean["category"], clean["storage"], clean["quantity"], clean["unit"],
                  clean["expires_on"], clean["expires_estimated"], item_id, user_id))
    return get_item(conn, user_id, item_id, today)


def remove_item(conn, user_id: int, item_id: int, reason: str = "used") -> bool:
    if reason not in ("used", "discarded"):
        raise ValidationError("移除原因只能是 used（用完了）或 discarded（扔掉了）")
    cur = conn.execute("UPDATE pantry_items SET status=?, updated_at=datetime('now') "
                       "WHERE id=? AND user_id=? AND status='active'", (reason, item_id, user_id))
    return cur.rowcount > 0


def usable_pantry(conn, user_id: int, today: date) -> list[dict]:
    """推荐时能用的库存：去掉按（估算）到期日已经过期的。过期的先让用户在首页清点（还在 / 用完了 / 扔了），
    确认「还在」的会重新进来。"""
    return [p for p in list_pantry(conn, user_id, today) if p["days_left"] is None or p["days_left"] >= 0]


def review_items(conn, user_id: int, decisions: list, today: date) -> dict:
    """清点过期食材：keep 还在（到期日改成 2 天后，仍标「估算」，推荐时当临期优先用掉）/ used 用完了 / discarded 扔了。"""
    if not isinstance(decisions, list) or not decisions:
        raise ValidationError("没有要清点的食材")
    done = {"keep": 0, "used": 0, "discarded": 0}
    for d in decisions[:100]:
        if not isinstance(d, dict) or d.get("action") not in done or not isinstance(d.get("id"), int):
            raise ValidationError("清点结果格式不对")
        row = conn.execute("SELECT id FROM pantry_items WHERE id=? AND user_id=? AND status='active'",
                           (d["id"], user_id)).fetchone()
        if row is None:
            continue
        if d["action"] == "keep":
            conn.execute("UPDATE pantry_items SET expires_on=?, expires_estimated=1, updated_at=datetime('now') "
                         "WHERE id=? AND user_id=?", ((today + timedelta(days=2)).isoformat(), d["id"], user_id))
        else:
            remove_item(conn, user_id, d["id"], d["action"])
        done[d["action"]] += 1
    return done


def pantry_version(conn, user_id: int) -> str:
    """在用库存的内容指纹，用来判断推荐是否过时。
    不用 updated_at：它只精确到秒，推荐后同一秒内做菜扣库存会被漏判。"""
    import hashlib
    rows = conn.execute("SELECT id, name, quantity, unit, storage, expires_on FROM pantry_items "
                        "WHERE user_id=? AND status='active' ORDER BY id", (user_id,)).fetchall()
    return hashlib.sha1(json.dumps([tuple(r) for r in rows]).encode()).hexdigest()[:16]


# 冰箱页「勾选常见食材」的候选（按分类分组），前后端共用这一份
CATALOG = {
    "veg": ["番茄", "土豆", "洋葱", "胡萝卜", "青椒", "黄瓜", "西兰花", "白菜", "青菜", "菠菜", "茄子", "蘑菇",
            "葱", "姜", "蒜"],
    "egg_dairy": ["鸡蛋", "牛奶", "酸奶", "奶酪"],
    "meat": ["鸡胸", "鸡腿", "鸡翅", "五花肉", "排骨", "肉末", "牛肉", "培根", "香肠"],
    "seafood": ["虾", "鱼"],
    "tofu": ["豆腐", "豆皮"],
    "staple": ["大米", "米饭", "面条", "馒头", "面包", "饺子"],
    "fruit": ["苹果", "香蕉", "橙子"],
}


def catalog() -> list[dict]:
    return [{"category": c, "label": CATEGORIES[c], "items": items} for c, items in CATALOG.items()]


# ---------------------------------------------------------------- 一句话录入

PARSE_PROMPT = """把用户描述的冰箱食材解析成 JSON，只输出 JSON，不要解释。
格式：{"items": [{"name": "食材名（简短通用名，如 番茄、鸡蛋、五花肉）", "quantity": 数字或 null, "unit": "单位，如 个、斤、g、盒，没有就空字符串",
"storage": "fridge|freezer|pantry（冷藏/冷冻/常温，用户没说就按常识）"}]}
规则：只提取食材，忽略与食材无关的话；「半颗」quantity=0.5；「两斤」quantity=2 unit=斤；没提数量 quantity=null。"""


def _fallback_parse(text: str) -> list[dict]:
    parts = re.split(r"[，,、；;\s和还有以及]+", text)
    out = []
    for p in parts:
        p = re.sub(r"^(冰箱里|家里|有|剩下|剩|还剩|买了)", "", p.strip())
        if 1 <= len(p) <= 12:
            out.append({"name": p})
    return out


def parse_text(client, model: str | None, text: str) -> list[dict]:
    """把「有鸡蛋、番茄、半颗洋葱」解析成食材列表。没配模型或模型出错时按标点粗分，保证可用。"""
    text = health._text(text, 500)
    if not text:
        raise ValidationError("说说冰箱里有什么吧")
    if client is not None and model:
        try:
            data = _llm_json(client, model, PARSE_PROMPT, text, max_tokens=1500)
            items = [i for i in (data.get("items") or []) if isinstance(i, dict) and str(i.get("name") or "").strip()]
            if items:
                return items[:40]
        except Exception:  # noqa: BLE001 —— 解析失败退回规则切分，不让用户卡住
            pass
    return _fallback_parse(text)[:40]


# ---------------------------------------------------------------- AI 菜谱

RECIPE_PROMPT = """你是做家常菜很在行的朋友，根据用户冰箱里现有的食材推荐 3 道今天能做的菜。只输出 JSON，不要解释。

格式：
{"recipes": [{
  "title": "菜名",
  "summary": "一句话说明为什么推荐（如 用掉快过期的菠菜，10 分钟出锅）",
  "minutes": 总耗时分钟整数,
  "difficulty": 1-3 的整数（1 简单 2 一般 3 稍难）,
  "servings": 份数整数,
  "kcal_per_serving": 每份估算热量整数,
  "protein_g": 每份蛋白质克数整数, "carbs_g": 每份碳水克数整数, "fat_g": 每份脂肪克数整数,
  "ingredients": [{"name": "用料通用名", "amount": "用量，如 2个、150g、少许", "optional": 是否可省略}],
  "equipment": ["用到的厨具，从 炒锅/锅/电饭煲/微波炉/空气炸锅/烤箱 里选"],
  "steps": ["步骤1", "步骤2", "..."],
  "tips": "一条小贴士，可为空字符串"
}]}

规则：
1. 主要用冰箱里已有的食材；标注「临期」的食材优先用掉。
2. 每道菜「必需但冰箱里没有」的食材最多 2 样（常备调料不算）；能不缺就不缺。
3. 3 道菜要有区别（做法或主料不同），优先家常、步骤清楚、新手也能做成。
4. 过敏原和用户不吃的东西绝对不能出现在用料里。
5. 步骤写清火候和时间（如「中火炒 2 分钟」），每步一句话，4–8 步。
6. 份量、口味、厨具、时间按「用户情况」来；用户补充的要求优先。"""


def _llm_json(client, model: str, system: str, user: str, max_tokens: int = 4000) -> dict:
    resp = client.chat.completions.create(
        model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"}, temperature=0.7, max_tokens=max_tokens, stream=False)
    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("模型返回的不是 JSON 对象")
    return data


def clean_recipe(raw: dict) -> dict | None:
    """校验并规整模型给出的一道菜；缺关键字段返回 None。"""
    if not isinstance(raw, dict):
        return None
    title = health._text(raw.get("title"), 30)
    steps = [health._text(s, 200) for s in (raw.get("steps") or []) if health._text(s, 200)][:12]
    ingredients = []
    for i in (raw.get("ingredients") or [])[:20]:
        if isinstance(i, dict) and health._text(i.get("name"), 20):
            ingredients.append({"name": health._text(i.get("name"), 20), "amount": health._text(i.get("amount"), 20),
                                "optional": bool(i.get("optional"))})
    if not title or not steps or not ingredients:
        return None

    def bounded(value, lo, hi, default):
        try:
            return max(lo, min(hi, int(round(float(value)))))
        except (TypeError, ValueError):
            return default

    kcal = raw.get("kcal_per_serving")
    macros = {k: bounded(raw.get(k), 0, 300, None) for k in ("protein_g", "carbs_g", "fat_g")}
    return {"title": title, "summary": health._text(raw.get("summary"), 80),
            "minutes": bounded(raw.get("minutes"), 1, 240, 20), "difficulty": bounded(raw.get("difficulty"), 1, 3, 1),
            "servings": bounded(raw.get("servings"), 1, 8, 1),
            "kcal_per_serving": bounded(kcal, 0, 3000, None) if kcal is not None else None,
            # 每份营养素（估算）。模型没给就是 None，记一餐时不填，避免显示成「0g」误导
            "macros": macros if all(v is not None for v in macros.values()) else None,
            "equipment": [health._text(e, 10) for e in (raw.get("equipment") or []) if health._text(e, 10)][:6]
            if isinstance(raw.get("equipment"), list) else [],
            "ingredients": ingredients, "steps": steps, "tips": health._text(raw.get("tips"), 120)}


def annotate(recipe: dict, pantry: list[dict], staples=DEFAULT_STAPLES) -> dict:
    """对照当前库存，给每样用料标注 have / staple / missing；统计缺料与用到的临期食材。"""
    used_ids, expiring = [], []
    missing = []
    for ing in recipe["ingredients"]:
        ing.pop("status", None)
        ing.pop("pantry_id", None)
        if is_staple(ing["name"], staples):
            ing["status"] = "staple"
            continue
        hit = next((p for p in pantry if names_match(ing["name"], p["name"])), None)
        if hit:
            ing["status"], ing["pantry_id"] = "have", hit["id"]
            if hit["id"] not in used_ids:
                used_ids.append(hit["id"])
                if hit["days_left"] is not None and hit["days_left"] <= EXPIRING_DAYS:
                    expiring.append(hit["name"])
        else:
            ing["status"] = "missing"
            if not ing["optional"]:
                missing.append(ing["name"])
    recipe["missing"] = missing
    recipe["uses_expiring"] = expiring
    recipe["uses_count"] = len(used_ids)
    return recipe


def rank_key(recipe: dict, goals=()):
    """推荐排序（越小越靠前）。默认：
      现在就能做（不缺必需料）→ 符合你的时间/难度/热量 → 用到的临期食材多 → 缺料少 → 用到的库存多 → 耗时短
    「能不能马上做」放第一位：核心问题是「剩下的东西能做什么」，缺料的菜再能消耗临期食材也得先去买。
    问卷 Q7 改变中间几位的先后：
      选了「食材总放坏」→ 用到的临期食材多 提到「符合设置」之前（宁可多花点时间也先救食材）
      选了「想省钱」（且没选上一项）→ 缺料少 提到「临期」之前（少买一样是一样）"""
    missing = len(recipe["missing"])
    off = bool(recipe.get("fit"))
    expiring = -len(recipe["uses_expiring"])
    tail = (-recipe["uses_count"], recipe["minutes"])
    if "waste" in goals:
        return (missing > 0, expiring, off, missing, *tail)
    if "save_money" in goals:
        return (missing > 0, off, missing, expiring, *tail)
    return (missing > 0, off, expiring, missing, *tail)


def _meal_slot(now: datetime) -> str:
    h = now.hour
    return "早餐" if 5 <= h < 10 else "午餐" if 10 <= h < 15 else "晚餐" if 15 <= h < 21 else "夜宵"


def recommend(conn, client, model: str | None, user_id: int, now: datetime, note: str = "",
              daily_limit: int = 20) -> dict:
    """生成一批推荐（默认 3 道），校验、标注、排序后落库，返回 {batch, recipes, dropped}。"""
    if client is None or not model:
        raise ValidationError("还没有配置模型服务，暂时无法推荐菜谱")
    today = now.date()
    used = conn.execute("SELECT COUNT(DISTINCT batch) FROM recipes WHERE user_id=? AND date(created_at)=?",
                        (user_id, datetime.utcnow().date().isoformat())).fetchone()[0]
    if used >= daily_limit:
        raise ValidationError(f"今天已经推荐了 {used} 次，明天再来吧（每天最多 {daily_limit} 次）")
    pantry = usable_pantry(conn, user_id, today)
    if not pantry:
        if list_pantry(conn, user_id, today):
            raise ValidationError("冰箱里的东西按估算都过期了，先在首页清点一下吧")
        raise ValidationError("冰箱里还没有食材，先加几样吧")

    profile = health.get_profile(conn, user_id)
    prefs = prefs_mod.load(conn, user_id)
    allergies = prefs_mod.allergy_groups(profile)
    staples = prefs_mod.staple_names(prefs)
    # 换一批：上一批里没点开、没收藏、没做的菜记一次「跳过」，再读学到的口味
    taste.mark_skips(conn, user_id, now)
    learned = taste.profile(conn, user_id, now)
    lines = [f"现在是 {now.strftime('%H:%M')}，这顿是{_meal_slot(now)}。"]
    lines.append("冰箱里的食材（按到期从近到远）：")
    for p in pantry[:60]:
        flag = "【临期】" if p["days_left"] is not None and p["days_left"] <= EXPIRING_DAYS else ""
        lines.append(f"- {flag}{describe_item(p)} · {p['storage_label']}")
    lines.append("常备调料（不算缺料）：" + ("、".join(prefs["staples"]) or "没有"))
    lines.append("用户情况：")
    lines.extend("- " + t for t in prefs_mod.prompt_lines(prefs))
    if allergies:
        lines.append("过敏，绝对不能用：" + "、".join(label for label, _ in allergies))
    learned_lines = taste.prompt_lines(learned)
    if learned_lines:
        lines.append("从用户以前的选择里学到的：")
        lines.extend("- " + t for t in learned_lines)
    if profile.get("diet_preferences"):
        lines.append("饮食偏好：" + profile["diet_preferences"])
    if profile.get("conditions"):
        lines.append("健康状况（做菜时注意）：" + profile["conditions"])
    targets = health.compute_targets(profile, today)
    kcal_left = None
    if targets["complete"] and (profile.get("goal") in ("lose", "gain") or "healthy" in prefs["goals"]):
        kcal_left = health.daily_summary(conn, user_id, today, today)["remaining_calories"]
        lines.append(f"今天还可摄入约 {kcal_left} kcal，每份热量尽量不超过它。")
    if "healthy" not in prefs["goals"]:
        kcal_left = None  # 只有选了「想吃得健康」才把超热量的菜排后面
    if note:
        lines.append("用户补充：" + health._text(note, 200))

    data = _llm_json(client, model, RECIPE_PROMPT, "\n".join(lines))
    recipes, dropped = [], []
    for raw in (data.get("recipes") or [])[:5]:
        recipe = clean_recipe(raw)
        if recipe is None:
            continue
        recipe, reason = prefs_mod.apply_constraints(recipe, prefs, allergies)
        reason = reason or (taste.blocked(recipe, learned) if recipe else None)
        if reason:
            dropped.append({"title": raw.get("title") or "", "reason": reason})
            continue
        annotate(recipe, pantry, staples)
        recipe["fit"] = prefs_mod.fit_notes(recipe, prefs, kcal_left) + taste.notes(recipe, learned)
        recipes.append(recipe)
    if not recipes:
        why = "、".join(dict.fromkeys(d["reason"] for d in dropped))
        raise ValidationError(f"这次想到的菜都不符合你的设置（{why}），再试一次吧" if why
                              else "这次没能生成合适的菜谱，换个说法再试一次吧")
    recipes.sort(key=lambda r: rank_key(r, prefs["goals"]))

    batch = uuid.uuid4().hex[:12]
    version = pantry_version(conn, user_id)
    out = []
    for r in recipes[:3]:
        r["pantry_version"] = version
        cur = conn.execute("INSERT INTO recipes (user_id, batch, title, data) VALUES (?,?,?,?)",
                           (user_id, batch, r["title"], json.dumps(r, ensure_ascii=False)))
        out.append(recipe_payload(conn, user_id, cur.lastrowid, today))
    return {"batch": batch, "recipes": out, "dropped": dropped}


def recipe_payload(conn, user_id: int, recipe_id: int, today: date, refresh: bool = True) -> dict | None:
    """读取一道菜；refresh=True 时按当前库存重新标注（库存可能已变化）。"""
    row = conn.execute("SELECT * FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)).fetchone()
    if row is None:
        return None
    data = json.loads(row["data"])
    if refresh:
        annotate(data, usable_pantry(conn, user_id, today), prefs_mod.staple_names(prefs_mod.load(conn, user_id)))
    cooked = conn.execute("SELECT COUNT(*) FROM cook_logs WHERE user_id=? AND recipe_id=?",
                          (user_id, recipe_id)).fetchone()[0]
    # 用户对这道说过「不想吃」：前端据此从推荐列表里隐藏（刷新后也不再出现）
    disliked = conn.execute("SELECT reason FROM recipe_feedback WHERE user_id=? AND recipe_id=? AND kind='dislike' "
                            "ORDER BY id DESC LIMIT 1", (user_id, recipe_id)).fetchone()
    return {"id": row["id"], "batch": row["batch"], "saved": bool(row["saved"]), "created_at": row["created_at"],
            "cooked_count": cooked, "disliked": disliked["reason"] if disliked else None, **data}


def latest_batch(conn, user_id: int, today: date) -> dict:
    row = conn.execute("SELECT batch FROM recipes WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if row is None:
        return {"batch": None, "recipes": [], "stale": False}
    ids = [r["id"] for r in conn.execute("SELECT id FROM recipes WHERE user_id=? AND batch=? ORDER BY id",
                                         (user_id, row["batch"])).fetchall()]
    recipes = [recipe_payload(conn, user_id, i, today) for i in ids]
    stale = bool(recipes) and recipes[0].get("pantry_version") != pantry_version(conn, user_id)
    return {"batch": row["batch"], "recipes": recipes, "stale": stale}


def set_saved(conn, user_id: int, recipe_id: int, saved: bool) -> bool:
    cur = conn.execute("UPDATE recipes SET saved=? WHERE id=? AND user_id=?", (int(saved), recipe_id, user_id))
    return cur.rowcount > 0


def list_saved(conn, user_id: int, today: date) -> dict:
    saved = [recipe_payload(conn, user_id, r["id"], today) for r in conn.execute(
        "SELECT id FROM recipes WHERE user_id=? AND saved=1 ORDER BY id DESC LIMIT 100", (user_id,)).fetchall()]
    logs = [dict(r) | {"used": json.loads(r["used"])} for r in conn.execute(
        "SELECT * FROM cook_logs WHERE user_id=? ORDER BY cooked_at DESC, id DESC LIMIT 30", (user_id,)).fetchall()]
    return {"saved": saved, "cooked": logs}


# ---------------------------------------------------------------- 做好了：扣库存 + 记一餐

_AMOUNT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([^\d\s]*)")


def _parse_amount(text: str):
    m = _AMOUNT_RE.match(text or "")
    return (float(m.group(1)), m.group(2)) if m else (None, "")


def cook_preview(conn, user_id: int, recipe_id: int, now: datetime) -> dict | None:
    """「做好了」确认页：列出会动到的库存，并给出建议（能按数量扣就扣，否则按分类建议用完/还有剩）。"""
    recipe = recipe_payload(conn, user_id, recipe_id, now.date())
    if recipe is None:
        return None
    pantry = {p["id"]: p for p in list_pantry(conn, user_id, now.date())}
    usage = []
    for ing in recipe["ingredients"]:
        p = pantry.get(ing.get("pantry_id"))
        if not p or any(u["item_id"] == p["id"] for u in usage):
            continue
        amount, unit = _parse_amount(ing["amount"])
        remaining = None
        if p["quantity"] is not None and amount is not None and (unit or "") == (p["unit"] or ""):
            remaining = round(max(0.0, p["quantity"] - amount), 2)
            used_up = remaining <= 0
        else:
            used_up = not (p["category"] in USUALLY_LEFTOVER or any(n in p["name"] for n in LEFTOVER_NAMES))
        usage.append({"item_id": p["id"], "name": p["name"], "amount": ing["amount"], "quantity": p["quantity"],
                      "unit": p["unit"], "remaining": remaining, "used_up": used_up})
    slot = {"早餐": "breakfast", "午餐": "lunch", "晚餐": "dinner"}.get(_meal_slot(now), "snack")
    return {"recipe": recipe, "usage": usage, "meal_type": slot, "eaten_servings": 1}


def cook(conn, user_id: int, recipe_id: int, now: datetime, usage: list, eaten_servings=1,
         meal_type: str | None = None, log_meal: bool = True) -> dict | None:
    """做好了：按确认结果扣库存；按吃掉的份数记一餐（热量为 AI 估算）；写做菜记录。调用方负责提交。"""
    preview = cook_preview(conn, user_id, recipe_id, now)
    if preview is None:
        return None
    recipe = preview["recipe"]
    eaten = health._num(eaten_servings, "吃了几份", 0, 8) or 0
    meal_type = meal_type or preview["meal_type"]
    if meal_type not in health.MEAL_TYPES:
        raise ValidationError("餐次只能是 breakfast / lunch / dinner / snack")

    suggested = {u["item_id"]: u for u in preview["usage"]}
    decisions = {}
    for u in usage or []:
        if isinstance(u, dict) and isinstance(u.get("item_id"), int) and u["item_id"] in suggested:
            decisions[u["item_id"]] = bool(u.get("used_up"))
    used_log = []
    for item_id, s in suggested.items():
        used_up = decisions.get(item_id, s["used_up"])
        if used_up:
            remove_item(conn, user_id, item_id, "used")
            used_log.append({"name": s["name"], "result": "用完了"})
        elif s["remaining"] is not None and s["remaining"] <= 0:
            # 按数量算已经用光，但用户说还有剩：说明原来记的数量不准，改成「数量未知」而不是存 0
            conn.execute("UPDATE pantry_items SET quantity=NULL, updated_at=datetime('now') WHERE id=? AND user_id=?",
                         (item_id, user_id))
            used_log.append({"name": s["name"], "result": "还有剩"})
        elif s["remaining"] is not None:
            conn.execute("UPDATE pantry_items SET quantity=?, updated_at=datetime('now') WHERE id=? AND user_id=?",
                         (s["remaining"], item_id, user_id))
            unit = s["unit"] or ""
            left = int(s["remaining"]) if float(s["remaining"]).is_integer() else s["remaining"]
            used_log.append({"name": s["name"], "result": f"还剩 {left}{unit}"})
        else:
            used_log.append({"name": s["name"], "result": "还有剩"})

    record = None
    if log_meal and eaten > 0:
        kcal = recipe.get("kcal_per_serving")
        item = {"name": recipe["title"], "amount": f"{eaten:g} 份", "calories": min(5000, round((kcal or 400) * eaten))}
        if recipe.get("macros"):
            item.update({"protein": round(recipe["macros"]["protein_g"] * eaten, 1),
                         "carbs": round(recipe["macros"]["carbs_g"] * eaten, 1),
                         "fat": round(recipe["macros"]["fat_g"] * eaten, 1)})
        record = health.add_record(conn, user_id, "meal", {
            "meal_type": meal_type,
            "items": [item],
            "note": "做菜后自动记录，热量为估算" + ("" if kcal else "（菜谱未给热量，按 400 kcal/份估）"),
        }, now, source="cook")
    conn.execute("INSERT INTO cook_logs (user_id, recipe_id, title, cooked_at, servings, record_id, used) "
                 "VALUES (?,?,?,?,?,?,?)",
                 (user_id, recipe_id, recipe["title"], now.isoformat(timespec="minutes"), eaten,
                  record["id"] if record else None, json.dumps(used_log, ensure_ascii=False)))
    return {"title": recipe["title"], "used": used_log,
            "record": {"id": record["id"], "text": health.describe_record(record)} if record else None}
