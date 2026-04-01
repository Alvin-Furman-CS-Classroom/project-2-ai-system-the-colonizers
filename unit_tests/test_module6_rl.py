"""
Unit tests for Module 6: Survival Assessment & Adaptation

Tests survival probability assessment using heuristics or RL.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module6_rl.q_learning import TabularQAgent, discretize_colony_state
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

    def test_survival_capped_by_colonist_vitals(self):
        """High shared resources must not mask starving colonists (actual loss condition)."""
        assessor = SurvivalAssessor(use_rl=False)
        dying_agents = ColonyState(
            {
                "agents": [
                    {
                        "id": 0,
                        "name": "A",
                        "location": (0, 0),
                        "status": "active",
                        "oxygen": 8.0,
                        "calories": 80.0,
                        "integrity": 80.0,
                    },
                ],
                "resources": {"oxygen": 95.0, "calories": 95.0, "integrity": 95.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 0,
                "world_seed": 0,
                "difficulty": "normal",
            }
        )
        p = assessor.assess_survival(dying_agents)["survival_probability"]
        self.assertLess(p, 0.15)

    def test_rl_assessment_reflects_injected_q_values(self):
        """Deterministic: higher max_a Q(s,a) → higher reported survival (logistic)."""
        trained = SurvivalAssessor(use_rl=True)
        healthy = ColonyState(
            {
                "agents": [{"id": 0, "name": "A", "location": (0, 0), "status": "active",
                            "oxygen": 95, "calories": 95, "integrity": 95}],
                "resources": {"oxygen": 90.0, "calories": 90.0, "integrity": 90.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 0,
                "world_seed": 0,
                "difficulty": "normal",
            }
        )
        critical = ColonyState(
            {
                "agents": [{"id": 0, "name": "A", "location": (0, 0), "status": "active",
                            "oxygen": 40, "calories": 40, "integrity": 40}],
                "resources": {"oxygen": 25.0, "calories": 25.0, "integrity": 25.0},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 0,
                "world_seed": 0,
                "difficulty": "normal",
            }
        )
        sh = discretize_colony_state(healthy)
        sc = discretize_colony_state(critical)
        self.assertNotEqual(sh, sc)
        trained._q_agent.q[sh] = {"mild": 4.0, "normal": 4.0, "harsh": 3.0}
        trained._q_agent.q[sc] = {"mild": -3.0, "normal": -3.0, "harsh": -4.0}
        ah = trained.assess_survival(healthy)["survival_probability"]
        ac = trained.assess_survival(critical)["survival_probability"]
        self.assertGreater(ah, ac)
        self.assertEqual(trained.assess_survival(healthy)["assessment_method"], "Q-Learning")

    def test_offline_training_runs_without_error(self):
        trained = SurvivalAssessor(use_rl=True)
        trained.train_q_learning(episodes=50, max_steps_per_episode=5, epsilon=0.3, seed=1)
        p = trained.assess_survival(ColonyState())["survival_probability"]
        self.assertTrue(0.0 <= p <= 1.0)

    def test_standard_q_learning_backup(self):
        """Hand-check one Q-learning step: Q ← Q + α(r + γ max Q(s',·) − Q)."""
        agent = TabularQAgent(learning_rate=0.5, discount_factor=0.9)
        s0, s1 = 0, 1
        agent.q[s1]["mild"] = 4.0
        agent.q[s1]["normal"] = 3.0
        agent.q_learning_step(s0, "mild", reward=1.0, next_state_id=s1, terminal=False)
        # Q(s0,mild) = 0 + 0.5 * (1 + 0.9*4 - 0) = 0.5 * 4.6 = 2.3
        self.assertAlmostEqual(agent.q_sa(s0, "mild"), 2.3, places=5)
        agent.q_learning_step(s0, "mild", reward=0.0, next_state_id=s1, terminal=True)
        # Q = 2.3 + 0.5 * (0 + 0 - 2.3) = 1.15
        self.assertAlmostEqual(agent.q_sa(s0, "mild"), 1.15, places=5)


if __name__ == "__main__":
    unittest.main()
