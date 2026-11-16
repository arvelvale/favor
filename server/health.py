"""健康领域逻辑：目标计算、记录校验、日汇总、趋势。REST 接口与 agent 工具共用这一层。"""
import json
from datetime import date, datetime, timedelta

from db import record_to_dict

KINDS = ("meal", "water", "exercise", "sleep", "weight", "mood")
MEAL_TYPES = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}
INTENSITIES = {"low": "轻松", "moderate": "中等", "high": "高强度"}
# 代谢当量（MET）：消耗 kcal = MET × 体重kg × 小时数
INTENSITY_MET = {"low": 3.5, "moderate": 5.0, "high": 8.0}

ACTIVITY_LEVELS = {
    "sedentary": ("久坐少动", 1.2),
    "light": ("轻度活动", 1.375),
    "moderate": ("中度活动", 1.55),
    "active": ("高度活动", 1.725),
    "very_active": ("体力劳动/专业训练", 1.9),
}
# 目标对应的热量系数与蛋白质系数。
# 设计值：减脂 = 15% 热量缺口 → 代码 TDEE × 0.85；增肌 = 10% 热量盈余 → TDEE × 1.10。
GOALS = {
    "lose": ("减脂", 0.85, 1.6),
    "maintain": ("保持健康", 1.0, 1.2),
    "gain": ("增肌", 1.10, 1.8),
    "sleep": ("改善睡眠", 1.0, 1.2),
}
DEFAULT_TARGETS = {"calories": 2000, "water_ml": 2000, "exercise_min": 30, "sleep_hours": 8.0, "protein_g": None}

PROFILE_FIELDS = ("sex", "birth_year", "height_cm", "weight_kg", "target_weight_kg", "activity_level",
                  "goal", "diet_preferences", "allergies", "conditions")


class ValidationError(ValueError):
    """面向用户（和模型）的中文校验错误。"""


# ---------------------------------------------------------------- 工具函数

def _num(value, name, lo, hi, *, integer=False, required=True):
    if value is None or value == "":
        if required:
            raise ValidationError(f"缺少「{name}」")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"「{name}」需要是数字") from None
    if not lo <= number <= hi:
        raise ValidationError(f"「{name}」应在 {lo}–{hi} 之间")
    return int(round(number)) if integer else round(number, 1)


def _text(value, limit=200):
    return str(value or "").strip()[:limit]


