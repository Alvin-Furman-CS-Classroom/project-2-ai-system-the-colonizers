"""
Unit tests for Module 1: Colony State Management

Tests the core state representation and resource management.
"""

import unittest
from src.module1_state.colony_state import ColonyState


class TestColonyState(unittest.TestCase):
    """Test cases for ColonyState class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ColonyState()
    
    def test_initial_state(self):
        """Test that initial state has default values."""
        self.assertEqual(self.state.turn_number, 0)
        self.assertEqual(self.state.resources["oxygen"], 100.0)
        self.assertEqual(len(self.state.agents), 0)
    
    def test_consume_resources(self):
        """Test resource consumption."""
        self.state.consume_resources({"oxygen": -10.0})
        self.assertEqual(self.state.resources["oxygen"], 90.0)
    
    def test_resource_cannot_go_below_zero(self):
        """Test that resources cannot go below zero."""
        self.state.consume_resources({"oxygen": -150.0})
        self.assertEqual(self.state.resources["oxygen"], 0.0)
    
    def test_add_agent(self):
        """Test adding an agent."""
        agent = {"id": 1, "name": "Test Agent", "oxygen": 50.0}
        self.state.add_agent(agent)
        self.assertEqual(len(self.state.agents), 1)
        self.assertEqual(self.state.agents[0]["name"], "Test Agent")
    
    def test_to_json(self):
        """Test JSON serialization."""
        json_str = self.state.to_json()
        self.assertIsInstance(json_str, str)
        # Should be able to parse it back
        new_state = ColonyState.from_json(json_str)
        self.assertEqual(new_state.turn_number, self.state.turn_number)
    
    def test_next_turn(self):
        """Test turn advancement."""
        initial_turn = self.state.turn_number
        self.state.next_turn()
        self.assertEqual(self.state.turn_number, initial_turn + 1)


if __name__ == "__main__":
    unittest.main()
