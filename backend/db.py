"""Archivio SQLite: inventario, spazio disponibile e percorsi salvati."""
import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trenino.db"))

_lock = threading.Lock()


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS layouts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                data       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )


def get_setting(key):
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def set_setting(key, value):
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def _row(r):
    return {"id": r["id"], "name": r["name"], "created_at": r["created_at"], **json.loads(r["data"])}


def list_layouts():
    with _conn() as c:
        rows = c.execute("SELECT id, name, data, created_at FROM layouts ORDER BY id DESC").fetchall()
    return [_row(r) for r in rows]


def get_layout(lid):
    with _conn() as c:
        r = c.execute("SELECT id, name, data, created_at FROM layouts WHERE id = ?", (lid,)).fetchone()
    return _row(r) if r else None


def add_layout(name, data):
    with _lock, _conn() as c:
        return c.execute("INSERT INTO layouts(name, data) VALUES(?, ?)", (name, json.dumps(data))).lastrowid


def rename_layout(lid, name):
    with _lock, _conn() as c:
        return c.execute("UPDATE layouts SET name = ? WHERE id = ?", (name, lid)).rowcount > 0


def delete_layout(lid):
    with _lock, _conn() as c:
        return c.execute("DELETE FROM layouts WHERE id = ?", (lid,)).rowcount > 0
