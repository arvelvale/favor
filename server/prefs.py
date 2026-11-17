"""厨房偏好（问卷结果）：默认值、校验、写进推荐提示词的文字，以及服务端硬约束。

原则：问卷的每一题都必须改变一个看得见的行为。对应关系：
  Q1 household   → 默认份量；推荐结构（一人「一锅出、少剩菜」/ 家庭「两菜一汤」）；老人、小孩的提示
  Q2 skill       → 难度上限（超出的排后面并标注）；新手模式下步骤解释术语
  Q3 minutes     → 时间上限（超出的排后面并标注）
  Q4 equipment   → 硬过滤：需要用户没有的厨具的菜直接剔除
  Q5 staples     → 勾选的调料不算「缺料」
  Q6 taste       → 过敏、饮食方式、不吃的 = 硬约束（代码校验）；辣度 = 软偏好（只进提示词）
  Q7 goals       → 排序规则（见 kitchen.rank_key）、首页模块顺序；选「吃得健康」时健康进主导航
  Q8 body        → 复用健康档案（身高体重、目标），推荐时按今天剩余热量提示
"""
import json
import re

import health
from health import ValidationError

HOUSEHOLDS = {"solo": "只有我", "two": "两个人", "family": "一家人"}
FAMILY_FLAGS = {"elderly": "有老人", "kids": "有小孩"}
SKILLS = {"beginner": "几乎不会", "home": "会做家常菜", "skilled": "挺熟练"}
# 难度 1 简单 / 2 一般 / 3 稍难。「想学做饭」时上限 +1
DIFFICULTY_CAP = {"beginner": 1, "home": 2, "skilled": 3}
MINUTE_CHOICES = (15, 30, 0)  # 0 = 不赶时间（不设上限）
EQUIPMENT = {"wok": "炒锅", "rice_cooker": "电饭煲", "microwave": "微波炉", "air_fryer": "空气炸锅",
             "oven": "烤箱", "mini_pot": "小电锅"}
STAPLE_OPTIONS = ("盐", "油", "酱油", "醋", "糖", "蚝油", "料酒", "淀粉", "豆瓣酱", "胡椒粉", "香油", "鸡精")
# 勾一项等于勾了它的常见写法，避免菜谱写「生抽」时被算成缺料
STAPLE_ALIASES = {"油": ("食用油", "植物油", "花生油", "菜籽油"), "酱油": ("生抽", "老抽"), "糖": ("白糖", "冰糖"),
                  "淀粉": ("玉米淀粉", "生粉", "水淀粉"), "香油": ("芝麻油",), "胡椒粉": ("白胡椒粉", "胡椒")}
ALWAYS_STAPLES = ("水", "清水", "开水", "温水")
SPICES = {"none": "不吃辣", "mild": "微辣", "medium": "中辣", "hot": "很能吃辣"}
DIETS = {"none": "没有限制", "vegetarian": "素食（蛋奶素）", "vegan": "纯素", "halal": "清真", "no_beef": "不吃牛肉"}
GOALS = {"what_to_cook": "不知道做什么", "waste": "食材总放坏", "save_money": "想省钱",
         "healthy": "想吃得健康", "learn": "想学做饭"}
QUESTIONS = ("household", "skill", "minutes", "equipment", "staples", "taste", "goals", "body")
STATUSES = ("done", "skipped")

DEFAULTS = {
    "household": "solo", "family_size": 3, "family_flags": [],
    "skill": "home", "minutes": 30,
    "equipment": ["wok", "rice_cooker", "microwave"],
    "staples": ["盐", "油", "酱油", "醋", "糖"],
    "spice": "mild", "dislikes": [], "diet": "none",
    "goals": ["what_to_cook"],
}

# ---------------------------------------------------------------- 存取


def _pick(value, allowed, name):
    if value not in allowed:
        raise ValidationError(f"{name}的取值不对")
    return value


def _str_list(value, limit=10, length=10):
    if not isinstance(value, list):
        raise ValidationError("应为列表")
    out = []
    for v in value:
        t = health._text(v, length)
        if t and t not in out:
            out.append(t)
    return out[:limit]


