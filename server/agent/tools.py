"""Agent 可调用的工具：OpenAI function-calling 格式的定义 + 执行器。

每个执行器返回 (result, cards)：result 回传给模型；cards 是给前端渲染的结构化卡片。
"""
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import health
import kitchen
from health import ValidationError
from rag import glossary as rag_glossary
from rag import prompts as rag_prompts
from rag import retriever as rag_retriever


@dataclass
class ToolContext:
    conn: object
    user_id: int
    now: datetime  # 用户本地时间
    images: object = None      # ImageService；未配置生图时为 None，生图工具对模型不可见
    images_this_turn: int = 0  # 每轮对话最多生成 1 张，控制费用
    citations_this_turn: int = 0  # 本轮已发出的资料编号数，多次检索时编号接着排
    llm: object = None         # 推荐菜谱时再调一次模型（非流式 JSON）
    model: str | None = None
    recipe_limit: int = 20

    @property
    def today(self) -> date:
        return self.now.date()


AT_PARAM = {"type": "string",
            "description": "发生时间，本地时间 YYYY-MM-DDTHH:MM 或 HH:MM（当天）。用户没说就省略，表示现在。"}

TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, properties: dict, required: list[str] | None = None):
    def register(fn):
        TOOLS[name] = {
            "schema": {"type": "function", "function": {
                "name": name, "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required or []}}},
            "run": fn,
        }
        return fn
    return register


IMAGE_TOOLS = {"generate_food_image"}
RAG_TOOLS = {"search_nutrition"}


def schemas(image_enabled: bool = False, rag_enabled: bool = True) -> list[dict]:
    def visible(name):
        if name in IMAGE_TOOLS and not image_enabled:
            return False
        if name in RAG_TOOLS and not rag_enabled:
            return False
        return True
    return [t["schema"] for name, t in TOOLS.items() if visible(name)]


def _record_card(record: dict, action: str = "logged") -> dict:
    return {"type": "record", "action": action, "kind": record["kind"], "record_id": record["id"],
            "title": health.describe_record(record), "at": record["at"]}


def _log(ctx: ToolContext, kind: str, data: dict, at_value=None):
    at = health.parse_at(at_value, ctx.now)
    record = health.add_record(ctx.conn, ctx.user_id, kind, data, at, source="agent")
    summary = health.daily_summary(ctx.conn, ctx.user_id, at.date(), ctx.today)
    totals = summary["totals"]
    result = {"ok": True, "record_id": record["id"], "saved": health.describe_record(record),
              "day": at.date().isoformat(),
              "day_totals": {"calories_in": totals["calories_in"], "water_ml": totals["water_ml"],
                             "exercise_min": totals["exercise_min"], "sleep_hours": totals["sleep_hours"]},
              "targets": {k: summary["targets"][k] for k in ("calories", "water_ml", "exercise_min", "sleep_hours")},
              "remaining_calories": summary["remaining_calories"]}
    if kind == "meal":
        result["estimated_items"] = record["data"]["items"]
    return result, [_record_card(record)]


FOOD_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "食物名，如 牛肉面"},
        "amount": {"type": "string", "description": "份量，如 1碗(约500g)"},
        "calories": {"type": "number", "description": "估算热量 kcal"},
        "protein": {"type": "number", "description": "蛋白质 g"},
        "carbs": {"type": "number", "description": "碳水 g"},
        "fat": {"type": "number", "description": "脂肪 g"},
    },
    "required": ["name", "calories"],
}


@tool("log_meal", "记录一餐饮食。根据用户描述按中国常见份量估算每样食物的热量与三大营养素，直接记录，不必追问。",
      {"meal_type": {"type": "string", "enum": list(health.MEAL_TYPES), "description": "餐次"},
       "items": {"type": "array", "items": FOOD_ITEM},
       "note": {"type": "string"}, "at": AT_PARAM},
      ["meal_type", "items"])
def log_meal(ctx, args):
    return _log(ctx, "meal", args, args.get("at"))


@tool("log_water", "记录饮水（含茶、咖啡等无糖饮品的水量）。一杯约 250ml，一瓶矿泉水约 550ml。",
      {"ml": {"type": "integer"}, "at": AT_PARAM}, ["ml"])
def log_water(ctx, args):
    return _log(ctx, "water", args, args.get("at"))


