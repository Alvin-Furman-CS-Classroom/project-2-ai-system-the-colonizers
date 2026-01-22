"""
Integration test: Module 6 (RL) with Module 1 (State)

Tests that survival assessment correctly evaluates colony state.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module6_rl.survival_assessor import SurvivalAssessor


class TestRLStateIntegration(unittest.TestCase):
    """Integration tests for RL + State modules."""
    
    def test_assessment_reflects_state(self):
        """Test that assessment reflects current state conditions."""
        state = ColonyState()
        state.resources["oxygen"] = 10.0
        state.resources["calories"] = 5.0
        state.add_agent({"id": 0})
        
        assessor = SurvivalAssessor(use_rl=False)
        assessment = assessor.assess_survival(state)
        
        # Should identify critical threats
        self.assertGreater(len(assessment["critical_threats"]), 0)
        # Survival probability should be low
        self.assertLess(assessment["survival_probability"], 0.5)


if __name__ == "__main__":
    unittest.main()
