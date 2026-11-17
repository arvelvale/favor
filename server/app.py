"""Favor 健康管家 · API 服务。

开发：python app.py（配合 web/ 下 npm run dev，Vite 代理 /api）
生产：先在 web/ 下 npm run build，再启动本服务，静态页面由 Flask 直接提供。
"""
import json
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, Response, g, jsonify, request, send_from_directory, session, stream_with_context
from werkzeug.security import check_password_hash, generate_password_hash

import health
import kitchen
import onboarding
import prefs
from agent import runner
from config import Settings, logger
from rag import retriever as rag_retriever
from db import close_db, connect, get_db, init_db
from health import ValidationError
from images import DashScopeImageClient, ImageService, public_image


def create_app(settings: Settings | None = None, llm_client=None, image_client=None, images_async: bool = True) -> Flask:
    settings = settings or Settings()
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SETTINGS=settings,
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.secure_cookies,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=256 * 1024,
        JSON_AS_ASCII=False,
    )
    # 保持字典定义顺序：选项（活动水平、目标）按代码里的顺序展示，而不是按字母排序
    app.json.sort_keys = False
    init_db(settings.database_path)
    app.teardown_appcontext(close_db)

    # 启动时就创建模型客户端：openai 包导入在 Windows 上要 3 秒以上，
    # 放到首个对话请求里会让用户的第一句话白等这么久。
    if llm_client is None and settings.llm_enabled:
        from openai import OpenAI
        llm_client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
                            timeout=settings.llm_timeout, max_retries=2)
        _ = llm_client.chat.completions  # SDK 的 resources 是懒加载的，首次访问约 1.4 秒，这里预热

    def get_llm():
        return llm_client

    # 菜品配图（阿里云百炼）。没配密钥且没注入客户端时为 None，agent 不会看到生图工具。
    if image_client is None and settings.image_enabled:
        image_client = DashScopeImageClient(settings.image_api_key, settings.image_base_url,
                                            settings.image_model, settings.image_size)
    image_service = (ImageService(image_client, settings.database_path, settings.database_path.parent / "images",
                                  settings.image_daily_limit, run_async=images_async)
                     if image_client is not None else None)

    # ------------------------------------------------------------ 通用

    def error(message: str, status: int = 400):
        return jsonify({"error": message}), status

    @app.errorhandler(ValidationError)
    def on_validation(exc):
        return error(str(exc), 400)

    @app.errorhandler(413)
    def on_too_large(_exc):
        return error("请求内容过大", 413)

    @app.before_request
    def csrf_guard():
        # 写操作只接受 JSON：跨站表单无法在不触发 CORS 预检的情况下发送 application/json，
        # 配合 SameSite=Lax 会话 Cookie 防御 CSRF。本服务不开放 CORS。
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.method != "DELETE" and not request.is_json:
                return error("请求需为 JSON", 415)

    def local_now() -> datetime:
        """用户本地时间。前端在 X-TZ-Offset 头里传 Date#getTimezoneOffset()（分钟，UTC−本地）。"""
        try:
            offset = max(-840, min(840, int(request.headers.get("X-TZ-Offset", "-480"))))
        except ValueError:
            offset = -480
        return (datetime.now(timezone.utc) - timedelta(minutes=offset)).replace(tzinfo=None, microsecond=0)

    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return error("请先登录", 401)
            user = get_db().execute("SELECT id, username, nickname FROM users WHERE id=?", (user_id,)).fetchone()
            if user is None:
                session.clear()
                return error("请先登录", 401)
            g.user = dict(user)
            return view(*args, **kwargs)
        return wrapper

    def body() -> dict:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------ 账号

    @app.get("/api/meta")
    def meta():
        return jsonify({"llm_enabled": settings.llm_enabled, "model": settings.llm_model if settings.llm_enabled else None,
                        "image_enabled": image_service is not None,
                        "rag_enabled": settings.rag_enabled and rag_retriever.is_enabled()})

    @app.post("/api/auth/register")
    def register():
        data = body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        nickname = str(data.get("nickname", "")).strip()[:20] or username
        if not 3 <= len(username) <= 20 or not all(c.isalnum() or c in "_-" for c in username):
            return error("用户名为 3–20 位字母、数字、下划线或短横线")
        if not 8 <= len(password) <= 128:
            return error("密码至少 8 位")
        conn = get_db()
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return error("这个用户名已经被使用了", 409)
        cur = conn.execute("INSERT INTO users (username, password_hash, nickname) VALUES (?, ?, ?)",
                           (username, generate_password_hash(password), nickname))
        conn.commit()
        session.clear()
        session.permanent = True
        session["user_id"] = cur.lastrowid
        return jsonify({"user": {"id": cur.lastrowid, "username": username, "nickname": nickname,
                                 "prefs_status": "new"}}), 201

    @app.post("/api/auth/login")
    def login():
        data = body()
        row = get_db().execute("SELECT * FROM users WHERE username=?",
                               (str(data.get("username", "")).strip(),)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], str(data.get("password", ""))):
            return error("用户名或密码不正确", 401)
        session.clear()
        session.permanent = True
        session["user_id"] = row["id"]
        return jsonify({"user": {"id": row["id"], "username": row["username"], "nickname": row["nickname"],
                                 "prefs_status": prefs.get(get_db(), row["id"])["status"]}})

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/auth/me")
    @login_required
    def me():
        return jsonify({"user": g.user | {"prefs_status": prefs.get(get_db(), g.user["id"])["status"]}})

    # ------------------------------------------------------------ 偏好（问卷）

    def prefs_payload(conn, user_id):
        data = prefs.get(conn, user_id)
        profile = health.get_profile(conn, user_id)
        return data | {"allergies": prefs.allergy_list(profile), "servings": prefs.servings(data["prefs"]),
                       "health_in_nav": prefs.health_in_nav(data["prefs"])}

    # ------------------------------------------------------------ 新手引导

    @app.get("/api/onboarding")
    @login_required
    def get_onboarding():
        conn = get_db()
        data = onboarding.state(conn, g.user["id"], local_now().date())
        conn.commit()  # 第一次读取会建行
        return jsonify(data)

    @app.post("/api/onboarding")
    @login_required
    def post_onboarding():
        conn = get_db()
        data = onboarding.update(conn, g.user["id"], body(), local_now().date())
        conn.commit()
        return jsonify(data)

    @app.get("/api/preferences")
    @login_required
    def get_preferences():
        return jsonify(prefs_payload(get_db(), g.user["id"]))

    @app.put("/api/preferences")
    @login_required
    def put_preferences():
        """保存问卷（可只传一部分）。allergies 写回健康档案（单一来源）；profile 为 Q8 的身体数据。"""
        conn = get_db()
        data = body()
        profile_changes = dict(data.get("profile") or {}) if isinstance(data.get("profile"), dict) else {}
        if isinstance(data.get("allergies"), list):
            profile_changes["allergies"] = "、".join(prefs._str_list(data["allergies"]))
        if profile_changes:
            health.save_profile(conn, g.user["id"], profile_changes)
        prefs.save(conn, g.user["id"], data.get("prefs") or {}, status=data.get("status"), skipped=data.get("skipped"))
        conn.commit()
        return jsonify(prefs_payload(conn, g.user["id"]))

    # ------------------------------------------------------------ 档案

    def profile_payload(conn, user_id):
        profile = health.get_profile(conn, user_id)
        return {"profile": profile, "bmi": health.bmi(profile),
                "targets": health.compute_targets(profile, local_now().date()),
                "options": {"activity_levels": {k: v[0] for k, v in health.ACTIVITY_LEVELS.items()},
                            "goals": {k: v[0] for k, v in health.GOALS.items()}}}

    @app.get("/api/profile")
    @login_required
    def get_profile():
        return jsonify(profile_payload(get_db(), g.user["id"]))

    @app.put("/api/profile")
    @login_required
    def put_profile():
        conn = get_db()
        data = body()
        if "nickname" in data:
            nickname = str(data.pop("nickname") or "").strip()[:20]
            if nickname:
                conn.execute("UPDATE users SET nickname=? WHERE id=?", (nickname, g.user["id"]))
        health.save_profile(conn, g.user["id"], data)
        conn.commit()
        return jsonify(profile_payload(conn, g.user["id"]))

    # ------------------------------------------------------------ 记录

    @app.get("/api/summary")
    @login_required
    def summary():
        today = local_now().date()
        day = health.parse_day(request.args.get("day"), today)
        data = health.daily_summary(get_db(), g.user["id"], day, today)
        for r in data["records"]:
            r["text"] = health.describe_record(r)
        return jsonify(data)

    @app.get("/api/records")
    @login_required
    def records():
        today = local_now().date()
        end = health.parse_day(request.args.get("to"), today)
        start = health.parse_day(request.args.get("from"), end - timedelta(days=6))
        if (end - start).days > 120 or start > end:
            return error("日期范围无效（最多 120 天）")
        kind = request.args.get("kind") or None
        if kind and kind not in health.KINDS:
            return error("未知记录类型")
        items = health.list_records(get_db(), g.user["id"], start, end, kind)
        for r in items:
            r["text"] = health.describe_record(r)
        return jsonify({"records": items})

    @app.post("/api/records")
    @login_required
    def create_record():
        data = body()
        now = local_now()
        record = health.add_record(get_db(), g.user["id"], str(data.get("kind", "")), data.get("data") or {},
                                   health.parse_at(data.get("at"), now))
        get_db().commit()
        record["text"] = health.describe_record(record)
        return jsonify({"record": record}), 201

    @app.delete("/api/records/<int:record_id>")
    @login_required
    def remove_record(record_id):
        conn = get_db()
        if not health.delete_record(conn, g.user["id"], record_id):
            return error("记录不存在", 404)
        conn.commit()
        return jsonify({"ok": True})

    @app.get("/api/trends")
    @login_required
    def get_trends():
        try:
            days = max(7, min(90, int(request.args.get("days", 30))))
        except ValueError:
            days = 30
        today = local_now().date()
        conn = get_db()
        return jsonify({"series": health.trends(conn, g.user["id"], today, days),
                        "targets": health.compute_targets(health.get_profile(conn, g.user["id"]), today)})

    # ------------------------------------------------------------ 习惯

    @app.get("/api/habits")
    @login_required
    def habits():
        day = health.parse_day(request.args.get("day"), local_now().date())
        return jsonify({"habits": health.list_habits(get_db(), g.user["id"], day)})

    @app.post("/api/habits")
    @login_required
    def create_habit():
        data = body()
        habit = health.add_habit(get_db(), g.user["id"], data.get("name"), data.get("note", ""))
        get_db().commit()
        return jsonify({"habit": habit}), 201

    @app.post("/api/habits/<int:habit_id>/check")
    @login_required
    def check_habit(habit_id):
        data = body()
        day = health.parse_day(data.get("day"), local_now().date())
        if not health.set_habit_check(get_db(), g.user["id"], habit_id, day, bool(data.get("done", True))):
            return error("习惯不存在", 404)
        get_db().commit()
        return jsonify({"ok": True})

    @app.delete("/api/habits/<int:habit_id>")
    @login_required
    def remove_habit(habit_id):
        if not health.archive_habit(get_db(), g.user["id"], habit_id):
            return error("习惯不存在", 404)
        get_db().commit()
        return jsonify({"ok": True})

    # ------------------------------------------------------------ 对话

    def own_conversation(conn, conversation_id):
        return conn.execute("SELECT * FROM conversations WHERE id=? AND user_id=?",
                            (conversation_id, g.user["id"])).fetchone()

    @app.get("/api/conversations")
    @login_required
    def conversations():
        rows = get_db().execute("SELECT id, title, updated_at FROM conversations WHERE user_id=? "
                                "ORDER BY updated_at DESC, id DESC LIMIT 50", (g.user["id"],)).fetchall()
        return jsonify({"conversations": [dict(r) for r in rows]})

    @app.post("/api/conversations")
    @login_required
    def create_conversation():
        conn = get_db()
        cur = conn.execute("INSERT INTO conversations (user_id) VALUES (?)", (g.user["id"],))
        conn.commit()
        row = conn.execute("SELECT id, title, updated_at FROM conversations WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify({"conversation": dict(row)}), 201

    @app.delete("/api/conversations/<int:conversation_id>")
    @login_required
    def remove_conversation(conversation_id):
        conn = get_db()
        cur = conn.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, g.user["id"]))
        conn.commit()
        return (jsonify({"ok": True}), 200) if cur.rowcount else error("对话不存在", 404)

    @app.get("/api/conversations/<int:conversation_id>/messages")
    @login_required
    def conversation_messages(conversation_id):
        conn = get_db()
        if not own_conversation(conn, conversation_id):
            return error("对话不存在", 404)
        return jsonify({"messages": runner.display_messages(conn, conversation_id)})

    @app.post("/api/conversations/<int:conversation_id>/chat")
    @login_required
    def chat(conversation_id):
        if not own_conversation(get_db(), conversation_id):
            return error("对话不存在", 404)
        text = str(body().get("message", "")).strip()
        if not text:
            return error("消息不能为空")
        if len(text) > 2000:
            return error("消息太长了，控制在 2000 字以内吧")
        client = get_llm()
        if client is None:
            return error("还没有配置模型服务（LLM_API_KEY），暂时无法对话", 503)

        user_id, now = g.user["id"], local_now()

        def stream():
            # 流式响应期间使用独立连接，生命周期与生成器一致
            conn = connect(settings.database_path)
            try:
                for event in runner.run_turn(conn, client, settings.llm_model, user_id, conversation_id, text, now,
                                                images=image_service, recipe_limit=settings.recipe_daily_limit):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            finally:
                conn.close()

        return Response(stream_with_context(stream()), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------ 冰箱库存

    @app.get("/api/pantry")
    @login_required
    def pantry():
        return jsonify({"items": kitchen.list_pantry(get_db(), g.user["id"], local_now().date())})

    @app.get("/api/pantry/catalog")
    @login_required
    def pantry_catalog():
        return jsonify({"groups": kitchen.catalog(), "categories": kitchen.CATEGORIES, "storages": kitchen.STORAGES})

    @app.post("/api/pantry")
    @login_required
    def add_pantry():
        conn = get_db()
        items = kitchen.add_items(conn, g.user["id"], body().get("items"), local_now().date(),
                                  source=str(body().get("source") or "manual")[:10])
        conn.commit()
        return jsonify({"items": items}), 201

    @app.post("/api/pantry/parse")
    @login_required
    def parse_pantry():
        """一句话录入：只解析不入库，前端让用户确认后再 POST /api/pantry。"""
        items = kitchen.parse_text(get_llm(), settings.llm_model if settings.llm_enabled else None,
                                   body().get("text"))
        today = local_now().date()
        preview = []
        for raw in items:
            try:
                clean = kitchen._clean_item(raw, today)
            except ValidationError:
                continue
            preview.append(clean | {"days_left": kitchen._days_left(clean["expires_on"], today),
                                    "category_label": kitchen.CATEGORIES[clean["category"]],
                                    "storage_label": kitchen.STORAGES[clean["storage"]]})
        return jsonify({"items": preview})

    @app.patch("/api/pantry/<int:item_id>")
    @login_required
    def patch_pantry(item_id):
        conn = get_db()
        item = kitchen.update_item(conn, g.user["id"], item_id, body(), local_now().date())
        if item is None:
            return error("食材不存在", 404)
        conn.commit()
        return jsonify({"item": item})

    @app.post("/api/pantry/<int:item_id>/remove")
    @login_required
    def remove_pantry(item_id):
        conn = get_db()
        if not kitchen.remove_item(conn, g.user["id"], item_id, str(body().get("reason") or "used")):
            return error("食材不存在", 404)
        conn.commit()
        return jsonify({"ok": True})

    # ------------------------------------------------------------ 菜谱

    @app.post("/api/recipes/recommend")
    @login_required
    def recommend_recipes():
        conn = get_db()
        try:
            result = kitchen.recommend(conn, get_llm(), settings.llm_model if settings.llm_enabled else None,
                                       g.user["id"], local_now(), str(body().get("note") or ""),
                                       settings.recipe_daily_limit)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 模型超时、返回非 JSON 等，给用户可读的提示
            logger.warning("recommend failed: %s", type(exc).__name__)
            return error("这次没想出来，稍后再试一次吧", 502)
        conn.commit()
        return jsonify(result)

    @app.get("/api/recipes/latest")
    @login_required
    def latest_recipes():
        return jsonify(kitchen.latest_batch(get_db(), g.user["id"], local_now().date()))

    @app.get("/api/recipes")
    @login_required
    def saved_recipes():
        return jsonify(kitchen.list_saved(get_db(), g.user["id"], local_now().date()))

    @app.get("/api/recipes/<int:recipe_id>")
    @login_required
    def recipe_detail(recipe_id):
        recipe = kitchen.recipe_payload(get_db(), g.user["id"], recipe_id, local_now().date())
        return jsonify({"recipe": recipe}) if recipe else error("菜谱不存在", 404)

    @app.post("/api/recipes/<int:recipe_id>/save")
    @login_required
    def save_recipe(recipe_id):
        conn = get_db()
        if not kitchen.set_saved(conn, g.user["id"], recipe_id, bool(body().get("saved", True))):
            return error("菜谱不存在", 404)
        conn.commit()
        return jsonify({"ok": True})

    @app.get("/api/recipes/<int:recipe_id>/cook")
    @login_required
    def cook_preview(recipe_id):
        preview = kitchen.cook_preview(get_db(), g.user["id"], recipe_id, local_now())
        return jsonify(preview) if preview else error("菜谱不存在", 404)

    @app.post("/api/recipes/<int:recipe_id>/cook")
    @login_required
    def cook_recipe(recipe_id):
        conn = get_db()
        data = body()
        result = kitchen.cook(conn, g.user["id"], recipe_id, local_now(), data.get("usage") or [],
                              data.get("eaten_servings", 1), data.get("meal_type"),
                              log_meal=bool(data.get("log_meal", True)))
        if result is None:
            return error("菜谱不存在", 404)
        conn.commit()
        return jsonify(result)

    # ------------------------------------------------------------ 菜品配图

    def own_image(image_id):
        return get_db().execute("SELECT * FROM images WHERE id=? AND user_id=?", (image_id, g.user["id"])).fetchone()

    @app.get("/api/images/<int:image_id>")
    @login_required
    def image_status(image_id):
        row = own_image(image_id)
        if row is None:
            return error("图片不存在", 404)
        return jsonify({"image": public_image(row)})

    @app.get("/api/images/<int:image_id>/file")
    @login_required
    def image_file(image_id):
        row = own_image(image_id)
        if row is None or row["status"] != "ready" or not row["file"]:
            return error("图片不存在", 404)
        folder = settings.database_path.parent / "images"
        res = send_from_directory(folder, row["file"], max_age=86400)
        res.headers["Cache-Control"] = "private, max-age=86400"  # 只属于本人，不让共享缓存保存
        return res

    # ------------------------------------------------------------ 前端静态资源

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path):
        if path.startswith("api/"):
            return error("接口不存在", 404)
        dist = settings.web_dist
        if not (dist / "index.html").exists():
            return error("前端尚未构建：在 web/ 下运行 npm run build，或用 npm run dev 开发", 404)
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    logger.info("Favor ready · db=%s · llm=%s", settings.database_path,
                settings.llm_model if settings.llm_enabled else "disabled")
    return app


if __name__ == "__main__":
    application = create_app()
    cfg = application.config["SETTINGS"]
    application.run(host="127.0.0.1", port=cfg.port, debug=cfg.debug, threaded=True)
