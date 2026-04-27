"""
Unit tests for GameEngine station blocking, repair progression, and grid pathfinding.
"""

import unittest
from unittest.mock import patch

from src.game_engine import GameEngine, BASE_REPAIR_TURNS
from src.module1_state.colony_state import ColonyState


def _open_rect_passable(wx0: int, wx1: int, wy0: int, wy1: int):
    """Factory: _is_tile_passable that treats [wx0,wx1)×[wy0,wy1) as open land."""

    def _fn(x: int, y: int, _exclude_agent_id=None) -> bool:
        return wx0 <= x < wx1 and wy0 <= y < wy1

    return _fn


class TestGameEngineStationRepairs(unittest.TestCase):
    """Test failed-station repair progression and pathing behavior."""

    def setUp(self):
        self.state = ColonyState({"world_seed": 42, "difficulty": "normal"})
        # Add four living agents; three on failed station footprint, one elsewhere.
        for i, loc in enumerate([(0, 0), (1, 0), (0, 1), (8, 8)]):
            self.state.add_agent(
                {
                    "id": i,
                    "name": f"A{i}",
                    "location": loc,
                    "oxygen": 80.0,
                    "calories": 70.0,
                    "integrity": 90.0,
                    "status": "active",
                },
                validate=False,
            )

        self.state.infrastructure["oxy_station_1"] = {
            "kind": "resource_station",
            "station_id": "oxy_station_1",
            "resource_type": "oxygen",
            "center": (0, 0),
            "size": 2,
            "status": "failed",
            "repair_remaining_turns": BASE_REPAIR_TURNS,
            "repair_agent_id": None,
        }
        self.engine = GameEngine(self.state, survival_use_rl=False)

    def test_failed_station_tile_is_walkable(self):
        """Failed station tiles should remain walkable so agents can step on to repair."""
        self.assertTrue(self.engine._is_tile_passable(0, 0))

    def test_goal_exception_allows_repair_destination(self):
        """Pathfinding should allow blocked goal tile as destination for repair."""
        # Use a footprint edge tile so there is an adjacent passable approach tile.
        path = self.engine.get_path_for_agent_to_location(agent_id=3, world_x=1, world_y=1)
        self.assertTrue(path)
        self.assertEqual(path[-1], (1, 1))

    def test_repair_progress_scales_with_agent_cap(self):
        """Repair decrement should scale with agents present up to cap."""
        report = self.engine._advance_station_repairs()
        station = self.state.infrastructure["oxy_station_1"]
        self.assertEqual(report["progressed"][0]["effective_agents"], 3)
        self.assertEqual(station["repair_remaining_turns"], BASE_REPAIR_TURNS - 3)

    def test_repair_pauses_without_agents_on_station(self):
        """Repair should pause when no living agents are on station footprint."""
        self.engine._advance_station_repairs()
        # Move all agents away
        for idx, agent in enumerate(self.state.agents):
            self.state.update_agent(idx, {"location": (10 + idx, 10 + idx)}, validate=False)
        before = self.state.infrastructure["oxy_station_1"]["repair_remaining_turns"]
        report = self.engine._advance_station_repairs()
        after = self.state.infrastructure["oxy_station_1"]["repair_remaining_turns"]
        self.assertEqual(before, after)
        self.assertIn("oxy_station_1", report["paused"])

    def test_handoff_and_completion(self):
        """Repair should allow handoff and eventually complete."""
        # Tick 1 with three agents present
        self.engine._advance_station_repairs()
        # Move two away, keep one at station for handoff/continuation
        self.state.update_agent(0, {"location": (9, 9)}, validate=False)
        self.state.update_agent(1, {"location": (9, 10)}, validate=False)

        # Continue ticks until repaired
        for _ in range(BASE_REPAIR_TURNS):
            self.engine._advance_station_repairs()
            if self.state.infrastructure["oxy_station_1"]["status"] == "operational":
                break

        station = self.state.infrastructure["oxy_station_1"]
        self.assertEqual(station["status"], "operational")
        self.assertEqual(station["repair_remaining_turns"], 0)
        self.assertIsNone(station["repair_agent_id"])


class TestGameEngineLongRangePathfinding(unittest.TestCase):
    """A* must complete on large worlds (fixed iteration cap was ~5k; far too low for 100×100+)."""

    def test_grid_pathfind_diagonal_corner_to_corner_120(self):
        state = ColonyState(
            {
                "world_seed": 1,
                "difficulty": "normal",
                "world_min_x": 0,
                "world_max_x": 120,
                "world_min_y": 0,
                "world_max_y": 120,
            }
        )
        engine = GameEngine(state, survival_use_rl=False)
        with patch.object(engine, "_is_tile_passable", _open_rect_passable(0, 120, 0, 120)):
            path = engine._grid_pathfind((0, 0), (119, 119))
        self.assertTrue(path, "expected a path on open 120×120 grid")
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (119, 119))
        # Monotonic progress toward goal along an optimal-ish octile path
        self.assertGreaterEqual(len(path), 119)

    def test_grid_pathfind_navigates_slit_wall_80(self):
        """Vertical wall with one gap; start and goal on opposite sides."""
        state = ColonyState(
            {
                "world_seed": 2,
                "difficulty": "normal",
                "world_min_x": 0,
                "world_max_x": 80,
                "world_min_y": 0,
                "world_max_y": 80,
            }
        )
        blocked = {(40, y) for y in range(80) if y != 40}

        def passable(x: int, y: int, _exclude=None) -> bool:
            if not (0 <= x < 80 and 0 <= y < 80):
                return False
            return (x, y) not in blocked

        engine = GameEngine(state, survival_use_rl=False)
        with patch.object(engine, "_is_tile_passable", passable):
            path = engine._grid_pathfind((10, 40), (70, 40))
        self.assertTrue(path)
        self.assertEqual(path[0], (10, 40))
        self.assertEqual(path[-1], (70, 40))
        for px, py in path:
            self.assertNotIn((px, py), blocked)

    def test_get_path_agent_integration_large_open_200(self):
        state = ColonyState(
            {
                "world_seed": 3,
                "difficulty": "normal",
                "world_min_x": 0,
                "world_max_x": 200,
                "world_min_y": 0,
                "world_max_y": 200,
            }
        )
        state.add_agent(
            {
                "id": 0,
                "name": "P0",
                "location": (0, 0),
                "oxygen": 80.0,
                "calories": 70.0,
                "integrity": 90.0,
                "status": "active",
            },
            validate=False,
        )
        engine = GameEngine(state, survival_use_rl=False)
        with patch.object(engine, "_is_tile_passable", _open_rect_passable(0, 200, 0, 200)):
            path = engine.get_path_for_agent_to_location(0, 199, 199)
        self.assertTrue(path)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (199, 199))


if __name__ == "__main__":
    unittest.main()