def normalize(changes: dict) -> dict:
    """校验问卷答案（可只传一部分），返回规整后的字段。未知字段忽略。"""
    clean = {}
    if not isinstance(changes, dict):
        return clean
    if "household" in changes:
        clean["household"] = _pick(changes["household"], HOUSEHOLDS, "做饭人数")
    if "family_size" in changes:
        clean["family_size"] = int(health._num(changes["family_size"], "家里几口人", 2, 10, integer=True))
    if "family_flags" in changes:
        clean["family_flags"] = [f for f in _str_list(changes["family_flags"], length=20) if f in FAMILY_FLAGS]
    if "skill" in changes:
        clean["skill"] = _pick(changes["skill"], SKILLS, "做饭水平")
    if "minutes" in changes:
        clean["minutes"] = _pick(changes["minutes"], MINUTE_CHOICES, "做饭时间")
    if "equipment" in changes:
        # 注意长度上限要容得下最长的代码（rice_cooker 11 位），否则会被截断后当成未知值丢掉
        eq = [e for e in _str_list(changes["equipment"], length=20) if e in EQUIPMENT]
        if not eq:
            raise ValidationError("至少选一样厨具")
        clean["equipment"] = eq
    if "staples" in changes:
        clean["staples"] = _str_list(changes["staples"], limit=20)
    if "spice" in changes:
        clean["spice"] = _pick(changes["spice"], SPICES, "辣度")
    if "dislikes" in changes:
        clean["dislikes"] = _str_list(changes["dislikes"])
    if "diet" in changes:
        clean["diet"] = _pick(changes["diet"], DIETS, "饮食方式")
    if "goals" in changes:
        clean["goals"] = [g for g in _str_list(changes["goals"], length=20) if g in GOALS] or ["what_to_cook"]
    return clean


