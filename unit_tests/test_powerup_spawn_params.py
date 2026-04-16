"""Difficulty tables for powerup counts / spawn rates (imports visual_game → pygame)."""

import unittest

import pygame

from visual_game import (
    POWERUP_AUTO_CALORIES,
    POWERUP_AUTO_INTEGRITY,
    POWERUP_AUTO_OXYGEN,
    POWERUP_GILLS,
    POWERUP_SPEED_BOOST,
    _powerup_params_for_difficulty,
    _random_powerup_type,
)


class TestPowerupSpawnParams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.set_mode((1, 1), pygame.HIDDEN)

    def test_easy_more_generous_than_hard(self):
        e = _powerup_params_for_difficulty("easy")
        h = _powerup_params_for_difficulty("hard")
        self.assertGreaterEqual(e["max_on_map"], h["max_on_map"])
        self.assertGreaterEqual(e["turn_spawn_p"], h["turn_spawn_p"])

    def test_random_type_includes_speed(self):
        rng = __import__("random").Random(123)
        seen = {_random_powerup_type(rng, _powerup_params_for_difficulty("easy")["weights"]) for _ in range(50)}
        self.assertIn(POWERUP_SPEED_BOOST, seen)

    def test_unique_spawn_prefers_missing_type(self):
        rng = __import__("random").Random(5)
        weights = _powerup_params_for_difficulty("normal")["weights"]
        present = {POWERUP_AUTO_OXYGEN, POWERUP_AUTO_CALORIES, POWERUP_AUTO_INTEGRITY, POWERUP_SPEED_BOOST}
        # Only gills is missing; we should always choose it while missing types exist.
        for _ in range(10):
            t = _random_powerup_type(rng, weights, present_types=present)
            self.assertEqual(t, POWERUP_GILLS)

    def test_unique_spawn_falls_back_when_all_present(self):
        rng = __import__("random").Random(9)
        weights = _powerup_params_for_difficulty("normal")["weights"]
        present = {
            POWERUP_AUTO_OXYGEN,
            POWERUP_AUTO_CALORIES,
            POWERUP_AUTO_INTEGRITY,
            POWERUP_SPEED_BOOST,
            POWERUP_GILLS,
        }
        # All types already present; should behave like weighted random (i.e., return any valid type).
        t = _random_powerup_type(rng, weights, present_types=present)
        self.assertIn(
            t,
            {
                POWERUP_AUTO_OXYGEN,
                POWERUP_AUTO_CALORIES,
                POWERUP_AUTO_INTEGRITY,
                POWERUP_SPEED_BOOST,
                POWERUP_GILLS,
            },
        )


if __name__ == "__main__":
    unittest.main()
