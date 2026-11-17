"""SQLite 数据层。每个请求一个连接，挂在 flask.g 上，请求结束关闭。"""
import json
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    nickname      TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id           INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    sex               TEXT,
    birth_year        INTEGER,
    height_cm         REAL,
    weight_kg         REAL,
    target_weight_kg  REAL,
    activity_level    TEXT,
    goal              TEXT,
    diet_preferences  TEXT NOT NULL DEFAULT '',
    allergies         TEXT NOT NULL DEFAULT '',
    conditions        TEXT NOT NULL DEFAULT '',
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- kind: meal / water / exercise / sleep / weight / mood
-- day / at 均为用户本地时间（由前端时区偏移换算），data 为该类记录的 JSON 字段。
CREATE TABLE IF NOT EXISTS records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT    NOT NULL,
    day        TEXT    NOT NULL,
    at         TEXT    NOT NULL,
    data       TEXT    NOT NULL,
    source     TEXT    NOT NULL DEFAULT 'manual',
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_records_user_day ON records(user_id, day);

CREATE TABLE IF NOT EXISTS habits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    note       TEXT    NOT NULL DEFAULT '',
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS habit_checks (
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    day      TEXT    NOT NULL,
    PRIMARY KEY (habit_id, day)
);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT    NOT NULL DEFAULT '新的对话',
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 百炼生成的菜品图；file 为 data/images 下的文件名，只对 user_id 本人提供
CREATE TABLE IF NOT EXISTS images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT    NOT NULL,
    prompt     TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'pending',
    file       TEXT,
    error      TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 按 OpenAI 消息格式存储，可原样回放给模型；tool_calls / events 为 JSON。
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT    NOT NULL,
    content         TEXT    NOT NULL DEFAULT '',
    tool_calls      TEXT,
    tool_call_id    TEXT,
    events          TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path: Path) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["SETTINGS"].database_path)
    return g.db


def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def row_to_dict(row) -> dict:
    return dict(row) if row is not None else None


def record_to_dict(row) -> dict:
    item = dict(row)
    item["data"] = json.loads(item["data"])
    return item
