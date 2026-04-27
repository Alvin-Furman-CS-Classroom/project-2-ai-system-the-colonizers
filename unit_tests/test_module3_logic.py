"""
Unit tests for Module 3: Rule Enforcement Engine

Tests propositional logic rule checking and violation detection.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module3_logic.rule_engine import RuleEngine


class TestRuleEngine(unittest.TestCase):
    """Test cases for RuleEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ColonyState()
        self.rule_engine = RuleEngine()
    
    def test_check_violations_oxygen_zero(self):
        """Test detection of oxygen zero violation."""
        # Add agent with zero oxygen
        self.state.add_agent({"id": 0, "name": "Test Agent", "location": (0, 0), "oxygen": 0.0, "calories": 50.0}, validate=False)
        violations = self.rule_engine.check_violations(self.state)
        # Should find oxygen_zero_death violation
        self.assertGreater(len(violations), 0)
        oxygen_violations = [v for v in violations if "oxygen" in v.violation_type]
        self.assertGreater(len(oxygen_violations), 0)
    
    def test_apply_violations_death(self):
        """Test applying death consequence marks agents as dead (but keeps them in state)."""
        self.state.add_agent(
            {
                "id": 0,
                "name": "Test Agent",
                "location": (0, 0),
                "oxygen": 0.0,
                "calories": 50.0,
            },
            validate=False,
        )
        violations = self.rule_engine.check_violations(self.state)
        initial_count = len(self.state.agents)
        self.assertGreater(initial_count, 0)  # Ensure agent was added
        self.rule_engine.apply_violations(self.state, violations)
        # Agent should remain in the list but be marked dead
        self.assertEqual(len(self.state.agents), initial_count)
        self.assertEqual(self.state.agents[0].get("status"), "dead")
    
    def test_evaluate_state(self):
        """Test complete state evaluation."""
        self.state.add_agent({"id": 0, "name": "Test Agent", "location": (0, 0), "oxygen": 50.0, "calories": 50.0}, validate=False)
        result = self.rule_engine.evaluate_state(self.state)
        self.assertIn("violations_found", result)
        self.assertIn("state_after", result)

    def test_multiple_deaths_removal_order(self):
        """
        Test that multiple agents with zero oxygen are all marked dead.

        Previously, death removed agents from the list; now it preserves them
        in `state.agents` with status \"dead\" so that other modules (e.g. UI)
        can still render their final positions.
        """
        self.state.add_agent(
            {"id": 0, "name": "A", "location": (0, 0), "oxygen": 0.0, "calories": 50.0},
            validate=False,
        )
        self.state.add_agent(
            {"id": 1, "name": "B", "location": (1, 1), "oxygen": 0.0, "calories": 50.0},
            validate=False,
        )
        self.state.add_agent(
            {"id": 2, "name": "C", "location": (2, 2), "oxygen": 50.0, "calories": 50.0},
            validate=False,
        )
        violations = self.rule_engine.check_violations(self.state)
        self.rule_engine.apply_violations(self.state, violations)

        # All three agents remain; the two with zero oxygen are marked dead,
        # and the healthy one stays non-dead.
        self.assertEqual(len(self.state.agents), 3)
        statuses = {a["name"]: a.get("status") for a in self.state.agents}
        self.assertEqual(statuses["A"], "dead")
        self.assertEqual(statuses["B"], "dead")
        self.assertNotEqual(statuses["C"], "dead")


if __name__ == "__main__":
    unittest.main()
