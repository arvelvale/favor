"""新手引导（第 3 期）：聚焦式 4 步引导的状态、上手进度清单、情境提示。

原则：
- 进度尽量从真实数据推导（冰箱里放过几样、推荐过没有、做过/收藏过没有），换设备也能接着来，
  也不会出现「做过了引导还说没做」。只有推导不出来的才单独存：是否打开过菜谱、引导是否跳过/完成、
  看过哪些提示、是否关掉了清单。
- 情境提示每条只出现一次（看过就记下），条件由服务端判断，文案在前端。
"""
import json
from datetime import date, datetime

import kitchen
import prefs as prefs_mod
from health import ValidationError

TOUR_STATES = ("active", "skipped", "done")
PANTRY_GOAL = 3  # 第 1 步：冰箱里至少放过 3 样

# 情境提示（每条一次）。顺序即优先级
TIP_IDS = ("expiring", "ask_household", "ask_skill", "ask_minutes", "ask_equipment", "ask_staples", "ask_taste",
           "ask_goals", "expiry_dates", "health")
HEALTH_TIP_AFTER_DAYS = 7


def _row(conn, user_id: int):
    return conn.execute("SELECT * FROM onboarding WHERE user_id=?", (user_id,)).fetchone()


def _count(conn, sql: str, user_id: int) -> int:
    return conn.execute(sql, (user_id,)).fetchone()[0]


def steps(conn, user_id: int, opened_recipe: bool) -> dict:
    """4 步引导里每一步是否完成（从真实数据推导）。"""
    return {
        "pantry": _count(conn, "SELECT COUNT(*) FROM pantry_items WHERE user_id=?", user_id) >= PANTRY_GOAL,
        "recommend": _count(conn, "SELECT COUNT(*) FROM recipes WHERE user_id=?", user_id) > 0,
        "open": opened_recipe,
        "cook": (_count(conn, "SELECT COUNT(*) FROM cook_logs WHERE user_id=?", user_id) > 0
                 or _count(conn, "SELECT COUNT(*) FROM recipes WHERE user_id=? AND saved=1", user_id) > 0),
    }


def _ensure(conn, user_id: int):
    """第一次读取时建行。已经做过菜的老用户直接算引导完成，不再打扰。"""
    row = _row(conn, user_id)
    if row is None:
        veteran = _count(conn, "SELECT COUNT(*) FROM cook_logs WHERE user_id=?", user_id) > 0
        conn.execute("INSERT OR IGNORE INTO onboarding (user_id, tour) VALUES (?, ?)",
                     (user_id, "done" if veteran else "active"))
        row = _row(conn, user_id)
    return row


def available_tips(conn, user_id: int, today: date, done: dict, tour: str, seen: list) -> list[str]:
    """现在满足条件、且还没看过的提示（按优先级）。引导进行中不出提示，免得同时出现两个焦点。"""
    if tour == "active":
        return []
    tips = []
    pantry = kitchen.list_pantry(conn, user_id, today)
    if any(p["days_left"] is not None and p["days_left"] <= kitchen.EXPIRING_DAYS for p in pantry):
        tips.append("expiring")
    state = prefs_mod.get(conn, user_id)
    if done["recommend"]:
        # 第 2 期跳过的题，在用户看过一次推荐之后再问（这时候他知道这些设置有什么用）
        tips.extend(f"ask_{q}" for q in state["skipped"] if q != "body")
    if len(pantry) >= 5 and all(p["expires_estimated"] or not p["expires_on"] for p in pantry):
        tips.append("expiry_dates")
    created = conn.execute("SELECT created_at FROM users WHERE id=?", (user_id,)).fetchone()[0]
    days = (today - datetime.fromisoformat(created).date()).days
    if done["cook"] and days >= HEALTH_TIP_AFTER_DAYS and not prefs_mod.health_in_nav(state["prefs"]):
        tips.append("health")
    return [t for t in TIP_IDS if t in tips and t not in seen]


def state(conn, user_id: int, today: date) -> dict:
    row = _ensure(conn, user_id)
    done = steps(conn, user_id, bool(row["opened_recipe"]))
    seen = json.loads(row["tips_seen"] or "[]")
    pstate = prefs_mod.get(conn, user_id)
    checklist = [
        {"key": "prefs", "label": "告诉 Favor 你的口味和厨具", "done": pstate["status"] == "done"},
        {"key": "pantry", "label": f"冰箱里放 {PANTRY_GOAL} 样食材", "done": done["pantry"]},
        {"key": "recommend", "label": "让 Favor 推荐一次", "done": done["recommend"]},
        {"key": "open", "label": "打开一道菜看看", "done": done["open"]},
        {"key": "cook", "label": "做好或收藏一道菜", "done": done["cook"]},
    ]
    current = next((k for k in ("pantry", "recommend", "open", "cook") if not done[k]), None)
    return {
        "tour": row["tour"],
        "steps": done,
        "current": current,  # 引导当前停在哪一步；None = 4 步都做完了（等用户看完完成提示）
        # 完成提示要区分「真做了」（已扣库存、记了一餐）和「只收藏了」
        "cooked": _count(conn, "SELECT COUNT(*) FROM cook_logs WHERE user_id=?", user_id) > 0,
        "checklist": checklist,
        "checklist_done": sum(c["done"] for c in checklist),
        "checklist_dismissed": bool(row["checklist_dismissed"]),
        "tips": available_tips(conn, user_id, today, done, row["tour"], seen),
        "prefs_status": pstate["status"],
    }


def update(conn, user_id: int, changes: dict, today: date) -> dict:
    """tour: skipped/done；opened_recipe: true；checklist_dismissed: true；seen_tip: 提示 id。调用方负责提交。"""
    _ensure(conn, user_id)
    if not isinstance(changes, dict):
        changes = {}
    if "tour" in changes:
        if changes["tour"] not in ("skipped", "done"):
            raise ValidationError("引导状态只能是 skipped 或 done")
        conn.execute("UPDATE onboarding SET tour=?, updated_at=datetime('now') WHERE user_id=?",
                     (changes["tour"], user_id))
    if changes.get("opened_recipe") is True:
        conn.execute("UPDATE onboarding SET opened_recipe=1, updated_at=datetime('now') WHERE user_id=?", (user_id,))
    if changes.get("checklist_dismissed") is True:
        conn.execute("UPDATE onboarding SET checklist_dismissed=1, updated_at=datetime('now') WHERE user_id=?",
                     (user_id,))
    if "seen_tip" in changes:
        # 可以一次标记多条：整份问卷都跳过的人只看一条合并的「补问卷」提示，点「不用了」就把 ask_* 全部记为看过
        tips = changes["seen_tip"] if isinstance(changes["seen_tip"], list) else [changes["seen_tip"]]
        if not tips or any(t not in TIP_IDS for t in tips):
            raise ValidationError("未知的提示")
        seen = json.loads(_row(conn, user_id)["tips_seen"] or "[]")
        seen.extend(t for t in tips if t not in seen)
        conn.execute("UPDATE onboarding SET tips_seen=?, updated_at=datetime('now') WHERE user_id=?",
                     (json.dumps(seen), user_id))
    return state(conn, user_id, today)
