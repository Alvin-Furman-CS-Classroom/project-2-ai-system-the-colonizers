"""
Unit tests for Module 2: Task Planning & Logistics Optimization

Tests search algorithms (A*, IDA*, Beam Search) for task planning.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import TaskPlanner, Task


class TestTaskPlanner(unittest.TestCase):
    """Test cases for TaskPlanner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ColonyState()
        # Add some test agents
        self.state.add_agent({"id": 0, "location": (0, 0)})
        self.state.add_agent({"id": 1, "location": (5, 5)})
        self.planner = TaskPlanner(self.state)
    
    def test_plan_with_astar(self):
        """Test A* task planning."""
        tasks = [
            Task("task1", (10, 10), {}, 1, 2),
            Task("task2", (20, 20), {}, 2, 3)
        ]
        assignments = self.planner.plan_with_astar(tasks)
        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments[0].task.task_id, "task1")
    
    def test_plan_with_beam_search(self):
        """Test Beam Search task planning."""
        tasks = [
            Task("task1", (10, 10), {}, 1, 2)
        ]
        assignments = self.planner.plan_with_beam_search(tasks, beam_width=2)
        self.assertGreaterEqual(len(assignments), 1)
    
    def test_calculate_path_cost(self):
        """Test path cost calculation."""
        task1 = Task("t1", (0, 0), {}, 1, 1)
        task2 = Task("t2", (3, 4), {}, 1, 1)
        cost = self.planner._calculate_path_cost(task1, task2)
        self.assertAlmostEqual(cost, 5.0, places=1)  # Distance = 5


if __name__ == "__main__":
    unittest.main()
