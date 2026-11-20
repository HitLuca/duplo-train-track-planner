"""Catalogo dei pezzi (misure dagli STL del set "Optimized") e costanti angolari.

Unità: millimetri. Le direzioni sono intere, in passi da 3,75° (U = 96 passi = giro completo).
"""
import math

DEG = 3.75
U = 96
HALFU = 48

PT = {
    "S":    {"kind": "lin",   "len": 128, "fam": "S",   "label": "Rettilineo",           "info": "12,8 cm", "stl": "track_straight_standard", "color": "#4C7BD9"},
    "S2":   {"kind": "lin",   "len": 64,  "fam": "S",   "label": "Mezzo rettilineo",     "info": "6,4 cm",  "stl": "track_straight_half", "color": "#78A0EA"},
    "S4":   {"kind": "lin",   "len": 32,  "fam": "S",   "label": "Quarto di rettilineo", "info": "3,2 cm",  "stl": "track_straight_quarter", "color": "#A9C3F4"},
    "C30":  {"kind": "curve", "R": 256,   "u": 8,  "fam": "C30", "label": "Curva 30°",        "info": "raggio 25,6 cm · 12 = cerchio", "stl": "track_curve30deg_standard", "color": "#2E9E5B"},
    "C30h": {"kind": "curve", "R": 256,   "u": 4,  "fam": "C30", "label": "Mezza curva 30°",  "info": "15°, stesso raggio", "stl": "track_curve30deg_half", "color": "#5DBD84"},
    "C30q": {"kind": "curve", "R": 256,   "u": 2,  "fam": "C30", "label": "Quarto curva 30°", "info": "7,5°, stesso raggio", "stl": "track_curve30deg_quarter", "color": "#93D7AE"},
    "C45":  {"kind": "curve", "R": 174.3, "u": 12, "fam": "C45", "label": "Curva 45°",        "info": "raggio 17,4 cm · 8 = cerchio", "stl": "track_curve45deg", "color": "#E8892B"},
    "C45h": {"kind": "curve", "R": 174.3, "u": 6,  "fam": "C45", "label": "Mezza curva 45°",  "info": "22,5°, stesso raggio", "stl": "track_curve45deg_half", "color": "#F0A75E"},
    "C45q": {"kind": "curve", "R": 174.3, "u": 3,  "fam": "C45", "label": "Quarto curva 45°", "info": "11,25°, stesso raggio", "stl": "track_curve45deg_quarter", "color": "#F6C796"},
    "C15":  {"kind": "curve", "R": 500,   "u": 4,  "fam": "C15", "label": "Curva 15°",        "info": "raggio 50 cm · 24 = cerchio", "stl": "track_curve15deg", "color": "#8E5BD6"},
    "C15h": {"kind": "curve", "R": 500,   "u": 2,  "fam": "C15", "label": "Mezza curva 15°",  "info": "7,5°, stesso raggio", "stl": "track_curve15deg_half", "color": "#AD86E3"},
    "C15q": {"kind": "curve", "R": 500,   "u": 1,  "fam": "C15", "label": "Quarto curva 15°", "info": "3,75°, stesso raggio", "stl": "track_curve15deg_quarter", "color": "#CDB4EE"},
    "X90":  {"kind": "cross", "len": 128, "lines": [0, 24],     "fam": "X", "label": "Incrocio 90°",       "info": "due binari a croce", "stl": "track_cross90deg", "color": "#D9443F"},
    "X60":  {"kind": "cross", "len": 128, "lines": [0, 16],     "fam": "X", "label": "Incrocio 60°",       "info": "due binari a 60°", "stl": "track_cross60deg", "color": "#E2635E"},
    "X6":   {"kind": "cross", "len": 128, "lines": [0, 16, 32], "fam": "X", "label": "Incrocio esagonale", "info": "tre binari a 60°", "stl": "track_cross60deg_hexagon", "color": "#EA8783"},
    "RAMP": {"kind": "lin",   "len": 224, "fam": "B", "label": "Rampa del ponte",    "info": "22,4 cm · MILD o ROLLERCOASTER", "stl": "BRIDGE-*", "color": "#E7B81F"},
    "EL":   {"kind": "lin",   "len": 224, "fam": "B", "label": "Sopraelevato lungo", "info": "22,4 cm (LONG)", "stl": "LONG-*", "color": "#B07A2A"},
    "ES":   {"kind": "lin",   "len": 128, "fam": "B", "label": "Sopraelevato corto", "info": "12,8 cm (SHORT)", "stl": "SHORT-*", "color": "#C9954A"},
    "PIL":  {"kind": "none",  "fam": "B", "label": "Pilastro 2×4", "info": "alto 3 mattoncini", "stl": "duplo 2x4 pillars", "color": "#8A6A3A"},
}
TYPES = list(PT)
CURVES = [t for t in TYPES if PT[t]["kind"] == "curve"]
XTYPES = ["X90", "X60", "X6"]
SIZEW = {"C30": 1, "C30h": .3, "C30q": .12, "C45": 1, "C45h": .3, "C45q": .12, "C15": 1, "C15h": .3, "C15q": .12}

GROUPS = [
    ("Rettilinei", ["S", "S2", "S4"]),
    ("Curve 30° (quelle classiche)", ["C30", "C30h", "C30q"]),
    ("Curve 45° (strette)", ["C45", "C45h", "C45q"]),
    ("Curve 15° (larghe)", ["C15", "C15h", "C15q"]),
    ("Incroci", ["X90", "X60", "X6"]),
    ("Ponti", ["RAMP", "EL", "ES", "PIL"]),
]

DEFAULT_INV = {"S": 8, "S2": 2, "S4": 0, "C30": 16, "C30h": 2, "C30q": 0, "C45": 0, "C45h": 0, "C45q": 0,
               "C15": 0, "C15h": 0, "C15q": 0, "X90": 1, "X60": 0, "X6": 0, "RAMP": 2, "EL": 1, "ES": 0, "PIL": 0}


def is_elev(t):
    return t == "EL" or t == "ES"


def rad(h):
    """Direzione in passi → radianti."""
    return h * DEG * math.pi / 180


def normalize_inv(inv):
    """Inventario completo con tutti i tipi, valori interi non negativi."""
    out = dict(DEFAULT_INV)
    for t, v in (inv or {}).items():
        if t in PT:
            out[t] = max(0, int(v))
    return out
