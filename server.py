"""Trenino Duplo - server: file statici + API JSON.
Tutta l'elaborazione (ricerca, geometria, dati da disegnare) sta in `backend/`; il frontend mostra soltanto.
Solo libreria standard Python, nessuna dipendenza.
"""
import json
import os
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from backend import db
from backend.pieces import PT, normalize_inv
from backend.render import card, catalog, describe, detail
from backend.search import JobStore, SearchJob

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(ROOT, "app"))
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 2 * 1024 * 1024
SEARCH_MS = {"fast": 2000, "normal": 5000, "deep": 12000}

JOBS = JobStore()
_CATALOG = None
_cards_lock = threading.Lock()


class NotFound(Exception):
    pass


# ---------------- logica delle API ----------------

def current_inv():
    return normalize_inv(db.get_setting("inventory"))


def parse_inv(raw):
    if not isinstance(raw, dict) or not all(t in PT and isinstance(v, int) and 0 <= v <= 999 for t, v in raw.items()):
        raise ValueError("inventario non valido")
    return normalize_inv(raw)


def parse_room(raw):
    """Spazio disponibile in cm; {w:0,h:0} = nessun limite."""
    raw = raw or {}
    try:
        w, h = max(0, float(raw.get("w") or 0)), max(0, float(raw.get("h") or 0))
    except (TypeError, ValueError):
        raise ValueError("spazio non valido") from None
    return {"w": w, "h": h}


def save_inventory(d):
    inv = parse_inv(d.get("inv"))
    db.set_setting("inventory", inv)
    if "room" in d:
        db.set_setting("room", parse_room(d["room"]))
    return inv


def job_or_404(jid):
    job = JOBS.get(jid)
    if not job:
        raise NotFound("ricerca scaduta: rilancia la ricerca")
    return job


def job_cards(job):
    with _cards_lock:
        if not hasattr(job, "cards"):
            job.cards = [{"index": i, **card(r)} for i, r in enumerate(job.results)]
    return job.cards


def job_result(job, i):
    if not job.done or not 0 <= i < len(job.results):
        raise NotFound("percorso non trovato")
    return job.results[i]


def start_search(d):
    inv = save_inventory(d)
    room = parse_room(d.get("room"))
    ms = SEARCH_MS.get(d.get("depth"), SEARCH_MS["normal"])
    previous = []
    if d.get("previous"):
        prev = JOBS.get(str(d["previous"]))
        if prev and prev.done:
            previous = prev.results
    room_mm = {"w": room["w"] * 10, "h": room["h"] * 10} if room["w"] > 0 and room["h"] > 0 else None
    return JOBS.add(SearchJob(inv, room_mm, ms, previous))


def search_status(job):
    out = {"id": job.id, "done": job.done, "progress": round(job.progress(), 3), "found": job.found, "error": job.error}
    if job.done and not job.error:
        out["results"] = job_cards(job)
    return out


def saved_summary(row, inv):
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"], **card(row, inv)}


def layout_or_404(lid):
    row = db.get_layout(lid)
    if not row:
        raise NotFound("percorso non trovato")
    return row


def clean_name(raw, default=""):
    return str(raw or "").strip()[:80] or default


# ---------------- HTTP ----------------

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC_DIR, **kw)

    def log_message(self, fmt, *args):
        if not re.match(r"/api/(health|search/\w+$)", self.path):
            super().log_message(fmt, *args)

    def send_json(self, obj, status=200):
        body = json.dumps(obj, separators=(",", ":")).encode()
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

    def route(self, method, path):
        global _CATALOG
        if path == "/api/health" and method == "GET":
            return {"ok": True}

        if path == "/api/catalog" and method == "GET":
            if _CATALOG is None:
                _CATALOG = catalog()
            return _CATALOG

        if path == "/api/inventory":
            if method == "GET":
                return {"inv": current_inv(), "room": db.get_setting("room") or {"w": 0, "h": 0}}
            if method == "PUT":
                save_inventory(self.read_json())
                return {"ok": True}

        if path == "/api/search" and method == "POST":
            return 202, {"id": start_search(self.read_json()).id}

        m = re.fullmatch(r"/api/search/(\w+)", path)
        if m and method == "GET":
            return search_status(job_or_404(m.group(1)))

        m = re.fullmatch(r"/api/search/(\w+)/(\d+)(/save)?", path)
        if m:
            job, i = job_or_404(m.group(1)), int(m.group(2))
            r = job_result(job, i)
            if not m.group(3) and method == "GET":
                return {"index": i, **detail(r, current_inv())}
            if m.group(3) and method == "POST":
                name = clean_name(self.read_json().get("name"), "Percorso")
                lid = db.add_layout(name, {**describe(r["seq"]), "tag": r.get("tag")})
                return 201, {"id": lid}

        if path == "/api/layouts" and method == "GET":
            inv = current_inv()
            return [saved_summary(r, inv) for r in db.list_layouts()]

        m = re.fullmatch(r"/api/layouts/(\d+)", path)
        if m:
            lid = int(m.group(1))
            if method == "GET":
                row = layout_or_404(lid)
                return {"id": row["id"], "name": row["name"], **detail(row, current_inv())}
            if method == "DELETE":
                if not db.delete_layout(lid):
                    raise NotFound("percorso non trovato")
                return {"ok": True}
            if method == "PATCH":
                name = clean_name(self.read_json().get("name"))
                if not name:
                    raise ValueError("nome mancante")
                if not db.rename_layout(lid, name):
                    raise NotFound("percorso non trovato")
                return {"ok": True}

        raise NotFound("non trovato")

    def api(self, method):
        try:
            res = self.route(method, self.path.split("?", 1)[0])
            status, body = res if isinstance(res, tuple) else (200, res)
            self.send_json(body, status)
        except NotFound as e:
            self.send_json({"error": str(e)}, 404)
        except (ValueError, json.JSONDecodeError) as e:
            self.send_json({"error": str(e)}, 400)

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
    db.init()
    print(f"Trenino Duplo su http://0.0.0.0:{PORT}  (db: {db.DB_PATH})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