@tool("log_exercise", "记录一次运动。calories 可省略，系统会按强度和体重估算。",
      {"activity": {"type": "string", "description": "运动项目，如 跑步、瑜伽、快走"},
       "minutes": {"type": "integer"},
       "intensity": {"type": "string", "enum": list(health.INTENSITIES)},
       "calories": {"type": "integer", "description": "消耗热量 kcal（用户手环给出时填写）"},
       "note": {"type": "string"}, "at": AT_PARAM},
      ["activity", "minutes"])
def log_exercise(ctx, args):
    return _log(ctx, "exercise", args, args.get("at"))


@tool("log_sleep", "记录一次睡眠，计入醒来那天。用户说“昨晚睡了7小时”就记在今天。",
      {"hours": {"type": "number"}, "quality": {"type": "integer", "description": "主观质量 1-5"},
       "bedtime": {"type": "string", "description": "入睡时间 HH:MM"},
       "note": {"type": "string"}, "at": AT_PARAM},
      ["hours"])
def log_sleep(ctx, args):
    return _log(ctx, "sleep", args, args.get("at"))


@tool("log_weight", "记录体重（kg）。用户说斤要除以 2 换算成 kg。",
      {"kg": {"type": "number"}, "body_fat": {"type": "number", "description": "体脂率 %"}, "at": AT_PARAM},
      ["kg"])
def log_weight(ctx, args):
    return _log(ctx, "weight", args, args.get("at"))


@tool("log_mood", "记录心情与身体感受。score: 1 很糟 … 5 很好。",
      {"score": {"type": "integer"}, "symptoms": {"type": "array", "items": {"type": "string"},
                                                    "description": "身体不适，如 头痛、胃胀"},
       "note": {"type": "string"}, "at": AT_PARAM},
      ["score"])
def log_mood(ctx, args):
    return _log(ctx, "mood", args, args.get("at"))


@tool("delete_record", "删除一条记录（用户说记错了、要撤销时）。record_id 来自之前的工具结果或 list_records。",
      {"record_id": {"type": "integer"}}, ["record_id"])
def delete_record(ctx, args):
    record_id = int(args.get("record_id") or 0)
    row = ctx.conn.execute("SELECT * FROM records WHERE id=? AND user_id=?", (record_id, ctx.user_id)).fetchone()
    if not row:
        return {"ok": False, "error": "找不到这条记录"}, []
    from db import record_to_dict
    record = record_to_dict(row)
    health.delete_record(ctx.conn, ctx.user_id, record_id)
    return {"ok": True, "deleted": health.describe_record(record)}, [_record_card(record, "deleted")]


@tool("get_day_summary", "查看某天的摄入、饮水、运动、睡眠汇总与目标对比，以及当天所有记录和习惯打卡。",
      {"day": {"type": "string", "description": "YYYY-MM-DD，省略为今天"}})
def get_day_summary(ctx, args):
    day = health.parse_day(args.get("day"), ctx.today)
    summary = health.daily_summary(ctx.conn, ctx.user_id, day, ctx.today)
    summary["records"] = [{"id": r["id"], "at": r["at"], "text": health.describe_record(r)}
                          for r in summary["records"]]
    return summary, []


@tool("get_trends", "查看最近 N 天的逐日数据（热量、蛋白质、饮水、运动、睡眠、体重、心情），用于周报和趋势分析。",
      {"days": {"type": "integer", "description": "7-90，默认 7"}})
def get_trends(ctx, args):
    days = max(2, min(90, int(args.get("days") or 7)))
    series = health.trends(ctx.conn, ctx.user_id, ctx.today, days)
    logged = [d for d in series if d["count"]]
    def avg(key):
        values = [d[key] for d in logged if d[key]]
        return round(sum(values) / len(values), 1) if values else None
    weights = [d["weight_kg"] for d in series if d["weight_kg"]]
    overview = {"days": days, "days_with_records": len(logged),
                "avg_calories_in": avg("calories_in"), "avg_water_ml": avg("water_ml"),
                "avg_exercise_min": avg("exercise_min"), "avg_sleep_hours": avg("sleep_hours"),
                "avg_mood": avg("mood"),
                "weight_change_kg": round(weights[-1] - weights[0], 1) if len(weights) >= 2 else None}
    return {"overview": overview, "series": series}, [{"type": "trend", "days": days}]


