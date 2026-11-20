"""Generatori di percorsi chiusi e mosse per allungarli."""
import itertools
import math

from .geometry import analyze, remaining, sub_items, walk
from .pieces import CURVES, HALFU, PT, SIZEW, TYPES, U, XTYPES, rad

_cid = itertools.count(1000)


def new_cid():
    return next(_cid)


def wpick(arr, w, rnd):
    return rnd.choices(arr, weights=w)[0]


def bridge_units(av):
    """Ponti possibili con i pezzi disponibili: rampa su + sopraelevati + rampa giù."""
    out = []
    if av.get("RAMP", 0) < 2:
        return out
    combos = [[], ["ES"], ["EL"], ["EL", "ES"], ["EL", "EL"], ["ES", "ES"], ["EL", "EL", "EL"], ["EL", "EL", "ES"]]
    for c in combos:
        if c.count("EL") > av.get("EL", 0) or c.count("ES") > av.get("ES", 0):
            continue
        if max(0, len(c) - 1) > av.get("PIL", 0):
            continue
        items = [{"t": "RAMP", "up": 1}] + [{"t": t} for t in c] + [{"t": "RAMP", "up": -1}]
        out.append({"items": items, "len": 448 + sum(PT[t]["len"] for t in c), "w": 3})
    return out


def compose(L, av, rnd, no_x=False, no_b=False):
    """Riempie una lunghezza L (multipla di 32 mm) con pezzi diritti disponibili."""
    rem, a, out = L, dict(av), []
    guard = 0
    while rem > 0 and guard < 60:
        guard += 1
        u = []
        if a.get("S", 0) > 0 and rem >= 128:
            u.append({"items": [{"t": "S"}], "len": 128, "w": 4})
        if a.get("S2", 0) > 0 and rem >= 64:
            u.append({"items": [{"t": "S2"}], "len": 64, "w": 1.5})
        if a.get("S4", 0) > 0 and rem >= 32:
            u.append({"items": [{"t": "S4"}], "len": 32, "w": 1})
        if not no_x and rem >= 128:
            for x in XTYPES:
                if a.get(x, 0) > 0:
                    li = math.floor(rnd.random() * len(PT[x]["lines"]))
                    u.append({"items": [{"t": x, "cid": new_cid(), "li": li}], "len": 128, "w": .5})
        if not no_b:
            u.extend(b for b in bridge_units(a) if b["len"] <= rem)
        if not u:
            return None
        c = wpick(u, [x["w"] * x["len"] / 128 for x in u], rnd)
        items = [dict(x) for x in c["items"]]
        out.extend(items)
        a = sub_items(a, items)
        rem -= c["len"]
    return out if rem == 0 else None


def fam_pref(av, rnd):
    fams = [f for f in ("C30", "C45", "C15") if any(PT[t]["fam"] == f and av.get(t, 0) > 0 for t in CURVES)]
    w = {}
    if not fams:
        return w
    main = "C30" if rnd.random() < .55 and "C30" in fams else rnd.choice(fams)
    for f in fams:
        w[f] = 10 if f == main else (0 if rnd.random() < .5 else 1.5)
    return w


def pick_turns(target, av, rnd, fw):
    for _ in range(12):
        rem, a, out = target, dict(av), []
        while rem > 0:
            c = [t for t in CURVES if a.get(t, 0) > 0 and PT[t]["u"] <= rem]
            if not c:
                break
            t = wpick(c, [max(.02, fw.get(PT[t]["fam"], 0)) * SIZEW[t] for t in c], rnd)
            out.append(t)
            a[t] -= 1
            rem -= PT[t]["u"]
        if rem == 0:
            return out
    return None


def order_turns(turns, rnd):
    if rnd.random() < .5:
        out = list(turns)
        rnd.shuffle(out)
        return out
    return sorted(turns, key=lambda t: (-PT[t]["u"], t))


