"""Multi-floor progression: trees, wood quota, adversarial suppression, carryover knobs."""

import random
import unittest

from src.module1_state.colony_state import ColonyState
from src.module1_state.floor_carryover import (
    next_floor_knobs,
    summarize_finished_floor,
)
from src.module1_state.tree_generation import (
    generate_world_trees,
    maybe_spawn_progression_tree,
    try_harvest_trees,
)
from src.game_engine import GameEngine, NO_ADVERSARY_EVENT
from src.module6_rl.q_learning import discretize_colony_state


class TestMultiFloor(unittest.TestCase):
    def _state(self, **kw) -> ColonyState:
        data = {
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
            "turn_number": 3,
            "world_seed": 42,
            "difficulty": "normal",
            "world_min_x": -5,
            "world_max_x": 5,
            "world_min_y": -5,
            "world_max_y": 5,
            "floor_index": 1,
            "wood_quota": 5.0,
            "world_trees": [[1, 1], [2, 2]],
            "floor_start_turn": 0,
            "floor_disasters_count": 2,
            "floor_deaths_count": 1,
            "turn_wood_quota_met": 2,
            "rl_carryover_stress_bin": 0,
        }
        data.update(kw)
        return ColonyState(data)

    def test_tree_generation_deterministic(self):
        s = self._state()
        a = generate_world_trees(s, -5, 5, -5, 5, tree_density_multiplier=1.0)
        b = generate_world_trees(s, -5, 5, -5, 5, tree_density_multiplier=1.0)
        self.assertEqual(a, b)
        s2 = ColonyState(s.to_dict())
        s2.difficulty = "hard"
        h = generate_world_trees(s2, -5, 5, -5, 5, tree_density_multiplier=1.0)
        s_easy = ColonyState(s.to_dict())
        s_easy.difficulty = "easy"
        e = generate_world_trees(s_easy, -5, 5, -5, 5, tree_density_multiplier=1.0)
        self.assertGreaterEqual(len(e), len(h))

    def test_harvest_adds_wood_and_removes_tree(self):
        s = self._state(world_trees=[[0, 0]])
        n = try_harvest_trees(s, [(0, 0)])
        self.assertEqual(n, 1)
        self.assertEqual(s.resources["wood"], 1.0)
        self.assertEqual(s.world_trees, [])

    def test_adversarial_suppressed_when_wood_meets_quota(self):
        s = self._state(resources={**self._state().resources, "wood": 10.0}, wood_quota=5.0)
        eng = GameEngine(s, survival_use_rl=False, survival_train_episodes=0)
        ev, summ = eng.run_adversarial_phase()
        self.assertEqual(ev.event_type, NO_ADVERSARY_EVENT.event_type)
        self.assertTrue(summ.get("suppressed_by_wood_quota"))

    def test_discretize_changes_with_floor_and_stress(self):
        a = self._state(floor_index=1, rl_carryover_stress_bin=0)
        b = self._state(floor_index=3, rl_carryover_stress_bin=2)
        self.assertNotEqual(discretize_colony_state(a), discretize_colony_state(b))

    def test_next_floor_knobs_increase_with_rough_prior_floor(self):
        summary = {
            "disasters_total": 6,
            "deaths_total": 2,
            "avg_pool_resources": 30.0,
        }
        k0 = next_floor_knobs([], 2, "normal")
        k1 = next_floor_knobs([summary], 2, "normal")
        self.assertGreaterEqual(k1["wood_quota_adjust"], k0["wood_quota_adjust"])
        self.assertGreaterEqual(k1["director_aggression_delta"], k0["director_aggression_delta"])

    def test_summarize_finished_floor_shape(self):
        s = self._state()
        d = summarize_finished_floor(s, 0, 2, 1, 2)
        self.assertIn("wood_turns_to_quota", d)
        self.assertEqual(d["disasters_total"], 2)

    def test_progression_tree_spawns_when_short_of_quota(self):
        s = ColonyState(
            {
                "agents": [],
                "resources": {"oxygen": 90.0, "calories": 90.0, "integrity": 90.0, "wood": 0.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 2,
                "world_seed": 4242,
                "difficulty": "normal",
                "floor_index": 1,
                "wood_quota": 80.0,
                "world_trees": [],
                "world_min_x": -15,
                "world_max_x": 15,
                "world_min_y": -15,
                "world_max_y": 15,
            }
        )
        before = len(s.world_trees)
        ok = maybe_spawn_progression_tree(
            s, rng=random.Random(99), spawn_probability=1.0, max_attempts=200
        )
        self.assertTrue(ok)
        self.assertGreater(len(s.world_trees), before)

    def test_progression_tree_skips_when_potential_wood_suffices(self):
        s = ColonyState(
            {
                "agents": [],
                "resources": {"oxygen": 90.0, "calories": 90.0, "integrity": 90.0, "wood": 2.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 1,
                "world_seed": 1,
                "difficulty": "normal",
                "wood_quota": 10.0,
                "world_trees": [[x, x] for x in range(8)],
                "world_min_x": -5,
                "world_max_x": 5,
                "world_min_y": -5,
                "world_max_y": 5,
            }
        )
        n = len(s.world_trees)
        ok = maybe_spawn_progression_tree(s, rng=random.Random(1), spawn_probability=1.0)
        self.assertFalse(ok)
        self.assertEqual(len(s.world_trees), n)


if __name__ == "__main__":
    unittest.main()
