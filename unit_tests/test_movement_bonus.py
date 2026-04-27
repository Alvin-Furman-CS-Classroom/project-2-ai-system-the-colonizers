"""Agent movement speed multiplier (no Pygame)."""

import unittest

from src.module1_state.movement_bonus import (
    effective_move_multiplier,
    prune_expired_speed_boosts,
)


class TestMovementBonus(unittest.TestCase):
    def test_default_multiplier_is_one(self):
        self.assertAlmostEqual(effective_move_multiplier({}, 5), 1.0)

    def test_speed_field_respected(self):
        self.assertAlmostEqual(effective_move_multiplier({"speed": 0.5}, 1), 0.5)
        self.assertAlmostEqual(effective_move_multiplier({"speed": 1.8}, 99), 1.8)

    def test_legacy_boost_keys_ignored_for_movement(self):
        """Permanent speed uses ``speed`` only; old temp keys do not stack."""
        agent = {
            "speed": 1.2,
            "speed_boost_end_turn": 999,
            "speed_boost_mult": 9.0,
        }
        self.assertAlmostEqual(effective_move_multiplier(agent, 1), 1.2)

    def test_prune_removes_stale_legacy_keys(self):
        agents = [
            {"id": 0, "speed_boost_end_turn": 3, "speed_boost_mult": 1.5},
        ]
        prune_expired_speed_boosts(agents, current_turn=5)
        self.assertNotIn("speed_boost_end_turn", agents[0])
        self.assertNotIn("speed_boost_mult", agents[0])


if __name__ == "__main__":
    unittest.main()
