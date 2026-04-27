"""Viewport tree guarantee (ensure_viewport_trees) without Pygame."""

import random
import unittest

from src.module1_state.colony_state import ColonyState
from src.module1_state.tree_generation import ensure_viewport_trees


class TestTreeViewportPolicy(unittest.TestCase):
    def test_adds_tree_when_viewport_empty(self):
        state = ColonyState(
            {
                "world_seed": 777,
                "turn_number": 1,
                "floor_index": 1,
                "difficulty": "normal",
                "world_min_x": 0,
                "world_max_x": 30,
                "world_min_y": 0,
                "world_max_y": 30,
                "world_trees": [],
                "agents": [],
                "resources": {"oxygen": 90.0, "calories": 90.0, "integrity": 90.0, "wood": 0.0},
                "infrastructure": {},
                "active_tasks": [],
            }
        )
        rng = random.Random(42)
        added = ensure_viewport_trees(
            state,
            view_x0=5,
            view_y0=5,
            view_x1=10,
            view_y1=10,
            k=1,
            margin_tiles=3,
            rng=rng,
            global_cap=500,
            sample_tries_per_need=80,
        )
        self.assertGreaterEqual(added, 1)
        self.assertGreaterEqual(len(state.world_trees), 1)
        # At least one tree in the (expanded) viewport band
        inside = [
            t
            for t in state.world_trees
            if len(t) >= 2 and 2 <= int(t[0]) < 13 and 2 <= int(t[1]) < 13
        ]
        self.assertTrue(inside)


if __name__ == "__main__":
    unittest.main()
