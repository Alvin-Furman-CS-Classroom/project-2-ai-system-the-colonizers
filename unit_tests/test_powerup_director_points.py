import unittest

from visual_game import (
    POWERUP_AUTO_CALORIES,
    POWERUP_AUTO_INTEGRITY,
    POWERUP_AUTO_OXYGEN,
    POWERUP_SPEED_BOOST,
    POWERUP_GILLS,
    director_points_gain_for_powerup,
)


class TestPowerupDirectorPoints(unittest.TestCase):
    def test_speed_more_than_auto(self):
        auto = director_points_gain_for_powerup(POWERUP_AUTO_OXYGEN, "normal")
        spd = director_points_gain_for_powerup(POWERUP_SPEED_BOOST, "normal")
        self.assertGreater(spd, auto)

    def test_difficulty_scales(self):
        n = director_points_gain_for_powerup(POWERUP_AUTO_CALORIES, "normal")
        h = director_points_gain_for_powerup(POWERUP_AUTO_INTEGRITY, "hard")
        e = director_points_gain_for_powerup(POWERUP_AUTO_OXYGEN, "easy")
        self.assertGreater(h, n)
        self.assertLess(e, n)

    def test_gills_has_gain(self):
        g = director_points_gain_for_powerup(POWERUP_GILLS, "normal")
        self.assertGreater(g, 0.0)


if __name__ == "__main__":
    unittest.main()

