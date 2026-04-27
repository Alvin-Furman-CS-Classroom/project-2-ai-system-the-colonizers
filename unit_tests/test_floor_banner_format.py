import unittest

from src.module1_state.colony_state import ColonyState
from visual_game import format_floor_banner


class TestFloorBannerFormat(unittest.TestCase):
    def test_banner_contains_deck_and_scan(self):
        s = ColonyState({"floor_index": 3, "world_seed": 42, "difficulty": "normal"})
        a, b = format_floor_banner(s)
        self.assertIn("DECK 3", a)
        self.assertIn("DEPTH", a)
        self.assertIn("Scan ID:", b)


if __name__ == "__main__":
    unittest.main()

