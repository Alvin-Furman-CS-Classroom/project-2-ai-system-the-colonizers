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


if __name__ == "__main__":
    unittest.main()
