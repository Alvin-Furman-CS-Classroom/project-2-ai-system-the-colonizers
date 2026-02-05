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
        """Test applying death consequence."""
        self.state.add_agent({"id": 0, "name": "Test Agent", "location": (0, 0), "oxygen": 0.0, "calories": 50.0}, validate=False)
        violations = self.rule_engine.check_violations(self.state)
        initial_count = len(self.state.agents)
        self.assertGreater(initial_count, 0)  # Ensure agent was added
        self.rule_engine.apply_violations(self.state, violations)
        # Agent should be removed
        self.assertLess(len(self.state.agents), initial_count)
    
    def test_evaluate_state(self):
        """Test complete state evaluation."""
        self.state.add_agent({"id": 0, "name": "Test Agent", "location": (0, 0), "oxygen": 50.0, "calories": 50.0}, validate=False)
        result = self.rule_engine.evaluate_state(self.state)
        self.assertIn("violations_found", result)
        self.assertIn("state_after", result)


if __name__ == "__main__":
    unittest.main()
