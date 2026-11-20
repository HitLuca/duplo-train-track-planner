"""Dati pronti per il disegno: forme dei pezzi già in coordinate di schermo, numeri, istruzioni,
percorso del treno. Il frontend li trasforma in SVG senza fare altri calcoli."""
import math
from math import cos, sin

from .geometry import analyze, footprint, point_at
from .pieces import DEG, GROUPS, PT, is_elev, rad

HALF_W = 31     # metà larghezza del binario (mm)
RAIL = 19       # distanza delle rotaie dal centro (mm)


def _r(v):
    return round(v, 1)


def make_t(rot_deg):
    """Ruota di rot_deg e ribalta l'asse y (lo schermo ha y verso il basso)."""
    a = rot_deg * math.pi / 180
    c, s = cos(a), sin(a)
    return lambda x, y: (_r(x * c - y * s), _r(-(x * s + y * c)))


def _xy_off(g, t, off):
    x, y, a = point_at(g, t)
    return x - off * sin(a), y + off * cos(a)


def _offset_line(g, off, T, step=8):
    m = max(2, math.ceil(g.len / step))
    return [T(*_xy_off(g, k / m, off)) for k in range(m + 1)]


class _Line:
    """Tratto diritto centrato in (cx, cy) con direzione o: un braccio di un incrocio."""
    R = 0

    def __init__(self, cx, cy, o, half):
        a = rad(o)
        self.x0, self.y0 = cx - half * cos(a), cy - half * sin(a)
        self.x1, self.y1 = cx + half * cos(a), cy + half * sin(a)
        self.h0, self.len, self.it = o, 2 * half, {}


def _shape(g, t, idx, T, step=8):
    left, right = _offset_line(g, HALF_W, T, step), _offset_line(g, -HALF_W, T, step)
    shape = {
        "i": idx,
        "t": t,
        "outline": left + right[::-1],
        "rails": [_offset_line(g, RAIL, T, step), _offset_line(g, -RAIL, T, step)],
        "ends": [[T(*_xy_off(g, 0, HALF_W)), T(*_xy_off(g, 0, -HALF_W))],
                 [T(*_xy_off(g, 1, HALF_W)), T(*_xy_off(g, 1, -HALF_W))]],
        "lift": 10 if is_elev(t) else (5 if t == "RAMP" else 0),
    }
    if t == "RAMP":
        shape["ramp"] = {"from": T(g.x0, g.y0), "to": T(g.x1, g.y1), "up": g.it.get("up") == 1}
    return shape


def _numbering(lay):
    """Numero di montaggio per ogni segmento (un incrocio ha un solo numero)."""
    num, by_cid, k = [], {}, 0
    for g in lay.W.segs:
        if PT[g.it["t"]]["kind"] == "cross":
            if g.it["cid"] not in by_cid:
                k += 1
                by_cid[g.it["cid"]] = k
            num.append(by_cid[g.it["cid"]])
        else:
            k += 1
            num.append(k)
    return num


def _cross_of(lay, cid):
    return next(c for c in lay.crosses if c["cid"] == cid)


def draw(lay, T, labels=False, step=8):
    pieces, lbls, done_x = [], [], set()
    num = _numbering(lay) if labels else None
    for i, g in enumerate(lay.W.segs):
        t = g.it["t"]
        if PT[t]["kind"] == "cross":
            if g.it["cid"] in done_x:
                continue
            done_x.add(g.it["cid"])
            c = _cross_of(lay, g.it["cid"])
            pieces.extend(_shape(_Line(c["x"], c["y"], o, 64), t, i, T, step) for o in c["orients"])
            pos = (c["x"], c["y"])
        else:
            pieces.append(_shape(g, t, i, T, step))
            pos = point_at(g, .5)[:2]
        if labels:
            lbls.append({"n": num[i], "at": T(*pos)})
    return pieces, lbls, num


def bbox(lay, T, pad=45):
    pts = []
    for g in lay.W.segs:
        pts.extend(T(*point_at(g, k / 8)[:2]) for k in range(9))
    for c in lay.crosses:
        for o in c["orients"]:
            a = rad(o)
            pts.append(T(c["x"] + 64 * cos(a), c["y"] + 64 * sin(a)))
            pts.append(T(c["x"] - 64 * cos(a), c["y"] - 64 * sin(a)))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"x": _r(min(xs) - pad), "y": _r(min(ys) - pad), "w": _r(max(xs) - min(xs) + 2 * pad), "h": _r(max(ys) - min(ys) + 2 * pad)}


# ---------------- catalogo ----------------