def parse_day(value, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValidationError("日期格式应为 YYYY-MM-DD") from None


def parse_at(value, now: datetime) -> datetime:
    """记录时间：缺省为当前本地时间；可只给日期或 HH:MM。不允许记到未来超过 1 小时。"""
    if not value:
        return now
    text = str(value).strip()
    try:
        if len(text) <= 5 and ":" in text:
            hh, mm = text.split(":")
            moment = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        elif len(text) == 10:
            moment = datetime.fromisoformat(text).replace(hour=now.hour, minute=now.minute)
        else:
            moment = datetime.fromisoformat(text[:16])
    except ValueError:
        raise ValidationError("时间格式应为 HH:MM 或 YYYY-MM-DDTHH:MM") from None
    if moment - now > timedelta(hours=1):
        raise ValidationError("不能记录未来的时间")
    return moment.replace(second=0, microsecond=0, tzinfo=None)


# ---------------------------------------------------------------- 档案与目标

def normalize_profile(data: dict) -> dict:
    out = {}
    if "sex" in data:
        sex = data["sex"]
        if sex not in (None, "", "male", "female"):
            raise ValidationError("性别只能是 male / female")
        out["sex"] = sex or None
    if "birth_year" in data:
        out["birth_year"] = _num(data["birth_year"], "出生年份", 1920, date.today().year - 10,
                                 integer=True, required=False)
    if "height_cm" in data:
        out["height_cm"] = _num(data["height_cm"], "身高(cm)", 100, 230, required=False)
    if "weight_kg" in data:
        out["weight_kg"] = _num(data["weight_kg"], "体重(kg)", 25, 300, required=False)
    if "target_weight_kg" in data:
        out["target_weight_kg"] = _num(data["target_weight_kg"], "目标体重(kg)", 25, 300, required=False)
    if "activity_level" in data:
        if data["activity_level"] not in (None, "", *ACTIVITY_LEVELS):
            raise ValidationError("活动水平取值无效")
        out["activity_level"] = data["activity_level"] or None
    if "goal" in data:
        if data["goal"] not in (None, "", *GOALS):
            raise ValidationError("目标取值无效")
        out["goal"] = data["goal"] or None
    for key in ("diet_preferences", "allergies", "conditions"):
        if key in data:
            out[key] = _text(data[key], 300)
    return out


def compute_targets(profile: dict | None, today: date) -> dict:
    """依据 Mifflin-St Jeor 公式估算每日目标；资料不全时给通用默认值并列出缺项。"""
    p = profile or {}
    needed = {"sex": "性别", "birth_year": "出生年份", "height_cm": "身高", "weight_kg": "体重",
              "activity_level": "活动水平"}
    missing = [label for key, label in needed.items() if not p.get(key)]
    targets = dict(DEFAULT_TARGETS)
    targets.update(missing=missing, complete=not missing, bmr=None, tdee=None)

    weight = p.get("weight_kg")
    if weight:
        # 饮水：33 ml/kg，夹在 1500–3500 ml
        targets["water_ml"] = int(min(3500, max(1500, round(weight * 33 / 50) * 50)))
        goal = GOALS.get(p.get("goal") or "maintain", GOALS["maintain"])
        targets["protein_g"] = round(weight * goal[2])

    age = today.year - p["birth_year"] if p.get("birth_year") else None
    if age is not None and age < 18:
        targets["sleep_hours"] = 9.0

    if not missing:
        base = 10 * weight + 6.25 * p["height_cm"] - 5 * age
        bmr = base + 5 if p["sex"] == "male" else base - 161
        tdee = bmr * ACTIVITY_LEVELS[p["activity_level"]][1]
        goal = GOALS.get(p.get("goal") or "maintain", GOALS["maintain"])
        # 安全下限：不低于基础代谢，且女性 ≥1200、男性 ≥1500 kcal
        floor = max(bmr, 1500 if p["sex"] == "male" else 1200)
        targets.update(bmr=round(bmr), tdee=round(tdee),
                       calories=int(round(max(floor, tdee * goal[1]) / 10) * 10))
    return targets


def bmi(profile: dict | None):
    p = profile or {}
    if p.get("height_cm") and p.get("weight_kg"):
        return round(p["weight_kg"] / (p["height_cm"] / 100) ** 2, 1)
    return None


def get_profile(conn, user_id: int) -> dict:
    row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return {key: None for key in PROFILE_FIELDS} | {"diet_preferences": "", "allergies": "", "conditions": ""}
    return {key: row[key] for key in PROFILE_FIELDS}


def save_profile(conn, user_id: int, changes: dict) -> dict:
    clean = normalize_profile(changes)
    current = get_profile(conn, user_id)
    current.update(clean)
    cols = ", ".join(PROFILE_FIELDS)
    marks = ", ".join("?" for _ in PROFILE_FIELDS)
    updates = ", ".join(f"{k}=excluded.{k}" for k in PROFILE_FIELDS)
    conn.execute(
        f"INSERT INTO profiles (user_id, {cols}) VALUES (?, {marks}) "
        f"ON CONFLICT(user_id) DO UPDATE SET {updates}, updated_at=datetime('now')",
        (user_id, *[current[k] for k in PROFILE_FIELDS]))
    return current


# ---------------------------------------------------------------- 记录

def normalize_record(kind: str, data: dict, profile: dict | None = None) -> dict:
    if kind not in KINDS:
        raise ValidationError(f"未知记录类型：{kind}")
    data = data or {}
    if kind == "meal":
        meal_type = data.get("meal_type") or "snack"
        if meal_type not in MEAL_TYPES:
            raise ValidationError("餐次只能是 breakfast / lunch / dinner / snack")
        raw_items = data.get("items") or []
        if not isinstance(raw_items, list) or not raw_items:
            raise ValidationError("至少需要一项食物")
        items = []
        for raw in raw_items[:20]:
            name = _text(raw.get("name"), 60)
            if not name:
                raise ValidationError("食物名称不能为空")
            items.append({
                "name": name,
                "amount": _text(raw.get("amount"), 40),
                "calories": _num(raw.get("calories"), f"{name}的热量", 0, 5000, integer=True),
                "protein": _num(raw.get("protein"), f"{name}的蛋白质", 0, 500, required=False) or 0,
                "carbs": _num(raw.get("carbs"), f"{name}的碳水", 0, 1000, required=False) or 0,
                "fat": _num(raw.get("fat"), f"{name}的脂肪", 0, 500, required=False) or 0,
            })
        totals = {k: round(sum(i[k] for i in items), 1) for k in ("calories", "protein", "carbs", "fat")}
        totals["calories"] = int(totals["calories"])
        return {"meal_type": meal_type, "items": items, "note": _text(data.get("note")), **totals}
    if kind == "water":
        return {"ml": _num(data.get("ml"), "饮水量(ml)", 10, 5000, integer=True)}
    if kind == "exercise":
        activity = _text(data.get("activity"), 40)
        if not activity:
            raise ValidationError("请说明运动项目")
        minutes = _num(data.get("minutes"), "运动时长(分钟)", 1, 600, integer=True)
        intensity = data.get("intensity") or "moderate"
        if intensity not in INTENSITIES:
            raise ValidationError("强度只能是 low / moderate / high")
        calories = _num(data.get("calories"), "消耗热量", 0, 5000, integer=True, required=False)
        if calories is None:
            weight = (profile or {}).get("weight_kg") or 60
            calories = int(round(INTENSITY_MET[intensity] * weight * minutes / 60))
        return {"activity": activity, "minutes": minutes, "intensity": intensity,
                "calories": calories, "note": _text(data.get("note"))}
    if kind == "sleep":
        return {"hours": _num(data.get("hours"), "睡眠时长(小时)", 0.5, 16),
                "quality": _num(data.get("quality"), "睡眠质量(1-5)", 1, 5, integer=True, required=False),
                "bedtime": _text(data.get("bedtime"), 5), "note": _text(data.get("note"))}
    if kind == "weight":
        return {"kg": _num(data.get("kg"), "体重(kg)", 25, 300),
                "body_fat": _num(data.get("body_fat"), "体脂率(%)", 3, 70, required=False)}
    # mood
    symptoms = data.get("symptoms") or []
    if not isinstance(symptoms, list):
        symptoms = [symptoms]
    return {"score": _num(data.get("score"), "心情评分(1-5)", 1, 5, integer=True),
            "symptoms": [_text(s, 30) for s in symptoms if _text(s, 30)][:10],
            "note": _text(data.get("note"), 300)}


def add_record(conn, user_id: int, kind: str, data: dict, at: datetime, source: str = "manual") -> dict:
    profile = get_profile(conn, user_id)
    clean = normalize_record(kind, data, profile)
    cur = conn.execute(
        "INSERT INTO records (user_id, kind, day, at, data, source) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, kind, at.date().isoformat(), at.isoformat(timespec="minutes"),
         json.dumps(clean, ensure_ascii=False), source))
    if kind == "weight":
        # 最新体重同步进档案，目标计算随之更新
        # 只有这条是时间上最新的体重才同步（补录旧体重不覆盖档案）
        latest = conn.execute("SELECT id FROM records WHERE user_id=? AND kind='weight' "
                              "ORDER BY at DESC, id DESC LIMIT 1", (user_id,)).fetchone()
        if latest and latest["id"] == cur.lastrowid:
            save_profile(conn, user_id, {"weight_kg": clean["kg"]})
    row = conn.execute("SELECT * FROM records WHERE id = ?", (cur.lastrowid,)).fetchone()
    return record_to_dict(row)


