"""
Unit tests for Module 4: Adversarial Event Selection

Tests game theory algorithms (Minimax, Alpha-Beta, MCTS) for event selection.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import AIDirector, Event


class TestAIDirector(unittest.TestCase):
    """Test cases for AIDirector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.events = [
            Event("hull_breach", "section_alpha", 0.5, {"oxygen": -20.0}, "Test breach"),
            Event("resource_shortage", "storage", 0.3, {"calories": -15.0}, "Test shortage")
        ]
        self.director = AIDirector(self.events)
        self.state = ColonyState()
    
    def test_select_event_minimax(self):
        """Test Minimax event selection."""
        event = self.director.select_event_minimax(self.state)
        self.assertIsInstance(event, Event)
        self.assertIn(event, self.events)
    
    def test_identify_vulnerabilities(self):
        """Test vulnerability identification."""
        self.state.resources["oxygen"] = 20.0  # Low oxygen
        vulnerabilities = self.director.identify_vulnerabilities(self.state)
        self.assertGreater(len(vulnerabilities), 0)
        self.assertTrue(any("oxygen" in v.lower() for v in vulnerabilities))
    
    def test_evaluate_challenge(self):
        """Test challenge evaluation."""
        event = self.events[0]
        challenge = self.director._evaluate_challenge(self.state, event)
        self.assertIsInstance(challenge, float)
        self.assertGreaterEqual(challenge, 0.0)

    def test_isolation_scores_with_station_layout(self):
        """Isolation scoring should return normalized values for each resource type."""
        self.state.infrastructure.update({
            "oxy_station_1": {
                "kind": "resource_station",
                "resource_type": "oxygen",
                "center": (-20, 0),
                "size": 2,
                "status": "operational",
            },
            "cal_station_1": {
                "kind": "resource_station",
                "resource_type": "calories",
                "center": (0, 0),
                "size": 2,
                "status": "operational",
            },
            "int_station_1": {
                "kind": "resource_station",
                "resource_type": "integrity",
                "center": (20, 0),
                "size": 3,
                "status": "operational",
            },
        })
        scores = self.director._isolation_scores(self.state)
        self.assertIn("oxygen", scores)
        self.assertIn("calories", scores)
        self.assertIn("integrity", scores)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in scores.values()))

    def test_repetition_penalty_reduces_score(self):
        """Recent repeated targets/types should reduce candidate score."""
        self.state.infrastructure["__director_memory__"] = {
            "recent_events": [
                {
                    "turn": 3,
                    "event_type": "resource_shortage",
                    "target_station_id": "storage",
                    "target_resource": "calories",
                }
            ]
        }
        self.state.turn_number = 4
        event = Event("resource_shortage", "storage", 0.3, {"calories": -15.0}, "Test shortage")
        penalized = self.director._apply_repetition_penalty(self.state, event, 1.0)
        self.assertLess(penalized, 1.0)


if __name__ == "__main__":
    unittest.main()