@tool("list_records", "按类型列出最近的记录（含 id），用于回顾或找到要删除的记录。",
      {"kind": {"type": "string", "enum": list(health.KINDS)},
       "days": {"type": "integer", "description": "回看天数，默认 3"}})
def list_records_tool(ctx, args):
    days = max(1, min(60, int(args.get("days") or 3)))
    rows = health.list_records(ctx.conn, ctx.user_id, ctx.today - timedelta(days=days - 1), ctx.today,
                               args.get("kind") or None)
    return {"records": [{"id": r["id"], "at": r["at"], "text": health.describe_record(r)} for r in rows[:60]]}, []


@tool("get_profile", "读取用户健康档案（身体数据、目标、饮食偏好、过敏、健康状况）和计算出的每日目标。", {})
def get_profile(ctx, args):
    profile = health.get_profile(ctx.conn, ctx.user_id)
    return {"profile": profile, "bmi": health.bmi(profile),
            "targets": health.compute_targets(profile, ctx.today)}, []


@tool("update_profile", "更新健康档案。只传用户明确告诉你的字段。",
      {"sex": {"type": "string", "enum": ["male", "female"]},
       "birth_year": {"type": "integer"}, "height_cm": {"type": "number"},
       "weight_kg": {"type": "number"}, "target_weight_kg": {"type": "number"},
       "activity_level": {"type": "string", "enum": list(health.ACTIVITY_LEVELS)},
       "goal": {"type": "string", "enum": list(health.GOALS)},
       "diet_preferences": {"type": "string", "description": "饮食偏好，如 不吃辣、素食"},
       "allergies": {"type": "string"}, "conditions": {"type": "string", "description": "已知健康状况"}})
def update_profile(ctx, args):
    changes = {k: v for k, v in args.items() if k in health.PROFILE_FIELDS}
    if not changes:
        return {"ok": False, "error": "没有可更新的字段"}, []
    profile = health.save_profile(ctx.conn, ctx.user_id, changes)
    targets = health.compute_targets(profile, ctx.today)
    return ({"ok": True, "profile": profile, "targets": targets},
            [{"type": "profile", "title": "已更新健康档案", "fields": list(changes),
              "calories": targets["calories"], "water_ml": targets["water_ml"]}])


@tool("add_habit", "为用户创建一个每日习惯（如 晚上11点前睡觉、每天两份蔬菜）。习惯要具体、可打卡。",
      {"name": {"type": "string", "description": "不超过 20 字"}, "note": {"type": "string"}}, ["name"])
def add_habit(ctx, args):
    habit = health.add_habit(ctx.conn, ctx.user_id, args.get("name"), args.get("note", ""))
    return {"ok": True, "habit": habit}, [{"type": "habit", "action": "created", "title": habit["name"]}]


@tool("check_habit", "为习惯打卡或取消打卡。habit_id 来自 get_day_summary 的 habits。",
      {"habit_id": {"type": "integer"}, "done": {"type": "boolean"},
       "day": {"type": "string", "description": "YYYY-MM-DD，省略为今天"}},
      ["habit_id"])
def check_habit(ctx, args):
    day = health.parse_day(args.get("day"), ctx.today)
    done = args.get("done", True) is not False
    habit = ctx.conn.execute("SELECT name FROM habits WHERE id=? AND user_id=?",
                             (int(args.get("habit_id") or 0), ctx.user_id)).fetchone()
    if not habit or not health.set_habit_check(ctx.conn, ctx.user_id, int(args["habit_id"]), day, done):
        return {"ok": False, "error": "找不到这个习惯"}, []
    return ({"ok": True, "habit": habit["name"], "done": done, "day": day.isoformat()},
            [{"type": "habit", "action": "checked" if done else "unchecked", "title": habit["name"]}])


@tool("generate_food_image",
      "为你推荐的菜品生成一张成品示意图（后台生成，用户会在卡片里看到）。"
      "只在给出具体菜谱或一餐搭配建议、或用户明确想看图时调用；记录类消息不要调用；每轮最多一次。",
      {"title": {"type": "string", "description": "菜名，不超过 15 字，如 香煎鸡胸配西兰花"},
       "description": {"type": "string", "description":
                       "画面描述，用英文写（生图模型对英文理解准得多，中文菜名常被画错）：菜的英文名或拼音、"
                       "主料的形状颜色质感、份量摆盘；容易画错的写明没有什么（如 no noodles, no meat）。不写风格词"}},
      ["title", "description"])
