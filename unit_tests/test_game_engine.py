"""
Unit tests for GameEngine station blocking and repair progression.
"""

import unittest

from src.game_engine import GameEngine, BASE_REPAIR_TURNS
from src.module1_state.colony_state import ColonyState


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
        self.engine = GameEngine(self.state)

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


if __name__ == "__main__":
    unittest.main()

