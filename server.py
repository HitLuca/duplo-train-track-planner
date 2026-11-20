"""Trenino Duplo - server minimale: file statici + API JSON su SQLite.
Solo libreria standard Python, nessuna dipendenza.
"""
import json
import os
import re
import sqlite3
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(ROOT, "app"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(ROOT, "data", "trenino.db"))
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 2 * 1024 * 1024

_lock = threading.Lock()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db() as c:
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
    with db() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def set_setting(key, value):
    with _lock, db() as c:
        c.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def list_layouts():
    with db() as c:
        rows = c.execute("SELECT id, name, data, created_at FROM layouts ORDER BY id DESC").fetchall()
    return [{"id": r["id"], "name": r["name"], "created_at": r["created_at"], **json.loads(r["data"])} for r in rows]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC_DIR, **kw)

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/health"):
            super().log_message(fmt, *args)

    # ---- helpers ----
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("corpo della richiesta mancante o troppo grande")
        data = json.loads(self.rfile.read(n))
        if not isinstance(data, dict):
            raise ValueError("JSON non valido")
        return data

    def api(self, method):
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/health" and method == "GET":
                return self.send_json({"ok": True})

            if path == "/api/inventory":
                if method == "GET":
                    return self.send_json({"inv": get_setting("inventory"), "room": get_setting("room")})
                if method == "PUT":
                    d = self.read_json()
                    inv = d.get("inv")
                    if not isinstance(inv, dict) or not all(isinstance(v, int) and 0 <= v <= 999 for v in inv.values()):
                        raise ValueError("inventario non valido")
                    set_setting("inventory", inv)
                    if "room" in d:
                        set_setting("room", d["room"])
                    return self.send_json({"ok": True})

            if path == "/api/layouts":
                if method == "GET":
                    return self.send_json(list_layouts())
                if method == "POST":
                    d = self.read_json()
                    name = str(d.get("name") or "Percorso").strip()[:80] or "Percorso"
                    layout = d.get("layout")
                    if not isinstance(layout, dict) or not isinstance(layout.get("seq"), list):
                        raise ValueError("percorso non valido")
                    with _lock, db() as c:
                        cur = c.execute("INSERT INTO layouts(name, data) VALUES(?, ?)", (name, json.dumps(layout)))
                    return self.send_json({"id": cur.lastrowid}, 201)

            m = re.fullmatch(r"/api/layouts/(\d+)", path)
            if m:
                lid = int(m.group(1))
                if method == "DELETE":
                    with _lock, db() as c:
                        n = c.execute("DELETE FROM layouts WHERE id = ?", (lid,)).rowcount
                    return self.send_json({"ok": bool(n)}, 200 if n else 404)
                if method == "PATCH":
                    name = str(self.read_json().get("name") or "").strip()[:80]
                    if not name:
                        raise ValueError("nome mancante")
                    with _lock, db() as c:
                        n = c.execute("UPDATE layouts SET name = ? WHERE id = ?", (name, lid)).rowcount
                    return self.send_json({"ok": bool(n)}, 200 if n else 404)

            return self.send_json({"error": "non trovato"}, 404)
        except (ValueError, json.JSONDecodeError) as e:
            return self.send_json({"error": str(e)}, 400)

    # ---- verbi ----
    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.api("GET")
        return super().do_GET()

    def do_POST(self):
        return self.api("POST")

    def do_PUT(self):
        return self.api("PUT")

    def do_PATCH(self):
        return self.api("PATCH")

    def do_DELETE(self):
        return self.api("DELETE")


if __name__ == "__main__":
    init_db()
    print(f"Trenino Duplo su http://0.0.0.0:{PORT}  (db: {DB_PATH})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