def _insert(items, pos, chunk):
    items[pos:pos] = chunk


def gen_sym_loop(inv, rnd):
    """Anello a simmetria centrale: mezzo giro (180°) ripetuto due volte → si chiude sempre."""
    half = {t: inv.get(t, 0) // 2 for t in TYPES}
    turns = pick_turns(HALFU, half, rnd, fam_pref(half, rnd))
    if not turns:
        return None
    a = dict(half)
    for t in turns:
        a[t] -= 1
    items = [{"t": t, "d": 1} for t in order_turns(turns, rnd)]
    if rnd.random() < .3:
        c = [t for t in CURVES if a.get(t, 0) >= 2]
        if c:
            t = rnd.choice(c)
            a[t] -= 2
            _insert(items, math.floor(rnd.random() * (len(items) + 1)), [{"t": t, "d": 1}])
            _insert(items, math.floor(rnd.random() * (len(items) + 1)), [{"t": t, "d": -1}])
    for _ in range(math.floor(rnd.random() * 4)):
        c = compose(rnd.choice([64, 128, 128, 256, 384]), a, rnd, no_x=True)
        if not c:
            continue
        _insert(items, math.floor(rnd.random() * (len(items) + 1)), c)
        a = sub_items(a, c)
    return analyze(items + [dict(x) for x in items], inv)


def _near32(v):
    k = math.floor(v / 32 + .5)
    return k if k >= 0 and abs(v - 32 * k) < .6 else -1


def fix_closure(items, start, target, av, rnd):
    """Chiude un tratto aggiungendo rettilinei in al massimo due direzioni."""
    W = walk(items, start)
    if W.end[2] != target[2]:
        return None
    ex, ey = target[0] - W.end[0], target[1] - W.end[1]
    if math.hypot(ex, ey) < .5:
        return items, av
    n = len(items)
    slot_h = [start[2]] + [g.h1 for g in W.segs]
    uniq = list(dict.fromkeys(slot_h))
    sols = []
    for ha in uniq:
        a = rad(ha)
        ux, uy = math.cos(a), math.sin(a)
        if abs(ux * ey - uy * ex) < .5:
            k = _near32(ux * ex + uy * ey)
            if k > 0:
                sols.append([(ha, k)])
    for p in range(len(uniq)):
        for q in range(p + 1, len(uniq)):
            a, b = rad(uniq[p]), rad(uniq[q])
            ux, uy, vx, vy = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
            det = ux * vy - uy * vx
            if abs(det) < 1e-6:
                continue
            ka = _near32((ex * vy - ey * vx) / det)
            kb = _near32((ux * ey - uy * ex) / det)
            if ka >= 0 and kb >= 0 and ka + kb > 0:
                sols.append([z for z in ((uniq[p], ka), (uniq[q], kb)) if z[1] > 0])
    if not sols:
        return None
    sols.sort(key=lambda s: sum(z[1] for z in s))
    head = sols[:3]
    rnd.shuffle(head)
    for sol in (head + sols[3:])[:12]:
        a2, ins, ok = dict(av), [], True
        for h, k in sol:
            c = compose(k * 32, a2, rnd, no_x=True)
            if not c:
                ok = False
                break
            a2 = sub_items(a2, c)
            ins.append((rnd.choice([i for i in range(n + 1) if slot_h[i] == h]), c))
        if not ok:
            continue
        ins.sort(key=lambda z: -z[0])
        out = list(items)
        for pos, c in ins:
            _insert(out, pos, c)
        return out, a2
    return None


def gen_figure8(inv, rnd):
    """Otto con incrocio: un'ansa chiusa più la sua copia specchiata."""
    xs = [t for t in XTYPES if inv.get(t, 0) > 0]
    if not xs:
        return None
    xt = rnd.choice(xs)
    hb = 72 if xt == "X90" else 64
    av = {t: (inv.get(t, 0) - (1 if t == xt else 0)) // 2 for t in TYPES}
    turns = pick_turns(hb, av, rnd, fam_pref(av, rnd))
    if not turns:
        return None
    a = dict(av)
    for t in turns:
        a[t] -= 1
    items = [{"t": t, "d": 1} for t in order_turns(turns, rnd)]
    for _ in range(math.floor(rnd.random() * 3)):
        c = compose(rnd.choice([64, 128, 256]), a, rnd, no_x=True)
        if not c:
            continue
        _insert(items, math.floor(rnd.random() * (len(items) + 1)), c)
        a = sub_items(a, c)
    fx = fix_closure(items, (64.0, 0.0, 0), (-64 * math.cos(rad(hb)), -64 * math.sin(rad(hb)), hb), a, rnd)
    if not fx:
        return None
    lobe, cid = fx[0], new_cid()
    mirror = [dict(x, d=-x["d"]) if PT[x["t"]]["kind"] == "curve" else dict(x) for x in lobe]
    seq = [{"t": xt, "cid": cid, "li": 0}] + [dict(x) for x in lobe] + [{"t": xt, "cid": cid}] + mirror
    return analyze(seq, inv)


def _slot_ok(seq, i):
    pv = seq[i - 1]
    return not (pv["t"] in ("EL", "ES") or (pv["t"] == "RAMP" and pv.get("up") == 1))


def _regions(seq, lay):
    multi = {c["cid"] for c in lay.crosses if len(c["segIdx"]) > 1}
    tot = sum(1 for it in seq if it.get("cid") in multi)
    r, c = [], 0
    for it in seq:
        r.append(c % tot if tot else 0)
        if it.get("cid") in multi:
            c += 1
    return r


STRAIGHT_LENS = [32, 64, 64, 128, 128, 128, 256, 256, 384, 448, 576, 672]


def expand(lay, inv, rnd, iters):
    """Allunga un percorso con mosse che mantengono la chiusura: stessi pezzi aggiunti su lati opposti."""
    cur = lay
    for _ in range(iters):
        seq, n = cur.seq, len(cur.seq)
        rem = remaining(inv, cur.cnt)
        reg = _regions(seq, cur)
        i = math.floor(rnd.random() * n)
        if not _slot_ok(seq, i):
            continue
        target = (cur.W.segs[i].h0 + HALFU) % U
        js = [j for j in range(n) if j != i and cur.W.segs[j].h0 == target and reg[j] == reg[i] and _slot_ok(seq, j)]
        if not js:
            continue
        j = rnd.choice(js)
        if rnd.random() < .75:
            L = rnd.choice(STRAIGHT_LENS)
            A = compose(L, rem, rnd)
            if not A:
                continue
            B = compose(L, sub_items(rem, A), rnd)
            if not B:
                continue
        else:
            cs = [t for t in CURVES if rem.get(t, 0) >= 4]
            if not cs:
                continue
            t = rnd.choice(cs)
            s = 1 if rnd.random() < .5 else -1
            r2 = dict(rem)
            r2[t] -= 4
            m1, m2 = [], []
            if rnd.random() < .4:
                L = rnd.choice([64, 128, 256])
                m1 = compose(L, r2, rnd, no_b=True) or []
                if m1:
                    r2 = sub_items(r2, m1)
                    m2 = compose(L, r2, rnd, no_b=True)
                    if not m2:
                        m1, m2 = [], []
            A = [{"t": t, "d": s}] + m1 + [{"t": t, "d": -s}]
            B = [{"t": t, "d": s}] + m2 + [{"t": t, "d": -s}]
        ns = list(seq)
        p1, q1, p2, q2 = (i, A, j, B) if i > j else (j, B, i, A)
        _insert(ns, p1, q1)
        _insert(ns, p2, q2)
        cand = analyze(ns, inv)
        if cand and cand.len > cur.len:
            cur = cand
    return cur
