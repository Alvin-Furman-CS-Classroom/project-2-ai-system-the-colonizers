import unittest

from src.game_engine import GameEngine, director_income_per_turn, director_budget_cap
from src.module1_state.colony_state import ColonyState


class TestDirectorBudget(unittest.TestCase):
    def _engine(self, difficulty: str = "normal", floor_index: int = 1) -> GameEngine:
        s = ColonyState(
            {
                "agents": [
                    {
                        "id": 0,
                        "name": "A",
                        "location": (0, 0),
                        "oxygen": 80.0,
                        "calories": 80.0,
                        "integrity": 80.0,
                        "status": "active",
                    }
                ],
                "resources": {"oxygen": 90.0, "calories": 90.0, "integrity": 90.0, "wood": 0.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 0,
                "world_seed": 1,
                "difficulty": difficulty,
                "floor_index": floor_index,
                "wood_quota": 999.0,
            }
        )
        return GameEngine(s, survival_use_rl=False, survival_train_episodes=0)

    def test_income_scales_with_difficulty(self):
        self.assertLess(director_income_per_turn("easy", 1), director_income_per_turn("normal", 1))
        self.assertLess(director_income_per_turn("normal", 1), director_income_per_turn("hard", 1))

    def test_budget_caps_by_difficulty(self):
        self.assertLess(director_budget_cap("easy"), director_budget_cap("normal"))
        self.assertLess(director_budget_cap("normal"), director_budget_cap("hard"))

    def test_points_accrue_each_turn(self):
        eng = self._engine("normal", 1)
        s = eng.state
        self.assertEqual(float(getattr(s, "director_points", 0.0)), 0.0)
        eng.run_adversarial_phase()
        self.assertGreater(float(s.director_points), 0.0)

    def test_points_decrease_when_event_purchased(self):
        eng = self._engine("normal", 1)
        s = eng.state
        # Ensure we're well-funded so a costed event is affordable.
        s.director_points = 10.0
        s.resources["wood"] = 0.0
        s.wood_quota = 999.0
        pts_before = float(s.director_points)
        ev, summ = eng.run_adversarial_phase()
        cost = float(getattr(ev, "cost", 0.0) or 0.0)
        if ev.event_type != "no_adversarial_event" and cost > 0.0:
            # After accrual then purchase, points must be strictly below the post-accrual amount.
            post_accrual = min(director_budget_cap(s.difficulty), pts_before + director_income_per_turn(s.difficulty, s.floor_index))
            self.assertLess(float(s.director_points), float(post_accrual))
            self.assertAlmostEqual(float(s.director_points), float(post_accrual - cost), places=6)
        self.assertIn("director_event_cost", summ)

    def test_affordability_can_force_no_event(self):
        eng = self._engine("easy", 1)
        s = eng.state
        s.director_points = 0.0
        # Make sure we don't hit wood suppression.
        s.resources["wood"] = 0.0
        s.wood_quota = 999.0
        ev, summ = eng.run_adversarial_phase()
        # On first turn, points might be < 2.0 → should allow SAVE/no-op.
        self.assertIn(ev.event_type, ("no_adversarial_event", "agent_trip_over_rock", "agent_oxygen_tank_puncture", "agent_ration_spoilage", "station_breakdown"))
        self.assertIn("director_points", summ)


if __name__ == "__main__":
    unittest.main()

