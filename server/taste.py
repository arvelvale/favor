"""越用越准（第 5 期）：从做过、收藏、跳过、「不想吃」里学口味，影响下一次推荐。

不是机器学习，是几条看得懂的规则（都写进测试）：
- 做过（强正向）、收藏（正向）→ 「用户喜欢」，提示模型推荐相近口味，但别原样重复
- 3 天内做过 → 排后面并标注「前天刚做过」，提示模型这次别再推
- 换一批时上一批里没点开、没收藏、没做的菜 → 记一次「跳过」；30 天内跳过 ≥2 次且没做过 → 排后面并标注
- 「不想吃」三种原因：不爱吃 → 以后不再推荐（服务端剔除）；太麻烦 → 排后面，并提示模型倾向省事的做法；
  最近吃过 → 7 天内排后面
- 所有学到的都在「我的 → Favor 学到的」里列出来，可以撤销
"""
import re
from datetime import datetime, timedelta

import kitchen
from health import ValidationError

REASONS = {"not_like": "不爱吃", "too_hard": "太麻烦", "recent": "最近吃过"}
RECENT_COOK_DAYS = 3
RECENT_SAID_DAYS = 7
SKIP_WINDOW_DAYS = 30
SKIP_THRESHOLD = 2
LIKED_WINDOW_DAYS = 90


def title_key(title: str) -> str:
    """菜名归一：去空白标点、统一常见别名（西红柿 → 番茄），用于判断「是不是同一道菜」。"""
    t = re.sub(r"[\s·、，,。.!！()（）]+", "", title or "")
    for alias, canonical in kitchen.SYNONYMS.items():
        t = t.replace(alias, canonical)
    return t


def _stamp(now: datetime) -> str:
    # 记用户本地时间（和 cook_logs.cooked_at 一致），否则「3 天内」「7 天内」会差一个时区
    return now.replace(microsecond=0).isoformat(sep=" ")


def _when(text: str) -> datetime:
    return datetime.fromisoformat(str(text).replace("T", " ")[:19])


# ---------------------------------------------------------------- 记录信号


