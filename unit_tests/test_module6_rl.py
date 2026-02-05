"""
Unit tests for Module 6: Survival Assessment & Adaptation

Tests survival probability assessment using heuristics or RL.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module6_rl.survival_assessor import SurvivalAssessor


class TestSurvivalAssessor(unittest.TestCase):
    """Test cases for SurvivalAssessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ColonyState()
        self.assessor = SurvivalAssessor(use_rl=False)  # Use heuristics for testing
    
    def test_assess_survival_healthy(self):
        """Test survival assessment for healthy colony."""
        assessment = self.assessor.assess_survival(self.state)
        self.assertIn("survival_probability", assessment)
        self.assertGreaterEqual(assessment["survival_probability"], 0.0)
        self.assertLessEqual(assessment["survival_probability"], 1.0)
    
    def test_assess_survival_critical(self):
        """Test survival assessment for critical colony."""
        self.state.resources["oxygen"] = 10.0
        self.state.resources["calories"] = 5.0
        assessment = self.assessor.assess_survival(self.state)
        # Should have low survival probability
        self.assertLess(assessment["survival_probability"], 0.5)
        self.assertGreater(len(assessment["critical_threats"]), 0)
    
    def test_identify_critical_threats(self):
        """Test critical threat identification."""
        self.state.resources["oxygen"] = 15.0  # Low (< 20.0) so should be "oxygen_depletion"
        threats = self.assessor._identify_critical_threats(self.state)
        # Check for either "oxygen_depletion" (if < 20) or "oxygen_low" (if < 50)
        self.assertTrue("oxygen_depletion" in threats or "oxygen_low" in threats)
    
    def test_estimate_time_to_failure(self):
        """Test time to failure estimation."""
        self.state.resources["oxygen"] = 25.0
        assessment = self.assessor.assess_survival(self.state)
        # Should have time_to_failure estimate if survival prob is low
        if assessment["survival_probability"] < 0.8:
            self.assertIsNotNone(assessment.get("time_to_failure"))


if __name__ == "__main__":
    unittest.main()
