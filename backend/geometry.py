"""Geometria: percorrere una sequenza di pezzi, verificarla (chiusura, ponti, incroci, collisioni)
e calcolarne l'ingombro.

Una sequenza è una lista di dict: {"t": tipo, "d": ±1 (curve), "up": ±1 (rampe), "cid", "li" (incroci)}.
"""
import math
from math import atan2, cos, hypot, sin

from .pieces import HALFU, PT, TYPES, U, is_elev, rad


class Seg:
    __slots__ = ("it", "x0", "y0", "h0", "s0", "x1", "y1", "h1", "s1", "len", "R", "cx", "cy", "th0", "dth")


class Walk:
    __slots__ = ("segs", "end", "total")

    def __init__(self, segs, end, total):
        self.segs, self.end, self.total = segs, end, total


def walk(seq, start=(0.0, 0.0, 0)):
    x, y, h = start
    s = 0.0
    segs = []
    for it in seq:
        p = PT[it["t"]]
        a = rad(h)
        g = Seg()
        g.it, g.x0, g.y0, g.h0, g.s0, g.R = it, x, y, h, s, 0
        if p["kind"] == "curve":
            d, u, R = it["d"], p["u"], p["R"]
            b = rad(h + d * u)
            cx, cy = x - d * R * sin(a), y + d * R * cos(a)
            x, y = cx + d * R * sin(b), cy - d * R * cos(b)
            g.cx, g.cy, g.R = cx, cy, R
            g.len = R * rad(u)
            g.th0 = atan2(g.y0 - cy, g.x0 - cx)
            g.dth = d * rad(u)
            h = (h + d * u) % U
        else:
            g.len = p["len"]
            x += g.len * cos(a)
            y += g.len * sin(a)
        g.x1, g.y1, g.h1 = x, y, h
        s += g.len
        g.s1 = s
        segs.append(g)
    return Walk(segs, (x, y, h), s)


def point_at(g, t):
    """Punto e direzione (radianti) a frazione t del pezzo."""
    if g.R:
        th = g.th0 + t * g.dth
        return g.cx + g.R * cos(th), g.cy + g.R * sin(th), rad(g.h0) + t * g.dth
    return g.x0 + (g.x1 - g.x0) * t, g.y0 + (g.y1 - g.y0) * t, rad(g.h0)


def counts(seq):
    """Pezzi usati (un incrocio conta una volta sola; un pilastro per ogni giunzione tra sopraelevati)."""
    c, seen, pil, n = {}, set(), 0, len(seq)
    for i, it in enumerate(seq):
        if PT[it["t"]]["kind"] == "cross":
            if it["cid"] in seen:
                continue
            seen.add(it["cid"])
        c[it["t"]] = c.get(it["t"], 0) + 1
        if is_elev(it["t"]) and is_elev(seq[(i + 1) % n]["t"]):
            pil += 1
    if pil:
        c["PIL"] = pil
    return c


def remaining(inv, cnt):
    return {t: inv.get(t, 0) - cnt.get(t, 0) for t in TYPES}


def sub_items(av, items):
    r = dict(av)
    seen, prev_el = set(), False
    for it in items:
        if PT[it["t"]]["kind"] == "cross":
            if it["cid"] in seen:
                continue
            seen.add(it["cid"])
        r[it["t"]] = r.get(it["t"], 0) - 1
        if is_elev(it["t"]) and prev_el:
            r["PIL"] = r.get("PIL", 0) - 1
        prev_el = is_elev(it["t"])
    return r


class Layout:
    __slots__ = ("seq", "W", "len", "cnt", "multiX", "crosses", "pieces")


def _ramp_up(it):
    return it["t"] == "RAMP" and it.get("up") == 1


def _ramp_down(it):
    return it["t"] == "RAMP" and it.get("up") == -1


