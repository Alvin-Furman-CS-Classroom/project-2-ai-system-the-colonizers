"""
Integration test: Module 3 (Logic) with Module 1 (State)

Tests that rule enforcement correctly modifies colony state.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module3_logic.rule_engine import RuleEngine


class TestLogicStateIntegration(unittest.TestCase):
    """Integration tests for Logic + State modules."""
    
    def test_rule_violation_updates_state(self):
        """Test that rule violations properly update state."""
        state = ColonyState()
        state.add_agent({"id": 0, "oxygen": 0.0, "calories": 50.0})
        initial_agent_count = len(state.agents)
        
        rule_engine = RuleEngine()
        result = rule_engine.evaluate_state(state)
        
        # Agent with zero oxygen should be removed
        self.assertLess(len(state.agents), initial_agent_count)
        self.assertGreater(result["violations_found"], 0)


if __name__ == "__main__":
    unittest.main()
