import unittest

from src.game_engine import GameEngine
from src.module1_state.colony_state import ColonyState


class TestGillsMovement(unittest.TestCase):
    def test_grid_pathfind_accepts_gills_flag(self):
        """
        Smoke test: gills flag is plumbed into pathfinder.
        (We don't assert water presence in procedural terrain here.)
        """
        s = ColonyState(
            {
                "agents": [
                    {"id": 0, "name": "A", "location": (0, 0), "status": "active", "gills": True},
                ],
                "resources": {"oxygen": 90.0, "calories": 90.0, "integrity": 90.0, "wood": 0.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 0,
                "world_seed": 1,
                "difficulty": "normal",
                "world_min_x": -10,
                "world_max_x": 10,
                "world_min_y": -10,
                "world_max_y": 10,
            }
        )
        eng = GameEngine(s, survival_use_rl=False, survival_train_episodes=0)
        path = eng.get_path_for_agent_to_location(0, 2, 2)
        self.assertTrue(path)


if __name__ == "__main__":
    unittest.main()

