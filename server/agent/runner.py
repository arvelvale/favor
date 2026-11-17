"""Agent 主循环：流式调用模型 → 执行工具 → 把结果喂回模型，直到模型给出最终回复。

对前端产出的事件（SSE data 行）：
  {"type": "delta", "content": "..."}          文本增量
  {"type": "tool", "name": "...", "status": "running"}
  {"type": "card", "card": {...}}               工具执行产生的结构化卡片
  {"type": "done", "title": "..."}              本轮结束（附会话标题）
  {"type": "error", "message": "..."}
"""
import json
from datetime import datetime

from config import logger

from . import tools
from .prompts import build_system_prompt

MAX_ROUNDS = 6          # 单轮对话内最多几次“模型→工具”往返，防止死循环
HISTORY_LIMIT = 40      # 回放给模型的最近消息条数
TOOL_LABELS = {
    "log_meal": "记录饮食", "log_water": "记录饮水", "log_exercise": "记录运动", "log_sleep": "记录睡眠",
    "log_weight": "记录体重", "log_mood": "记录心情", "delete_record": "删除记录",
    "get_day_summary": "查看当日数据", "get_trends": "分析趋势", "list_records": "查找记录",
    "get_profile": "读取档案", "update_profile": "更新档案", "add_habit": "创建习惯", "check_habit": "习惯打卡",
    "generate_food_image": "生成菜品图",
}


def load_history(conn, conversation_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM (SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?) ORDER BY id",
        (conversation_id, HISTORY_LIMIT)).fetchall()
    # 截断后的开头可能是孤立的 tool 消息或带 tool_calls 的 assistant，从第一条 user 消息开始回放
    start = next((i for i, r in enumerate(rows) if r["role"] == "user"), len(rows))
    history = []
    for r in rows[start:]:
        msg = {"role": r["role"], "content": r["content"] or ""}
        if r["tool_calls"]:
            msg["tool_calls"] = json.loads(r["tool_calls"])
        if r["tool_call_id"]:
            msg["tool_call_id"] = r["tool_call_id"]
        history.append(msg)
    return history


def save_message(conn, conversation_id: int, role: str, content: str = "", tool_calls=None,
                 tool_call_id=None, events=None) -> None:
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id, events) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, role, content,
         json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
         tool_call_id, json.dumps(events, ensure_ascii=False) if events else None))


def _stream_completion(client, model: str, messages: list[dict], tool_schemas: list[dict]):
    """流式调用一次模型，逐个产出文本增量；结束时产出 ("final", content, tool_calls)。"""
    stream = client.chat.completions.create(
        model=model, messages=messages, tools=tool_schemas, tool_choice="auto",
        temperature=0.4, max_tokens=4000, stream=True)  # 推理 token 也计入上限
    content, calls = [], {}
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if delta.content:
            content.append(delta.content)
            yield ("delta", delta.content)
        for tc in delta.tool_calls or []:
            slot = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                slot["id"] = tc.id
            if tc.function and tc.function.name:
                slot["name"] += tc.function.name
            if tc.function and tc.function.arguments:
                slot["arguments"] += tc.function.arguments
    tool_calls = [{"id": c["id"] or f"call_{i}", "type": "function",
                   "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                  for i, c in sorted(calls.items())]
    yield ("final", "".join(content), tool_calls)


def run_turn(conn, client, model: str, user_id: int, conversation_id: int, user_text: str, now: datetime,
             images=None):
    """执行一轮对话，产出事件 dict。conn 由调用方创建，本函数负责提交。"""
    ctx = tools.ToolContext(conn=conn, user_id=user_id, now=now, images=images)
    tool_schemas = tools.schemas(image_enabled=images is not None)
    history = load_history(conn, conversation_id)
    save_message(conn, conversation_id, "user", user_text)
    conn.execute("UPDATE conversations SET updated_at=datetime('now') WHERE id=?", (conversation_id,))
    title_row = conn.execute("SELECT title FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    title = title_row["title"]
    if title == "新的对话":
        title = user_text.strip().replace("\n", " ")[:18] or title
        conn.execute("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))
    conn.commit()

    history.append({"role": "user", "content": user_text})
    try:
        for _ in range(MAX_ROUNDS):
            messages = [{"role": "system", "content": build_system_prompt(conn, user_id, now, image_enabled=images is not None)}, *history]
            content, tool_calls = "", []
            for event in _stream_completion(client, model, messages, tool_schemas):
                if event[0] == "delta":
                    yield {"type": "delta", "content": event[1]}
                else:
                    _, content, tool_calls = event

            if not tool_calls:
                save_message(conn, conversation_id, "assistant", content)
                conn.commit()
                yield {"type": "done", "title": title}
                return

            assistant = {"role": "assistant", "content": content, "tool_calls": tool_calls}
            results = []
            for call in tool_calls:
                name = call["function"]["name"]
                yield {"type": "tool", "name": name, "label": TOOL_LABELS.get(name, name), "status": "running"}
                try:
                    result, cards = tools.execute(ctx, name, call["function"]["arguments"])
                except Exception as exc:  # 工具内部意外错误：记录日志，告诉模型失败，不暴露细节
                    conn.rollback()
                    logger.exception("tool %s failed", name)
                    result, cards = {"ok": False, "error": f"工具执行失败（{type(exc).__name__}）"}, []
                for card in cards:
                    yield {"type": "card", "card": card}
                results.append((call["id"], result, cards))

            # assistant(tool_calls) 与全部 tool 结果一起落库，保证历史回放时配对完整
            save_message(conn, conversation_id, "assistant", content, tool_calls=tool_calls)
            history.append(assistant)
            for call_id, result, cards in results:
                payload = json.dumps(result, ensure_ascii=False, default=str)
                save_message(conn, conversation_id, "tool", payload, tool_call_id=call_id, events=cards)
                history.append({"role": "tool", "tool_call_id": call_id, "content": payload})
            conn.commit()

        save_message(conn, conversation_id, "assistant", "这个问题我处理了好几步还没理清，换个说法再问我一次好吗？")
        conn.commit()
        yield {"type": "delta", "content": "这个问题我处理了好几步还没理清，换个说法再问我一次好吗？"}
        yield {"type": "done", "title": title}
    except Exception as exc:
        conn.rollback()
        logger.error("agent turn failed: %s", type(exc).__name__)
        yield {"type": "error", "message": _friendly_error(exc)}


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    if "Authentication" in name or "PermissionDenied" in name:
        return "模型服务的密钥无效，请检查 LLM_API_KEY 配置。"
    if "RateLimit" in name:
        return "模型服务有点忙，稍等几秒再试一次吧。"
    if "Timeout" in name or "Connection" in name:
        return "连接模型服务超时了，检查一下网络后再试。"
    return "这次回答出了点问题，请稍后再试。"


def display_messages(conn, conversation_id: int) -> list[dict]:
    """把存储的 OpenAI 格式消息整理成前端气泡：工具卡片并入随后的 assistant 气泡。"""
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,)).fetchall()
    bubbles, current = [], None
    for r in rows:
        if r["role"] == "user":
            bubbles.append({"id": r["id"], "role": "user", "content": r["content"], "cards": []})
            current = None
            continue
        if current is None:
            current = {"id": r["id"], "role": "assistant", "content": "", "cards": []}
            bubbles.append(current)
        if r["role"] == "tool":
            current["cards"].extend(json.loads(r["events"]) if r["events"] else [])
        elif r["content"]:
            current["content"] = f"{current['content']}\n\n{r['content']}" if current["content"] else r["content"]
    return bubbles