def icon(t):
    """Disegno del singolo pezzo per l'inventario."""
    p = PT[t]
    if p["kind"] == "none":
        return {"kind": "pillar"}
    it = {"t": t}
    if p["kind"] == "curve":
        it["d"] = 1
    if t == "RAMP":
        it["up"] = 1
    if p["kind"] == "cross":
        it.update(cid=1, li=0)
    lay = analyze([it], loose=True)
    T = make_t(-p["u"] * DEG / 2 if p["kind"] == "curve" else 0)
    b = bbox(lay, T)
    m = max(b["w"], b["h"] * 1.3)
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    pieces, _, _ = draw(lay, T)
    return {"kind": "pieces", "viewBox": [_r(cx - m / 2), _r(cy - m / 2.6), _r(m), _r(m / 1.3)], "pieces": pieces}


def catalog():
    groups = []
    for title, types in GROUPS:
        groups.append({"title": title, "types": [
            {"t": t, "label": PT[t]["label"], "info": PT[t]["info"], "stl": PT[t]["stl"], "color": PT[t]["color"], "icon": icon(t)}
            for t in types]})
    return {"groups": groups, "colors": {t: PT[t]["color"] for t in PT}, "labels": {t: PT[t]["label"] for t in PT}}


# ---------------- percorsi ----------------

def describe(seq):
    """Riassunto calcolato da una sequenza (per i percorsi salvati)."""
    lay = analyze(seq, loose=True)
    if not lay:
        raise ValueError("percorso vuoto")
    return {"seq": seq, "len": lay.len, "cnt": lay.cnt, "pieces": lay.pieces, "multiX": lay.multiX, "fp": footprint(lay)}


def card(entry, inv=None):
    """Dati per la miniatura in galleria."""
    lay = analyze(entry["seq"], loose=True)
    T = make_t(entry["fp"]["rot"])
    pieces, _, _ = draw(lay, T, step=24)
    out = {
        "tag": entry.get("tag"),
        "len": _r(entry["len"]),
        "pieces": entry["pieces"],
        "width": _r(entry["fp"]["w"]),
        "depth": _r(entry["fp"]["h"]),
        "crossing": entry["multiX"] > 0,
        "bridge": bool(entry["cnt"].get("RAMP")),
        "thumb": {"bbox": bbox(lay, T), "pieces": pieces},
    }
    if inv is not None:
        out["missing"] = any(v > inv.get(t, 0) for t, v in entry["cnt"].items())
    return out


def _steps(lay, num):
    steps, seen, k = [], set(), 0
    for idx, g in enumerate(lay.W.segs):
        it = g.it
        p = PT[it["t"]]
        piece = idx
        if p["kind"] == "cross":
            c = _cross_of(lay, it["cid"])
            piece = c["segIdx"][0]
            if it["cid"] in seen:
                steps.append({"piece": piece, "t": it["t"], "n": None, "text": f"ripassa sull'incrocio n. {num[idx]}", "icon": "↺"})
                continue
            seen.add(it["cid"])
        txt, ic = p["label"], ""
        if p["kind"] == "curve":
            txt += " — gira a sinistra" if it["d"] > 0 else " — gira a destra"
            ic = "↰" if it["d"] > 0 else "↱"
        if it["t"] == "RAMP":
            txt += " — sale" if it.get("up", 0) > 0 else " — scende"
        if p["kind"] == "cross" and len(_cross_of(lay, it["cid"])["segIdx"]) == 1:
            txt += " (usato come rettilineo)"
        k += 1
        steps.append({"piece": piece, "t": it["t"], "n": k, "text": txt, "icon": ic})
    return steps


def _train_path(lay, T, step=6):
    pts = []
    for g in lay.W.segs:
        m = max(2, math.ceil(g.len / step))
        for k in range(m):
            x, y, _ = point_at(g, k / m)
            pts.append([*T(x, y), _r(g.s0 + g.len * k / m)])
    return {"points": pts, "total": _r(lay.W.total)}


def detail(entry, inv):
    """Tutto quello che serve per la vista grande di un percorso."""
    lay = analyze(entry["seq"], loose=True)
    T = make_t(entry["fp"]["rot"])
    pieces, labels, num = draw(lay, T, labels=True)
    used = []
    for _, types in GROUPS:
        for t in types:
            u, have = entry["cnt"].get(t, 0), inv.get(t, 0)
            if u or have:
                used.append({"t": t, "used": u, "have": have})
    out = card(entry, inv)
    del out["thumb"]
    return {
        **out,
        "bbox": bbox(lay, T),
        "pieces": pieces,
        "labels": labels,
        "steps": _steps(lay, num),
        "used": used,
        "train": _train_path(lay, T),
    }