def generate_food_image(ctx, args):
    if ctx.images is None:
        return {"ok": False, "error": "没有配置生图服务"}, []
    if ctx.images_this_turn >= 1:
        return {"ok": False, "error": "这一轮已经生成过图片了"}, []
    image = ctx.images.start(ctx.conn, ctx.user_id, args.get("title"), args.get("description"))
    ctx.images_this_turn += 1
    return ({"ok": True, "image_id": image["id"], "status": "generating",
             "note": "图片正在后台生成，会直接显示在卡片里；回复里不要写链接，也不要描述图片已生成完毕"},
            [{"type": "image", "image_id": image["id"], "title": image["title"]}])


@tool("search_nutrition", rag_glossary.tool_description(),
      {"queries": {"type": "array", "items": {"type": "string"},
                   "description": "1-3 种不同说法的营养问题。把用户的口语换成知识库用词，"
                                  "并尽量多给一两种同义问法（如用户问「西红柿补铁吗」，"
                                  "可给 [「西红柿补铁吗」,「番茄补铁」,「深色蔬菜补铁」]），"
                                  "系统会融合各说法的检索结果。至少 1 个。"}},
      ["queries"])
def search_nutrition(ctx, args):
    # 兼容老调用：单字符串 query 当作只有一个说法的数组，离线评测/旧测试都不受影响。
    raw = args.get("queries")
    if raw is None:
        raw = args.get("query")
    if isinstance(raw, str):
        queries = [raw]
    elif isinstance(raw, list):
        queries = [str(q).strip() for q in raw if str(q).strip()]
    else:
        queries = []
    queries = [q for q in queries if q]
    if not queries:
        return {"ok": False, "error": "查询内容为空"}, []
    query = queries[0]  # 回显/卡片用第一个说法
    hits = rag_retriever.search_multi(queries)
    # 检索器每次都从 [1] 编号；同一轮第二次检索要接着上一批往后排，
    # 否则回答里的 [1] 会同时对应两条出处，引用自检也分不清。
    offset = ctx.citations_this_turn
    hits = [{**hit, "citation": offset + i} for i, hit in enumerate(hits, start=1)]
    ctx.citations_this_turn += len(hits)
    # 给模型：带 [n] 编号的资料 + 引用规则（无命中时是拒答约束）
    context = rag_prompts.build_rag_context(hits, query=query)
    # 给前端：引用卡片数据（阶段 2 渲染），同时把编号清单回传给模型便于核对
    payload = rag_prompts.sources_payload(hits, query=query)
    result = {
        "ok": True,
        "query": query,
        "hit_count": len(hits),
        "citation_numbers": [s["citation"] for s in payload["sources"]],
        "reference_material": context,
    }
    cards = [{"type": "sources", **payload}]
    return result, cards


# ---------------------------------------------------------------- 冰箱与菜谱

PANTRY_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "食材通用名，如 番茄、鸡蛋、五花肉"},
        "quantity": {"type": "number", "description": "数量，用户没说就省略"},
        "unit": {"type": "string", "description": "单位，如 个、斤、g、盒"},
        "storage": {"type": "string", "enum": list(kitchen.STORAGES), "description": "冷藏/冷冻/常温，没说就省略"},
        "expires_on": {"type": "string", "description": "到期日 YYYY-MM-DD，用户明确说了才填"},
    },
    "required": ["name"],
}


def _pantry_brief(items: list[dict]) -> list[str]:
    return [kitchen.describe_item(i) + f" · {i['storage_label']}" for i in items]


@tool("list_pantry", "查看用户冰箱里现在有哪些食材（按到期从近到远），含剩余天数。", {})
def list_pantry(ctx, args):
    items = kitchen.list_pantry(ctx.conn, ctx.user_id, ctx.today)
    return {"ok": True, "count": len(items), "items": _pantry_brief(items)}, []


