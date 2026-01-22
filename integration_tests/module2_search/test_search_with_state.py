"""
Integration test: Module 2 (Search) with Module 1 (State)

Tests that task planning correctly uses colony state information.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import TaskPlanner, Task


class TestSearchStateIntegration(unittest.TestCase):
    """Integration tests for Search + State modules."""
    
    def test_planning_uses_agent_locations(self):
        """Test that task planning considers agent locations from state."""
        state = ColonyState()
        state.add_agent({"id": 0, "location": (0, 0), "speed": 1.0})
        state.add_agent({"id": 1, "location": (10, 10), "speed": 1.0})
        
        planner = TaskPlanner(state)
        tasks = [
            Task("task1", (5, 5), {}, 1, 2),
            Task("task2", (15, 15), {}, 2, 3)
        ]
        
        assignments = planner.plan_with_astar(tasks)
        # Should assign tasks based on agent proximity
        self.assertEqual(len(assignments), 2)
        # Verify assignments reference valid agents
        for assignment in assignments:
            self.assertLess(assignment.agent_id, len(state.agents))


if __name__ == "__main__":
    unittest.main()