def list_records(conn, user_id: int, start: date, end: date, kind: str | None = None) -> list[dict]:
    sql = "SELECT * FROM records WHERE user_id = ? AND day BETWEEN ? AND ?"
    args = [user_id, start.isoformat(), end.isoformat()]
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    sql += " ORDER BY at DESC, id DESC LIMIT 500"
    return [record_to_dict(r) for r in conn.execute(sql, args).fetchall()]


def delete_record(conn, user_id: int, record_id: int) -> bool:
    cur = conn.execute("DELETE FROM records WHERE id = ? AND user_id = ?", (record_id, user_id))
    return cur.rowcount > 0


def describe_record(record: dict) -> str:
    """一句话描述，给前端卡片和模型回看用。"""
    d, kind = record["data"], record["kind"]
    if kind == "meal":
        names = "、".join(i["name"] for i in d["items"])
        return f"{MEAL_TYPES[d['meal_type']]} · {names} · {d['calories']} kcal"
    if kind == "water":
        return f"饮水 {d['ml']} ml"
    if kind == "exercise":
        return f"{d['activity']} {d['minutes']} 分钟 · {INTENSITIES[d['intensity']]} · 约 {d['calories']} kcal"
    if kind == "sleep":
        quality = f" · 质量 {d['quality']}/5" if d.get("quality") else ""
        return f"睡眠 {d['hours']} 小时{quality}"
    if kind == "weight":
        return f"体重 {d['kg']} kg"
    return f"心情 {d['score']}/5" + (f" · {'、'.join(d['symptoms'])}" if d.get("symptoms") else "")


# ---------------------------------------------------------------- 汇总与趋势