def record_open(conn, user_id: int, recipe_id: int, now: datetime) -> bool:
    row = conn.execute("SELECT title FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)).fetchone()
    if row is None:
        return False
    if not conn.execute("SELECT 1 FROM recipe_feedback WHERE user_id=? AND recipe_id=? AND kind='open'",
                        (user_id, recipe_id)).fetchone():
        conn.execute("INSERT INTO recipe_feedback (user_id, recipe_id, title, kind, created_at) VALUES (?,?,?,'open',?)",
                     (user_id, recipe_id, row["title"], _stamp(now)))
    # 新手引导第 2 步「打开一道菜」由这条 open 记录推导（见 onboarding.steps），这里不再单独写引导表：
    # 引导表的行是第一次读引导状态时才建的，直接 UPDATE 可能一行都没改到
    return True


def mark_skips(conn, user_id: int, now: datetime) -> int:
    """要换一批时调用：上一批里没点开、没收藏、没做的菜，各记一次「跳过」。返回记了几道。"""
    row = conn.execute("SELECT batch FROM recipes WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if row is None:
        return 0
    n = 0
    for r in conn.execute("SELECT id, title, saved FROM recipes WHERE user_id=? AND batch=?",
                          (user_id, row["batch"])).fetchall():
        touched = r["saved"] or conn.execute(
            "SELECT 1 FROM recipe_feedback WHERE user_id=? AND recipe_id=? AND kind IN ('open','skip','dislike')",
            (user_id, r["id"])).fetchone() or conn.execute(
            "SELECT 1 FROM cook_logs WHERE user_id=? AND recipe_id=?", (user_id, r["id"])).fetchone()
        if not touched:
            conn.execute("INSERT INTO recipe_feedback (user_id, recipe_id, title, kind, created_at) VALUES (?,?,?,'skip',?)",
                         (user_id, r["id"], r["title"], _stamp(now)))
            n += 1
    return n


def dislike(conn, user_id: int, recipe_id: int, reason: str, now: datetime) -> dict | None:
    if reason not in REASONS:
        raise ValidationError("原因只能是 不爱吃 / 太麻烦 / 最近吃过")
    row = conn.execute("SELECT title FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM recipe_feedback WHERE user_id=? AND recipe_id=? AND kind='dislike'", (user_id, recipe_id))
    conn.execute("INSERT INTO recipe_feedback (user_id, recipe_id, title, kind, reason, created_at) VALUES (?,?,?,'dislike',?,?)",
                 (user_id, recipe_id, row["title"], reason, _stamp(now)))
    return {"title": row["title"], "reason": reason, "reason_label": REASONS[reason]}


def forget(conn, user_id: int, title: str) -> int:
    """撤销对某道菜学到的负面信号（跳过、不想吃）。按归一化菜名匹配。"""
    key = title_key(title)
    if not key:
        raise ValidationError("菜名不能为空")
    ids = [r["id"] for r in conn.execute(
        "SELECT id, title FROM recipe_feedback WHERE user_id=? AND kind IN ('skip','dislike')", (user_id,)).fetchall()
        if title_key(r["title"]) == key]
    conn.executemany("DELETE FROM recipe_feedback WHERE id=?", [(i,) for i in ids])
    return len(ids)


# ---------------------------------------------------------------- 学到的口味


def profile(conn, user_id: int, now: datetime) -> dict:
    """{liked, recent, disliked, too_hard, skipped}，每项都是 {归一化菜名: 信息}，liked 另给排好序的列表。"""
    cooked: dict[str, dict] = {}
    for r in conn.execute("SELECT title, cooked_at FROM cook_logs WHERE user_id=? AND cooked_at >= ?",
                          (user_id, (now - timedelta(days=LIKED_WINDOW_DAYS)).isoformat())).fetchall():
        k = title_key(r["title"])
        c = cooked.setdefault(k, {"title": r["title"], "count": 0, "last": _when(r["cooked_at"])})
        c["count"] += 1
        c["last"] = max(c["last"], _when(r["cooked_at"]))
    saved = {title_key(r["title"]): r["title"] for r in conn.execute(
        "SELECT DISTINCT title FROM recipes WHERE user_id=? AND saved=1", (user_id,)).fetchall()}

    liked_scores: dict[str, tuple] = {}
    for k, c in cooked.items():
        liked_scores[k] = (c["count"] * 2 + (1 if k in saved else 0), c["title"])
    for k, t in saved.items():
        liked_scores.setdefault(k, (1, t))
    liked = [t for _, t in sorted(liked_scores.values(), key=lambda x: -x[0])][:8]

    recent = {k: {"title": c["title"], "why": _days_ago(c["last"], now)}
              for k, c in cooked.items() if now - c["last"] <= timedelta(days=RECENT_COOK_DAYS)}
    disliked, too_hard, skips = {}, {}, {}
    for r in conn.execute("SELECT title, kind, reason, created_at FROM recipe_feedback WHERE user_id=? "
                          "AND kind IN ('dislike','skip') ORDER BY id", (user_id,)).fetchall():
        k, at = title_key(r["title"]), _when(r["created_at"])
        if r["kind"] == "dislike":
            if r["reason"] == "not_like":
                disliked[k] = r["title"]
            elif r["reason"] == "too_hard":
                too_hard[k] = r["title"]
            elif r["reason"] == "recent" and now - at <= timedelta(days=RECENT_SAID_DAYS):
                recent.setdefault(k, {"title": r["title"], "why": "你说最近吃过"})
        elif now - at <= timedelta(days=SKIP_WINDOW_DAYS):
            s = skips.setdefault(k, {"title": r["title"], "count": 0, "last": at})
            s["count"] += 1
            s["last"] = max(s["last"], at)
    # 跳过之后又做过的，说明不是不喜欢，只是那天不想吃
    skipped = {k: s for k, s in skips.items()
               if s["count"] >= SKIP_THRESHOLD and not (k in cooked and cooked[k]["last"] > s["last"]) and k not in disliked}
    return {"liked": liked, "recent": recent, "disliked": disliked, "too_hard": too_hard, "skipped": skipped}


def _days_ago(when: datetime, now: datetime) -> str:
    d = (now.date() - when.date()).days
    return "今天刚做过" if d <= 0 else "昨天刚做过" if d == 1 else "前天刚做过" if d == 2 else f"{d} 天前做过"


def prompt_lines(p: dict) -> list[str]:
    lines = []
    if p["liked"]:
        lines.append("用户做过、收藏过的菜（说明喜欢这类口味，可以推荐相近的，但别原样重复）：" + "、".join(p["liked"]))
    if p["recent"]:
        lines.append("最近刚吃过，这次别再推荐：" + "、".join(v["title"] for v in p["recent"].values()))
    avoid = list(p["disliked"].values()) + [v["title"] for v in p["skipped"].values()]
    if avoid:
        lines.append("用户不爱吃或多次跳过，不要推荐，类似的也少推：" + "、".join(avoid))
    if p["too_hard"]:
        lines.append("用户嫌这些太麻烦，倾向步骤更少、更省事的做法：" + "、".join(p["too_hard"].values()))
    return lines


def blocked(recipe: dict, p: dict) -> str | None:
    """服务端硬剔除：用户说过「不爱吃」的菜。"""
    return "你说过不爱吃" if title_key(recipe["title"]) in p["disliked"] else None


def notes(recipe: dict, p: dict) -> list[str]:
    """软标注（和超时、太难一样排后面）：最近吃过、嫌麻烦、多次跳过。"""
    k = title_key(recipe["title"])
    out = []
    if k in p["recent"]:
        out.append(p["recent"][k]["why"])
    if k in p["too_hard"]:
        out.append("你说过这道太麻烦")
    if k in p["skipped"]:
        out.append(f"最近跳过了 {p['skipped'][k]['count']} 次")
    return out


def summary(conn, user_id: int, now: datetime) -> dict:
    """给「我的 → Favor 学到的」：常做的、少推的（可撤销）。"""
    p = profile(conn, user_id, now)
    less = [{"title": t, "why": "不爱吃，不再推荐"} for t in p["disliked"].values()]
    less += [{"title": t, "why": "嫌麻烦，排后面"} for t in p["too_hard"].values()]
    less += [{"title": s["title"], "why": f"跳过了 {s['count']} 次，排后面"} for s in p["skipped"].values()]
    less += [{"title": v["title"], "why": "最近吃过，这几天先不推"} for v in p["recent"].values() if v["why"] == "你说最近吃过"]
    return {"liked": p["liked"], "less": less}
