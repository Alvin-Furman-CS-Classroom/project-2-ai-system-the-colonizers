import os
import tempfile
import unittest

from src.module6_rl.q_learning import TabularQAgent
from src.module4_game_theory.budget_director import TabularDirectorQ, STANDARD_ACTIONS


class TestRLPersistence(unittest.TestCase):
    def test_survival_qagent_save_load_roundtrip(self):
        agent = TabularQAgent()
        agent.q_learning_step(1, agent.actions[0], 1.0, 2, terminal=False)
        agent.q_learning_step(1, agent.actions[1], 0.5, 2, terminal=False)

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "survival_q.json")
            agent.save_json(p)
            self.assertTrue(os.path.exists(p))

            agent2 = TabularQAgent()
            ok = agent2.try_load_json(p, merge=False)
            self.assertTrue(ok)
            self.assertNotEqual(agent2.q_sa(1, agent.actions[0]), 0.0)

    def test_director_q_save_load_roundtrip(self):
        q = TabularDirectorQ()
        q.update(10, STANDARD_ACTIONS[0], 1.2, 11)

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "director_q.json")
            q.save_json(p)
            self.assertTrue(os.path.exists(p))

            q2 = TabularDirectorQ()
            ok = q2.try_load_json(p, merge=False)
            self.assertTrue(ok)
            self.assertIn(10, q2.q)