@tool("add_pantry_items", "把用户买了、冰箱里有的食材加进库存。数量不知道就不填，到期日不知道就不填（系统会按常识估算）。",
      {"items": {"type": "array", "items": PANTRY_ITEM}}, ["items"])
def add_pantry_items(ctx, args):
    items = kitchen.add_items(ctx.conn, ctx.user_id, args.get("items"), ctx.today, source="agent")
    added = [kitchen.describe_item(i) for i in items if not i["merged"]]
    merged = [kitchen.describe_item(i) for i in items if i["merged"]]
    return ({"ok": True,
             "newly_added": added,  # 之前冰箱里没有，这次新放进去的（括号里是现在的数量和剩余天数）
             "merged_into_existing": merged,  # 冰箱里本来就有、这次合并后的总量
             "note_for_reply": "只按上面两项如实告诉用户放进去了什么；newly_added 里的东西之前冰箱里没有，"
                               "不要说「之前那盒」「原来的」，也不要自己推算总数。"},
            [{"type": "pantry", "action": "added", "names": [i["name"] for i in items]}])


@tool("remove_pantry_items", "用户说某些食材吃完了、用完了或扔掉了时，从库存里移除。",
      {"names": {"type": "array", "items": {"type": "string"}},
       "reason": {"type": "string", "enum": ["used", "discarded"], "description": "used 用完了 / discarded 扔掉了"}},
      ["names"])
def remove_pantry_items(ctx, args):
    reason = args.get("reason") or "used"
    pantry = kitchen.list_pantry(ctx.conn, ctx.user_id, ctx.today)
    removed, not_found = [], []
    for name in args.get("names") or []:
        hit = next((p for p in pantry if kitchen.names_match(str(name), p["name"]) and p["name"] not in removed), None)
        if hit and kitchen.remove_item(ctx.conn, ctx.user_id, hit["id"], reason):
            removed.append(hit["name"])
        else:
            not_found.append(str(name))
    cards = [{"type": "pantry", "action": "removed", "names": removed}] if removed else []
    return {"ok": True, "removed": removed, "not_found": not_found}, cards


@tool("recommend_recipes",
      "根据冰箱现有食材推荐 3 道今天能做的菜（优先现在就能做、用掉快过期的）。用户问「吃什么」「冰箱里这些能做什么」时调用。"
      "结果会以卡片展示给用户，卡片里有完整用料和步骤。",
      {"note": {"type": "string", "description": "用户的额外要求，如 想吃辣的、两个人吃、15 分钟内"}})
def recommend_recipes(ctx, args):
    result = kitchen.recommend(ctx.conn, ctx.llm, ctx.model, ctx.user_id, ctx.now,
                               str(args.get("note") or ""), ctx.recipe_limit)
    brief = [{"title": r["title"], "minutes": r["minutes"], "summary": r["summary"],
              "missing": r["missing"], "uses_expiring": r["uses_expiring"],
              "not_fitting_user_settings": r.get("fit") or [], "removed_ingredients": r.get("stripped") or []}
             for r in result["recipes"]]
    card = {"type": "recipes", "recipes": [
        {"id": r["id"], "title": r["title"], "minutes": r["minutes"], "difficulty": r["difficulty"],
         "kcal_per_serving": r["kcal_per_serving"], "missing": r["missing"], "uses_expiring": r["uses_expiring"],
         "summary": r["summary"], "fit": r.get("fit") or [], "stripped": r.get("stripped") or []}
        for r in result["recipes"]]}
    return {"ok": True, "recipes": brief, "dropped": result["dropped"],
            "note_for_reply": "卡片已展示完整做法，回复里每道菜一句话即可，不要重复用料和步骤。"}, [card]


def execute(ctx: ToolContext, name: str, raw_args: str):
    """执行工具。所有异常都转成给模型看的错误结果，绝不让一次工具失败打断对话。"""
    entry = TOOLS.get(name)
    if entry is None:
        return {"ok": False, "error": f"未知工具 {name}"}, []
    try:
        args = json.loads(raw_args or "{}")
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:
        return {"ok": False, "error": "参数不是合法 JSON 对象"}, []
    try:
        result, cards = entry["run"](ctx, args)
        ctx.conn.commit()
        return result, cards
    except ValidationError as exc:
        ctx.conn.rollback()
        return {"ok": False, "error": str(exc)}, []
