"""Precomputed terrain move_speed grid."""

import unittest

from src.module1_state.procedural_tiles import build_move_speed_grid, get_tile


class TestTerrainGrid(unittest.TestCase):
    def test_build_grid_shape_matches_world(self):
        ms, wx0, wy0, w, h = build_move_speed_grid(-3, 4, -2, 5, seed=99, difficulty="normal")
        self.assertEqual(wx0, -3)
        self.assertEqual(wy0, -2)
        self.assertEqual(w, 7)
        self.assertEqual(h, 7)
        self.assertEqual(len(ms), w * h)

    def test_grid_matches_get_tile_sample(self):
        ms, wx0, wy0, w, h = build_move_speed_grid(0, 3, 0, 3, seed=7, difficulty="hard")
        for yy in range(h):
            for xx in range(w):
                x, y = wx0 + xx, wy0 + yy
                t = get_tile(x, y, 7, "hard")
                self.assertAlmostEqual(
                    ms[yy * w + xx], float(t["move_speed"]), places=5
                )


if __name__ == "__main__":
    unittest.main()
