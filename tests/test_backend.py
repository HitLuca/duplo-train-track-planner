import random
import unittest

from backend.generate import gen_sym_loop
from backend.geometry import analyze
from backend.pieces import DEFAULT_INV
from backend.render import card, catalog, describe, detail
from backend.search import merge, search, select


class GeometryTest(unittest.TestCase):
    def test_circle_of_twelve_30deg_curves_closes(self):
        lay = analyze([{"t": "C30", "d": 1}] * 12, {"C30": 12})
        self.assertIsNotNone(lay)
        self.assertEqual(lay.pieces, 12)

    def test_eleven_curves_do_not_close(self):
        self.assertIsNone(analyze([{"t": "C30", "d": 1}] * 11, {"C30": 12}))

    def test_inventory_is_respected(self):
        self.assertIsNone(analyze([{"t": "C30", "d": 1}] * 12, {"C30": 11}))

    def test_bridge_needs_ramps_on_both_sides(self):
        seq = [{"t": "C30", "d": 1}] * 6 + [{"t": "RAMP", "up": 1}, {"t": "EL"}] + [{"t": "C30", "d": 1}] * 6
        self.assertIsNone(analyze(seq, {"C30": 12, "RAMP": 2, "EL": 1}))

    def test_sym_loop_is_valid(self):
        rnd = random.Random(3)
        loops = [x for x in (gen_sym_loop(DEFAULT_INV, rnd) for _ in range(50)) if x]
        self.assertTrue(loops)
        for lay in loops:
            self.assertIsNotNone(analyze(lay.seq, DEFAULT_INV))


class SearchAndRenderTest(unittest.TestCase):
    def test_search_finds_tagged_layouts(self):
        res = select(merge(search(DEFAULT_INV, None, 800, 1)))
        self.assertTrue(res)
        self.assertEqual(res[0]["tag"], "Il più lungo")
        for r in res:
            self.assertIsNotNone(analyze(r["seq"], DEFAULT_INV))

    def test_room_limit(self):
        room = {"w": 900, "h": 900}
        for r in search(DEFAULT_INV, room, 500, 2):
            self.assertLessEqual(r["fp"]["h"], 900)

    def test_render_payloads(self):
        r = describe([{"t": "C30", "d": 1}] * 12)
        c = card(r, {"C30": 5})
        self.assertTrue(c["missing"])
        self.assertTrue(c["thumb"]["pieces"])
        d = detail(r, DEFAULT_INV)
        self.assertEqual(len(d["steps"]), 12)
        self.assertEqual([s["n"] for s in d["steps"]], list(range(1, 13)))
        self.assertGreater(len(d["train"]["points"]), 100)
        self.assertEqual(sum(len(g["types"]) for g in catalog()["groups"]), 19)


if __name__ == "__main__":
    unittest.main()