def get(conn, user_id: int) -> dict:
    """{status: new/done/skipped, prefs: 合并默认值后的完整偏好, skipped: [跳过的题]}"""
    row = conn.execute("SELECT * FROM user_prefs WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        return {"status": "new", "prefs": json.loads(json.dumps(DEFAULTS)), "skipped": []}
    stored = json.loads(row["data"] or "{}")
    return {"status": row["status"], "prefs": json.loads(json.dumps(DEFAULTS)) | stored,
            "skipped": json.loads(row["skipped"] or "[]")}


def load(conn, user_id: int) -> dict:
    return get(conn, user_id)["prefs"]


def save(conn, user_id: int, changes: dict, status: str | None = None, skipped=None) -> dict:
    """合并保存。status 只在问卷完成/整体跳过时传；skipped 为跳过的题目（之后在合适时机再问）。调用方负责提交。"""
    current = get(conn, user_id)
    clean = normalize(changes)
    row = conn.execute("SELECT data FROM user_prefs WHERE user_id=?", (user_id,)).fetchone()
    stored = (json.loads(row["data"] or "{}") if row else {}) | clean
    new_status = _pick(status, STATUSES, "问卷状态") if status else (
        current["status"] if current["status"] != "new" else "done")
    new_skipped = current["skipped"] if skipped is None else [q for q in _str_list(skipped, length=20) if q in QUESTIONS]
    # 重新回答过的题不再算跳过
    answered = {"household": "household", "family_size": "household", "family_flags": "household", "skill": "skill",
                "minutes": "minutes", "equipment": "equipment", "staples": "staples", "spice": "taste",
                "dislikes": "taste", "diet": "taste", "goals": "goals"}
    if skipped is None:
        new_skipped = [q for q in new_skipped if q not in {answered[k] for k in clean}]
    conn.execute(
        "INSERT INTO user_prefs (user_id, data, status, skipped) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, status=excluded.status, skipped=excluded.skipped, "
        "updated_at=datetime('now')",
        (user_id, json.dumps(stored, ensure_ascii=False), new_status, json.dumps(new_skipped, ensure_ascii=False)))
    return get(conn, user_id)


# ---------------------------------------------------------------- 推荐用的派生值


def servings(prefs: dict) -> int:
    return {"solo": 1, "two": 2}.get(prefs["household"], prefs.get("family_size") or 3)


def staple_names(prefs: dict) -> tuple:
    names = list(ALWAYS_STAPLES)
    for s in prefs.get("staples") or []:
        names.append(s)
        names.extend(STAPLE_ALIASES.get(s, ()))
    return tuple(names)


def difficulty_cap(prefs: dict) -> int:
    cap = DIFFICULTY_CAP.get(prefs["skill"], 2)
    return min(3, cap + 1) if "learn" in prefs["goals"] else cap


def health_in_nav(prefs: dict) -> bool:
    return "healthy" in prefs["goals"]


def prompt_lines(prefs: dict) -> list[str]:
    """写进推荐提示词的偏好（软偏好靠这里；硬约束另在代码里校验）。"""
    n = servings(prefs)
    lines = []
    if prefs["household"] == "solo":
        lines.append("一个人吃：做 1 人份，优先一锅出、少剩菜的菜，别做多。")
    elif prefs["household"] == "two":
        lines.append("两个人吃：做 2 人份。")
    else:
        lines.append(f"给一家 {n} 口人做：做 {n} 人份；3 道菜按「两菜一汤」搭配（至少一道汤、一道素菜），能凑成一顿饭。")
    if "elderly" in prefs["family_flags"]:
        lines.append("家里有老人：少盐少油，做得软烂好嚼。")
    if "kids" in prefs["family_flags"]:
        lines.append("家里有小孩：不要太辣，注意去刺去骨、切小块。")
    cap = difficulty_cap(prefs)
    if prefs["skill"] == "beginner":
        lines.append(f"用户几乎不会做饭：难度不超过 {cap}；步骤里第一次出现焯水、勾芡、爆香、收汁等说法时，用括号解释怎么做。")
    elif prefs["skill"] == "skilled":
        lines.append("用户做饭挺熟练，可以推荐有点技术含量的菜。")
    else:
        lines.append(f"用户会做家常菜：难度不超过 {cap}。")
    if prefs["minutes"]:
        lines.append(f"工作日希望 {prefs['minutes']} 分钟内做完（含准备）。")
    eq = "、".join(EQUIPMENT[e] for e in prefs["equipment"])
    if prefs["equipment"] == ["mini_pot"]:
        lines.append("只有一个小电锅（宿舍条件）：只推荐一锅煮、焖、蒸能完成的菜，不要用炒锅、烤箱。")
    else:
        lines.append(f"只有这些厨具：{eq}。不要推荐需要其他厨具的菜（尤其烤箱、空气炸锅、微波炉没有时）。")
    lines.append(f"口味：{SPICES[prefs['spice']]}。")
    if prefs["diet"] != "none":
        lines.append(f"饮食方式：{DIETS[prefs['diet']]}，用料必须符合。")
    if prefs["dislikes"]:
        lines.append("不吃（绝对不能出现在用料里）：" + "、".join(prefs["dislikes"]))
    goals = prefs["goals"]
    if "waste" in goals:
        lines.append("用户最在意别把食材放坏：尽量一次多用掉几样临期食材。")
    if "save_money" in goals:
        lines.append("用户想省钱：尽量不用额外买的食材；非买不可时选便宜常见的。")
    if "learn" in goals:
        lines.append("用户想学做饭：3 道里安排一道能学到一个新手法的，tips 写这个手法的要点。")
    if "healthy" in goals:
        lines.append("用户想吃得健康：少油少盐，荤素搭配，热量估算尽量准确。")
    return lines


def summary_text(prefs: dict) -> str:
    """给对话 agent 的一行偏好摘要。"""
    parts = [f"{HOUSEHOLDS[prefs['household']]}（{servings(prefs)} 人份）", f"做饭水平：{SKILLS[prefs['skill']]}",
             f"工作日做饭：{str(prefs['minutes']) + ' 分钟内' if prefs['minutes'] else '不赶时间'}",
             "厨具：" + "、".join(EQUIPMENT[e] for e in prefs["equipment"]),
             "常备调料：" + ("、".join(prefs["staples"]) or "无"), f"辣度：{SPICES[prefs['spice']]}"]
    if prefs["diet"] != "none":
        parts.append(f"饮食方式：{DIETS[prefs['diet']]}")
    if prefs["dislikes"]:
        parts.append("不吃：" + "、".join(prefs["dislikes"]))
    parts.append("最想解决：" + "、".join(GOALS[g] for g in prefs["goals"]))
    return "；".join(parts)


# ---------------------------------------------------------------- 硬约束（服务端校验，不只靠提示词）

ALLERGY_GROUPS = {
    "海鲜": ("虾", "蟹", "贝", "蛤", "蚝", "鱿鱼", "墨鱼", "章鱼", "蛏", "螺", "海参", "鲍鱼", "海鲜"),
    "坚果": ("核桃", "杏仁", "腰果", "开心果", "榛子", "松子", "碧根果", "夏威夷果", "坚果"),
    "花生": ("花生",),
    "牛奶": ("牛奶", "奶粉", "芝士", "奶酪", "黄油", "奶油", "酸奶", "炼乳"),
    "鸡蛋": ("蛋",),
    "大豆": ("大豆", "黄豆", "豆腐", "豆浆", "腐竹", "豆皮", "毛豆", "豆豉", "豆瓣", "酱油", "生抽", "老抽", "腐乳", "味噌"),
    "小麦": ("小麦", "面", "麸", "馒头", "饺子", "馄饨", "饼"),
}
ALLERGY_OPTIONS = tuple(ALLERGY_GROUPS)


def allergy_list(profile: dict) -> list[str]:
    out = []
    for t in re.split(r"[，,、；;\s/]+", profile.get("allergies") or ""):
        t = t.strip().removesuffix("过敏")
        if t and t not in ("无", "没有", "暂无", "不过敏") and t not in out:
            out.append(t)
    return out


def allergy_groups(profile: dict) -> list[tuple[str, tuple]]:
    """[(展示名, 要查的词…)]：常见过敏原展开成具体食材，例如「海鲜」→ 虾、蟹、贝……"""
    return [(t, ALLERGY_GROUPS.get(t, (t,))) for t in allergy_list(profile)]


DIET_CATEGORIES = {"vegetarian": {"meat", "seafood"}, "vegan": {"meat", "seafood", "egg_dairy"}}
DIET_WORDS = {
    "vegetarian": ("猪油", "蚝油", "鱼露", "虾皮", "骨汤", "鸡汤", "高汤"),
    "vegan": ("猪油", "蚝油", "鱼露", "虾皮", "骨汤", "鸡汤", "高汤", "蜂蜜", "黄油", "奶油", "芝士", "奶酪", "蛋"),
    "halal": ("猪", "五花", "培根", "火腿", "腊肉", "腊肠", "香肠", "午餐肉", "酒"),
    "no_beef": ("牛肉", "肥牛", "牛腩", "牛排", "牛腱", "牛筋", "牛尾", "牛杂", "牛骨", "牛百叶", "牛丸", "牛柳"),
}
DISLIKE_GROUPS = {
    "内脏": ("肝", "肚", "腰花", "腰子", "肥肠", "大肠", "鸡心", "鸭肠", "鸭血", "猪血", "黄喉", "鸡胗", "鸭胗"),
    "海鲜": ("虾", "蟹", "贝", "蛤", "蚝", "鱿鱼", "墨鱼", "螺"),
}
# 单字忌口要排除的「不是一回事」的食材：不吃葱 ≠ 不吃洋葱
NOT_SAME = {"葱": ("洋葱",), "姜": ("姜黄",), "肝": ("猪肝菌",)}


def _hits(name: str, word: str) -> bool:
    if word not in name:
        return False
    return not any(x in name for x in NOT_SAME.get(word, ()))


def _ingredient_conflict(name: str, prefs: dict) -> str | None:
    from kitchen import guess_category  # 避免循环导入
    diet = prefs.get("diet") or "none"
    if diet != "none":
        if guess_category(name) in DIET_CATEGORIES.get(diet, set()):
            return DIETS[diet]
        if diet == "halal" and "排骨" in name and not any(x in name for x in ("牛", "羊", "鸡")):
            return DIETS[diet]
        if any(_hits(name, w) for w in DIET_WORDS.get(diet, ())):
            return DIETS[diet]
    for d in prefs.get("dislikes") or []:
        words = DISLIKE_GROUPS.get(d, (d,))
        if d == "海鲜" and guess_category(name) == "seafood":
            return "你不吃"
        if any(_hits(name, w) for w in words):
            return "你不吃"
    return None


EQUIP_WORDS = (("空气炸锅", "air_fryer"), ("烤箱", "oven"), ("微波", "microwave"), ("电饭煲", "rice_cooker"),
               ("电饭锅", "rice_cooker"), ("炒锅", "wok"), ("平底锅", "wok"), ("铁锅", "wok"), ("不粘锅", "wok"),
               ("锅", "pot"))
STEP_EQUIP_WORDS = EQUIP_WORDS[:5]  # 步骤里只认这几种强信号，「锅」太泛
# 需要的厨具 → 用户有哪些就算满足
SATISFIED_BY = {"wok": {"wok"}, "pot": {"wok", "mini_pot", "rice_cooker"}, "air_fryer": {"air_fryer"},
                "oven": {"oven"}, "microwave": {"microwave"}, "rice_cooker": {"rice_cooker"}}
NEED_LABEL = {"wok": "炒锅", "pot": "锅", "air_fryer": "空气炸锅", "oven": "烤箱", "microwave": "微波炉",
              "rice_cooker": "电饭煲"}


def required_equipment(recipe: dict) -> set:
    need = set()
    for name in recipe.get("equipment") or []:
        hit = next((code for word, code in EQUIP_WORDS if word in name), None)
        if hit:
            need.add(hit)
    text = recipe["title"] + " ".join(recipe["steps"])
    need.update(code for word, code in STEP_EQUIP_WORDS if word in text)
    return need


def apply_constraints(recipe: dict, prefs: dict, allergies: list) -> tuple[dict | None, str | None]:
    """硬约束：过敏 → 整道剔除；违反饮食方式/忌口的必需料 → 剔除，可省略的料 → 去掉并标注；缺厨具 → 剔除。
    返回 (菜谱或 None, 剔除原因)。"""
    text = recipe["title"] + " " + " ".join(i["name"] for i in recipe["ingredients"])
    for label, words in allergies:
        if any(w in text for w in words):
            return None, f"含过敏原「{label}」"
    kept, stripped = [], []
    for ing in recipe["ingredients"]:
        why = _ingredient_conflict(ing["name"], prefs)
        if why is None:
            kept.append(ing)
        elif ing["optional"]:
            stripped.append(ing["name"])
        else:
            return None, f"用到「{ing['name']}」（{why}）"
    have = set(prefs["equipment"])
    lacking = [NEED_LABEL[n] for n in sorted(required_equipment(recipe)) if not SATISFIED_BY[n] & have]
    if lacking:
        return None, "需要" + "、".join(lacking)
    recipe["ingredients"] = kept
    recipe["stripped"] = stripped
    return recipe, None


def fit_notes(recipe: dict, prefs: dict, kcal_left: int | None = None) -> list[str]:
    """软约束：超出时间、难度、热量的标注出来（排序时排后面），不剔除。"""
    notes = []
    if prefs["minutes"] and recipe["minutes"] > prefs["minutes"]:
        notes.append(f"要 {recipe['minutes']} 分钟，比你设的 {prefs['minutes']} 分钟久")
    if recipe["difficulty"] > difficulty_cap(prefs):
        notes.append("对你来说可能有点难")
    kcal = recipe.get("kcal_per_serving")
    if kcal_left is not None and kcal and kcal > max(0, kcal_left):
        notes.append(f"每份约 {kcal} kcal，超过今天还能吃的 {max(0, kcal_left)} kcal")
    return notes
