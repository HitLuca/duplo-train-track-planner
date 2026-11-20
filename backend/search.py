"""Ricerca dei percorsi: generazione casuale + allungamento, in parallelo su più processi."""
import multiprocessing as mp
import os
import queue
import random
import threading
import time
import uuid

from .generate import expand, gen_figure8, gen_sym_loop
from .geometry import footprint
from .pieces import PT, XTYPES


def signature(e):
    """Due percorsi con gli stessi pezzi e circa lo stesso ingombro contano come uno."""
    fp = e["fp"]
    return "".join(f"{k}{e['cnt'][k]}" for k in sorted(e["cnt"])) + f"|{round(fp['w'] / 40)}x{round(fp['h'] / 40)}|{e['multiX']}"


def _fits(fp, room):
    return (fp["w"] <= room["w"] and fp["h"] <= room["h"]) or (fp["w"] <= room["h"] and fp["h"] <= room["w"])


def search(inv, room, ms, seed, progress=None):
    """Cerca per `ms` millisecondi. Restituisce i migliori percorsi trovati (uno per firma), senza il Layout."""
    rnd = random.Random(seed)
    pool = {}
    t0 = time.monotonic()
    deadline = t0 + ms / 1000
    last_p = 0.0
    has_x = any(inv.get(t, 0) > 0 for t in XTYPES)

    def record(lay):
        if not lay:
            return
        fp = footprint(lay)
        if room and not _fits(fp, room):
            return
        e = {"seq": lay.seq, "len": lay.len, "cnt": lay.cnt, "pieces": lay.pieces, "multiX": lay.multiX, "fp": fp, "lay": lay}
        sig = signature(e)
        old = pool.get(sig)
        if not old or old["len"] < lay.len:
            pool[sig] = e

    while time.monotonic() < deadline:
        r = rnd.random()
        if len(pool) > 6 and r < .25:
            top = sorted(pool.values(), key=lambda e: -e["len"])[:8]
            base = rnd.choice(top)["lay"]
        elif has_x and r < .55:
            base = gen_figure8(inv, rnd)
        else:
            base = gen_sym_loop(inv, rnd)
        if not base:
            continue
        record(base)
        record(expand(base, inv, rnd, rnd.choice([10, 40, 120, 250, 400])))
        now = time.monotonic()
        if progress and now - last_p > .15:
            last_p = now
            progress(len(pool))
    return [{k: v for k, v in e.items() if k != "lay"} for e in pool.values()]


def merge(entries):
    """Tiene il più lungo per ogni firma."""
    best = {}
    for e in entries:
        sig = signature(e)
        if sig not in best or best[sig]["len"] < e["len"]:
            best[sig] = e
    return list(best.values())


def select(entries):
    """Sceglie i percorsi da mostrare, ognuno con un'etichetta."""
    all_ = sorted(entries, key=lambda x: (-x["len"], -x["pieces"]))
    out, used = [], set()

    def add(x, tag):
        if x is not None and id(x) not in used:
            used.add(id(x))
            out.append({**x, "tag": tag})

    first = lambda pred: next((x for x in all_ if pred(x)), None)  # noqa: E731
    shape = lambda x: f"{round(x['fp']['w'] / 80)}x{round(x['fp']['h'] / 80)}{x['multiX']}"  # noqa: E731
    if not all_:
        return out
    add(all_[0], "Il più lungo")
    add(first(lambda x: x["multiX"] > 0), "Il più lungo con incrocio")
    add(first(lambda x: x["cnt"].get("RAMP")), "Il più lungo con ponte")
    add(min(all_, key=lambda x: (-x["pieces"], -x["len"])), "Usa più pezzi")
    add(min(all_, key=lambda x: x["fp"]["w"] * x["fp"]["h"]), "Il più piccolo")
    add(first(lambda x: any(PT[t]["fam"] == "C45" for t in x["cnt"])), "Con curve strette")
    add(first(lambda x: any(PT[t]["fam"] == "C15" for t in x["cnt"])), "Con curve larghe")
    # varianti: forme diverse, scaglionate per lunghezza
    shapes = {shape(x) for x in out}
    for x in all_:
        if len(out) >= 14:
            break
        k = shape(x)
        if k in shapes:
            continue
        shapes.add(k)
        add(x, "Variante")
    return out


# ---------------- ricerca in parallelo ----------------

def _worker(wid, inv, room, ms, seed, q):
    res = search(inv, room, ms, seed, lambda n: q.put(("progress", wid, n)))
    q.put(("done", wid, res))


class SearchJob:
    def __init__(self, inv, room, ms, previous=None):
        self.id = uuid.uuid4().hex[:12]
        self.inv, self.room, self.ms = inv, room, ms
        self.previous = previous or []
        self.started = time.monotonic()
        self.found = 0
        self.done = False
        self.error = None
        self.results = []
        threading.Thread(target=self._run, daemon=True).start()

    def progress(self):
        if self.done:
            return 1.0
        return min(.99, (time.monotonic() - self.started) / (self.ms / 1000))

    def _run(self):
        try:
            entries = self._run_parallel()
            self.results = select(merge(self.previous + entries))
        except Exception as e:  # noqa: BLE001 - l'errore va mostrato all'utente
            self.error = str(e)
        finally:
            self.done = True

    def _run_parallel(self):
        workers = max(1, min(8, os.cpu_count() or 1))
        seed = random.randrange(1 << 30)
        if workers == 1:
            return search(self.inv, self.room, self.ms, seed, lambda n: setattr(self, "found", n))
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        procs = [ctx.Process(target=_worker, args=(w, self.inv, self.room, self.ms, seed + w * 7919, q), daemon=True)
                 for w in range(workers)]
        for p in procs:
            p.start()
        found, out, pending = [0] * workers, [], set(range(workers))
        deadline = time.monotonic() + self.ms / 1000 + 60
        try:
            while pending:
                try:
                    kind, wid, val = q.get(timeout=max(.1, deadline - time.monotonic()))
                except queue.Empty:
                    raise RuntimeError("la ricerca non ha risposto in tempo") from None
                if kind == "progress":
                    found[wid] = val
                    self.found = sum(found)
                else:
                    out.extend(val)
                    found[wid] = len(val)
                    self.found = sum(found)
                    pending.discard(wid)
        finally:
            for p in procs:
                p.join(timeout=2)
                if p.is_alive():
                    p.terminate()
        return out


class JobStore:
    """Ricerche recenti in memoria (le più vecchie vengono scartate)."""

    def __init__(self, keep=20):
        self.keep = keep
        self.jobs = {}
        self.lock = threading.Lock()

    def add(self, job):
        with self.lock:
            self.jobs[job.id] = job
            while len(self.jobs) > self.keep:
                self.jobs.pop(next(iter(self.jobs)))
        return job

    def get(self, jid):
        with self.lock:
            return self.jobs.get(jid)