def analyze(seq, inv=None, loose=False):
    """Analizza una sequenza: chiusura, ponti, inventario, incroci, collisioni.
    loose=True: solo geometria, senza verifiche (per disegnare). Restituisce Layout o None."""
    n = len(seq)
    if not n:
        return None
    W = walk(seq)
    if not loose:
        ex, ey, eh = W.end
        if eh != 0 or hypot(ex, ey) > 0.8:
            return None
        # ponti ben formati: rampa su → sopraelevati → rampa giù
        for i in range(n):
            it, nx, pv = seq[i], seq[(i + 1) % n], seq[(i - 1) % n]
            if _ramp_up(it) and not (is_elev(nx["t"]) or _ramp_down(nx)):
                return None
            if is_elev(it["t"]) and (not (is_elev(nx["t"]) or _ramp_down(nx)) or not (is_elev(pv["t"]) or _ramp_up(pv))):
                return None
            if _ramp_down(it) and not (is_elev(pv["t"]) or _ramp_up(pv)):
                return None
    cnt = counts(seq)
    if inv is not None and not loose:
        for t, v in cnt.items():
            if v > inv.get(t, 0):
                return None
    # incroci
    groups = {}
    for i, g in enumerate(W.segs):
        if PT[g.it["t"]]["kind"] == "cross":
            groups.setdefault(g.it["cid"], []).append(i)
    crosses, multi_x = [], 0
    for cid, lst in groups.items():
        t = W.segs[lst[0]].it["t"]
        lines = PT[t]["lines"]
        cs = [((W.segs[i].x0 + W.segs[i].x1) / 2, (W.segs[i].y0 + W.segs[i].y1) / 2) for i in lst]
        if not loose:
            for c in cs:
                if hypot(c[0] - cs[0][0], c[1] - cs[0][1]) > 1.2:
                    return None
            if len(lst) > len(lines):
                return None
        os_ = [W.segs[i].h0 % HALFU for i in lst]
        if len(set(os_)) != len(os_):
            return None
        try_li = [W.segs[lst[0]].it.get("li") or 0] if len(lst) == 1 else range(len(lines))
        sel = None
        for li in try_li:
            r = (os_[0] - lines[li]) % HALFU
            st = [(l + r) % HALFU for l in lines]
            if all(o in st for o in os_):
                sel = st
                break
        if sel is None:
            if loose:
                sel = os_
            else:
                return None
        if len(lst) > 1:
            multi_x += 1
        crosses.append({"cid": cid, "t": t, "segIdx": lst, "x": cs[0][0], "y": cs[0][1],
                        "s": W.segs[lst[0]].s0 + 64, "orients": sel, "unused": [o for o in sel if o not in os_]})
    lay = Layout()
    lay.seq, lay.W, lay.len, lay.cnt, lay.multiX, lay.crosses = seq, W, W.total, cnt, multi_x, crosses
    lay.pieces = sum(v for k, v in cnt.items() if k != "PIL")
    if loose:
        return lay
    if collides(lay):
        return None
    return lay


# campionamento per le collisioni (mm)
SP, TH, NEAR = 22, 56, 110
TH2 = TH * TH
_RAYS = (-58, -38, -16, 16, 38, 58)


def collides(lay):
    W = lay.W
    P, segs = W.total, W.segs
    grid = {}
    cid_of = [g.it["cid"] if PT[g.it["t"]]["kind"] == "cross" else None for g in segs]

    def add(x, y, s, si):
        ix, iy = math.floor(x / TH), math.floor(y / TH)
        csi = cid_of[si]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = grid.get((ix + dx, iy + dy))
                if not cell:
                    continue
                for qx, qy, qs, qsi in cell:
                    if qsi == si:
                        continue
                    if csi is not None and csi == cid_of[qsi]:
                        continue
                    ds = abs(s - qs)
                    if ds > P - ds:
                        ds = P - ds
                    if ds < NEAR:
                        continue
                    ex, ey = qx - x, qy - y
                    if ex * ex + ey * ey < TH2:
                        return True
        grid.setdefault((ix, iy), []).append((x, y, s, si))
        return False

    for i, g in enumerate(segs):
        m = max(1, round(g.len / SP))
        for k in range(m):
            t = (k + .5) / m
            px, py, _ = point_at(g, t)
            if add(px, py, g.s0 + t * g.len, i):
                return True
    for c in lay.crosses:
        for o in c["unused"]:
            a = rad(o)
            ca, sa = cos(a), sin(a)
            for r in _RAYS:
                if add(c["x"] + r * ca, c["y"] + r * sa, c["s"], c["segIdx"][0]):
                    return True
    return False


def footprint(lay):
    """Ingombro: prova rotazioni ogni 15° e tiene la più compatta (larghezza ≥ profondità)."""
    pts = []
    for g in lay.W.segs:
        m = max(2, round(g.len / 16))
        for k in range(m + 1):
            px, py, _ = point_at(g, k / m)
            pts.append((px, py))
    for c in lay.crosses:
        for o in c["unused"]:
            a = rad(o)
            pts.append((c["x"] + 64 * cos(a), c["y"] + 64 * sin(a)))
            pts.append((c["x"] - 64 * cos(a), c["y"] - 64 * sin(a)))
    best = None
    for deg in range(0, 90, 15):
        a = deg * math.pi / 180
        ca, sa = cos(a), sin(a)
        xs = [x * ca - y * sa for x, y in pts]
        ys = [x * sa + y * ca for x, y in pts]
        w, h = max(xs) - min(xs) + 64, max(ys) - min(ys) + 64
        if best is None or w * h < best["w"] * best["h"] - 1:
            best = {"w": w, "h": h, "rot": deg}
    if best["h"] > best["w"]:
        best = {"w": best["h"], "h": best["w"], "rot": best["rot"] + 90}
    return best