def _aggregate(records: list[dict]) -> dict:
    agg = {"calories_in": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "water_ml": 0,
           "exercise_min": 0, "exercise_kcal": 0, "sleep_hours": 0.0, "weight_kg": None, "mood": None}
    moods, weight_at = [], ""
    for r in records:
        d = r["data"]
        if r["kind"] == "meal":
            agg["calories_in"] += d["calories"]
            for k in ("protein", "carbs", "fat"):
                agg[k] += d.get(k, 0)
        elif r["kind"] == "water":
            agg["water_ml"] += d["ml"]
        elif r["kind"] == "exercise":
            agg["exercise_min"] += d["minutes"]
            agg["exercise_kcal"] += d["calories"]
        elif r["kind"] == "sleep":
            agg["sleep_hours"] += d["hours"]
        elif r["kind"] == "weight" and r["at"] >= weight_at:
            agg["weight_kg"], weight_at = d["kg"], r["at"]
        elif r["kind"] == "mood":
            moods.append(d["score"])
    for k in ("protein", "carbs", "fat", "sleep_hours"):
        agg[k] = round(agg[k], 1)
    agg["mood"] = round(sum(moods) / len(moods), 1) if moods else None
    return agg


def daily_summary(conn, user_id: int, day: date, today: date) -> dict:
    profile = get_profile(conn, user_id)
    records = list_records(conn, user_id, day, day)
    targets = compute_targets(profile, today)
    agg = _aggregate(records)
    if agg["weight_kg"] is None:
        last = conn.execute("SELECT data, day FROM records WHERE user_id=? AND kind='weight' AND day<=? "
                            "ORDER BY at DESC, id DESC LIMIT 1", (user_id, day.isoformat())).fetchone()
        agg["last_weight"] = {"kg": json.loads(last["data"])["kg"], "day": last["day"]} if last else None
    habits = list_habits(conn, user_id, day)
    return {
        "day": day.isoformat(),
        "totals": agg,
        "targets": targets,
        "remaining_calories": targets["calories"] - agg["calories_in"] + agg["exercise_kcal"],
        "records": records,
        "habits": habits,
    }


def trends(conn, user_id: int, end: date, days: int) -> list[dict]:
    start = end - timedelta(days=days - 1)
    by_day: dict[str, list] = {}
    for r in list_records(conn, user_id, start, end):
        by_day.setdefault(r["day"], []).append(r)
    series = []
    for i in range(days):
        key = (start + timedelta(days=i)).isoformat()
        series.append({"day": key, **_aggregate(by_day.get(key, [])), "count": len(by_day.get(key, []))})
    return series


# ---------------------------------------------------------------- 习惯

def list_habits(conn, user_id: int, day: date) -> list[dict]:
    rows = conn.execute("SELECT * FROM habits WHERE user_id=? AND archived=0 ORDER BY id", (user_id,)).fetchall()
    week_start = day - timedelta(days=6)
    out = []
    for row in rows:
        checks = {r["day"] for r in conn.execute(
            "SELECT day FROM habit_checks WHERE habit_id=? AND day BETWEEN ? AND ?",
            (row["id"], week_start.isoformat(), day.isoformat()))}
        out.append({"id": row["id"], "name": row["name"], "note": row["note"],
                    "done": day.isoformat() in checks, "week_count": len(checks)})
    return out


def add_habit(conn, user_id: int, name: str, note: str = "") -> dict:
    name = _text(name, 40)
    if not name:
        raise ValidationError("习惯名称不能为空")
    count = conn.execute("SELECT COUNT(*) FROM habits WHERE user_id=? AND archived=0", (user_id,)).fetchone()[0]
    if count >= 12:
        raise ValidationError("同时进行的习惯最多 12 个，先完成或删除一些吧")
    dup = conn.execute("SELECT id FROM habits WHERE user_id=? AND archived=0 AND name=?", (user_id, name)).fetchone()
    if dup:
        raise ValidationError(f"已经有「{name}」这个习惯了")
    cur = conn.execute("INSERT INTO habits (user_id, name, note) VALUES (?, ?, ?)", (user_id, name, _text(note)))
    return {"id": cur.lastrowid, "name": name, "note": _text(note), "done": False, "week_count": 0}


def set_habit_check(conn, user_id: int, habit_id: int, day: date, done: bool) -> bool:
    owner = conn.execute("SELECT id FROM habits WHERE id=? AND user_id=?", (habit_id, user_id)).fetchone()
    if not owner:
        return False
    if done:
        conn.execute("INSERT OR IGNORE INTO habit_checks (habit_id, day) VALUES (?, ?)", (habit_id, day.isoformat()))
    else:
        conn.execute("DELETE FROM habit_checks WHERE habit_id=? AND day=?", (habit_id, day.isoformat()))
    return True


def archive_habit(conn, user_id: int, habit_id: int) -> bool:
    cur = conn.execute("UPDATE habits SET archived=1 WHERE id=? AND user_id=?", (habit_id, user_id))
    return cur.rowcount > 0
