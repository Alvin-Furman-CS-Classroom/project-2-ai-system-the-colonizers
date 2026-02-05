"""
Unit tests for Module 2: Task Planning & Logistics Optimization

Tests search algorithms (A*, IDA*, Beam Search) for task planning.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import TaskPlanner, Task, ColonyGraph, PathResult


class TestColonyGraph(unittest.TestCase):
    """Test cases for ColonyGraph class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.graph = ColonyGraph.create_default_colony_graph()
    
    def test_graph_creation(self):
        """Test graph creation."""
        self.assertGreater(len(self.graph.nodes), 0)
        self.assertIn("section_alpha", self.graph.nodes)
    
    def test_add_node(self):
        """Test adding nodes."""
        graph = ColonyGraph()
        graph.add_node("test_node", (5, 5))
        self.assertIn("test_node", graph.nodes)
        self.assertEqual(graph.node_positions["test_node"], (5, 5))
    
    def test_add_edge(self):
        """Test adding edges."""
        graph = ColonyGraph()
        graph.add_edge("A", "B", 1.5)
        self.assertIn("A", graph.nodes)
        self.assertIn("B", graph.nodes)
        self.assertEqual(graph.edges["A"]["B"], 1.5)
        self.assertEqual(graph.edges["B"]["A"], 1.5)  # Bidirectional
    
    def test_get_neighbors(self):
        """Test getting neighbors."""
        neighbors = self.graph.get_neighbors("bridge")
        self.assertGreater(len(neighbors), 0)
        # Check that neighbors are tuples of (node, cost)
        for neighbor, cost in neighbors:
            self.assertIsInstance(neighbor, str)
            self.assertIsInstance(cost, (int, float))
    
    def test_heuristic(self):
        """Test heuristic function."""
        h = self.graph.heuristic("section_alpha", "section_beta")
        self.assertGreaterEqual(h, 0.0)


class TestTaskPlanner(unittest.TestCase):
    """Test cases for TaskPlanner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ColonyState()
        # Add some test agents with locations that map to graph nodes
        self.state.add_agent({"id": 0, "name": "Agent 0", "location": (0, 0)}, validate=False)
        self.state.add_agent({"id": 1, "name": "Agent 1", "location": (20, 0)}, validate=False)
        self.planner = TaskPlanner(self.state)
    
    def test_astar_pathfinding(self):
        """Test A* pathfinding on graph."""
        result = self.planner.astar_path("section_alpha", "section_beta")
        self.assertTrue(result.found)
        self.assertGreater(len(result.path), 0)
        self.assertEqual(result.path[0], "section_alpha")
        self.assertEqual(result.path[-1], "section_beta")
        self.assertGreaterEqual(result.cost, 0.0)
    
    def test_astar_pathfinding_same_node(self):
        """Test A* pathfinding when start == goal."""
        result = self.planner.astar_path("section_alpha", "section_alpha")
        self.assertTrue(result.found)
        self.assertEqual(len(result.path), 1)
        self.assertEqual(result.cost, 0.0)
    
    def test_idastar_pathfinding(self):
        """Test IDA* pathfinding."""
        result = self.planner.idastar_path("section_alpha", "storage")
        self.assertTrue(result.found)
        self.assertGreater(len(result.path), 0)
        self.assertEqual(result.path[0], "section_alpha")
        self.assertEqual(result.path[-1], "storage")
    
    def test_plan_with_astar(self):
        """Test A* task planning."""
        tasks = [
            Task("task1", (0, 0), {}, 1, 2),
            Task("task2", (20, 0), {}, 2, 3)
        ]
        assignments = self.planner.plan_with_astar(tasks)
        self.assertEqual(len(assignments), 2)
        # Check that assignments have required fields
        for assignment in assignments:
            self.assertIsNotNone(assignment.task)
            self.assertIsNotNone(assignment.agent_id)
            self.assertGreaterEqual(assignment.start_time, 0)
            self.assertGreaterEqual(assignment.completion_time, assignment.start_time)
    
    def test_plan_with_beam_search(self):
        """Test Beam Search task planning."""
        tasks = [
            Task("task1", (0, 0), {}, 1, 2)
        ]
        assignments = self.planner.plan_with_beam_search(tasks, beam_width=2)
        self.assertGreaterEqual(len(assignments), 1)
        # Check assignment structure
        self.assertEqual(assignments[0].task.task_id, "task1")
    
    def test_calculate_travel_cost(self):
        """Test travel cost calculation using pathfinding."""
        task = Task("test_task", (20, 0), {}, 1, 1)
        cost, path = self.planner.calculate_travel_cost(0, task)
        self.assertGreaterEqual(cost, 0.0)
        # Path may be empty if nodes don't match, but cost should be calculated
    
    def test_get_agent_location_node(self):
        """Test getting agent location as graph node."""
        node = self.planner.get_agent_location_node(0)
        # Should return a node (closest to agent's position)
        self.assertIsNotNone(node)
    
    def test_get_task_location_node(self):
        """Test getting task location as graph node."""
        task = Task("test", (0, 0), {}, 1, 1)
        node = self.planner.get_task_location_node(task)
        self.assertIsNotNone(node)
    
    def test_calculate_path_cost_deprecated(self):
        """Test deprecated path cost calculation (backward compatibility)."""
        task1 = Task("t1", (0, 0), {}, 1, 1)
        task2 = Task("t2", (3, 4), {}, 1, 1)
        cost = self.planner._calculate_path_cost(task1, task2)
        self.assertAlmostEqual(cost, 5.0, places=1)  # Distance = 5
    
    def test_empty_tasks(self):
        """Test planning with empty task list."""
        assignments = self.planner.plan_with_astar([])
        self.assertEqual(len(assignments), 0)
    
    def test_no_agents(self):
        """Test planning with no agents."""
        empty_state = ColonyState()
        planner = TaskPlanner(empty_state)
        tasks = [Task("task1", (0, 0), {}, 1, 1)]
        assignments = planner.plan_with_astar(tasks)
        self.assertEqual(len(assignments), 0)


if __name__ == "__main__":
    unittest.main()
