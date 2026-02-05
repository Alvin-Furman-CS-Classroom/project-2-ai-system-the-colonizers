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
        self.valid_agent = {
            "id": 0,
            "name": "Test Agent",
            "location": (10, 15),
            "oxygen": 75.0,
            "calories": 60.0,
            "integrity": 90.0,
            "status": "active"
        }
    
    def test_initial_state(self):
        """Test that initial state has default values."""
        self.assertEqual(self.state.turn_number, 0)
        self.assertEqual(self.state.resources["oxygen"], 100.0)
        self.assertEqual(len(self.state.agents), 0)
        self.assertEqual(len(self.state.infrastructure), 0)
        self.assertEqual(len(self.state.active_tasks), 0)
    
    def test_consume_resources(self):
        """Test resource consumption."""
        self.state.consume_resources({"oxygen": -10.0})
        self.assertEqual(self.state.resources["oxygen"], 90.0)
    
    def test_resource_cannot_go_below_zero(self):
        """Test that resources cannot go below zero."""
        self.state.consume_resources({"oxygen": -150.0})
        self.assertEqual(self.state.resources["oxygen"], 0.0)
    
    def test_add_agent_valid(self):
        """Test adding a valid agent."""
        success, errors = self.state.add_agent(self.valid_agent)
        self.assertTrue(success)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.state.agents), 1)
        self.assertEqual(self.state.agents[0]["name"], "Test Agent")
    
    def test_add_agent_invalid_missing_fields(self):
        """Test adding an agent with missing required fields."""
        invalid_agent = {"id": 1}  # Missing name and location
        success, errors = self.state.add_agent(invalid_agent)
        self.assertFalse(success)
        self.assertGreater(len(errors), 0)
        self.assertEqual(len(self.state.agents), 0)
    
    def test_add_agent_duplicate_id(self):
        """Test that duplicate agent IDs are rejected."""
        self.state.add_agent(self.valid_agent, validate=False)
        success, errors = self.state.add_agent(self.valid_agent)
        self.assertFalse(success)
        self.assertIn("already exists", errors[0])
    
    def test_add_agent_no_validation(self):
        """Test adding agent without validation."""
        invalid_agent = {"id": 1}  # Missing fields
        success, errors = self.state.add_agent(invalid_agent, validate=False)
        self.assertTrue(success)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.state.agents), 1)
    
    def test_get_agent_by_id(self):
        """Test getting agent by ID."""
        self.state.add_agent(self.valid_agent, validate=False)
        agent = self.state.get_agent_by_id(0)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["name"], "Test Agent")
        
        # Test non-existent ID
        agent = self.state.get_agent_by_id(999)
        self.assertIsNone(agent)
    
    def test_update_agent(self):
        """Test updating an agent."""
        self.state.add_agent(self.valid_agent, validate=False)
        success, errors = self.state.update_agent(0, {"oxygen": 50.0})
        self.assertTrue(success)
        self.assertEqual(self.state.agents[0]["oxygen"], 50.0)
    
    def test_update_agent_invalid_index(self):
        """Test updating agent with invalid index."""
        success, errors = self.state.update_agent(999, {"oxygen": 50.0})
        self.assertFalse(success)
        self.assertIn("Invalid agent_id", errors[0])
    
    def test_remove_agent(self):
        """Test removing an agent."""
        self.state.add_agent(self.valid_agent, validate=False)
        self.state.add_agent({**self.valid_agent, "id": 1, "name": "Agent 2"}, validate=False)
        self.assertEqual(len(self.state.agents), 2)
        
        self.state.remove_agent(0)
        self.assertEqual(len(self.state.agents), 1)
        self.assertEqual(self.state.agents[0]["id"], 1)
    
    def test_remove_agent_invalid_index(self):
        """Test removing agent with invalid index."""
        initial_count = len(self.state.agents)
        self.state.remove_agent(999)
        self.assertEqual(len(self.state.agents), initial_count)
    
    def test_validate_agent(self):
        """Test agent validation."""
        # Valid agent
        is_valid, errors = self.state.validate_agent(self.valid_agent)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid agent - missing fields
        invalid = {"id": 1}
        is_valid, errors = self.state.validate_agent(invalid)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Invalid agent - bad location
        invalid = {**self.valid_agent, "location": "not a tuple"}
        is_valid, errors = self.state.validate_agent(invalid)
        self.assertFalse(is_valid)
    
    def test_infrastructure_management(self):
        """Test infrastructure management methods."""
        # Add infrastructure
        self.state.add_infrastructure("section_alpha", {"integrity": 85.0, "status": "operational"})
        self.assertIn("section_alpha", self.state.infrastructure)
        
        # Get infrastructure
        infra = self.state.get_infrastructure("section_alpha")
        self.assertIsNotNone(infra)
        self.assertEqual(infra["integrity"], 85.0)
        
        # Update infrastructure
        success = self.state.update_infrastructure("section_alpha", {"integrity": 70.0})
        self.assertTrue(success)
        self.assertEqual(self.state.infrastructure["section_alpha"]["integrity"], 70.0)
        
        # Remove infrastructure
        success = self.state.remove_infrastructure("section_alpha")
        self.assertTrue(success)
        self.assertNotIn("section_alpha", self.state.infrastructure)
    
    def test_infrastructure_nonexistent(self):
        """Test infrastructure operations on non-existent location."""
        infra = self.state.get_infrastructure("nonexistent")
        self.assertIsNone(infra)
        
        success = self.state.update_infrastructure("nonexistent", {"status": "operational"})
        self.assertFalse(success)
        
        success = self.state.remove_infrastructure("nonexistent")
        self.assertFalse(success)
    
    def test_task_management(self):
        """Test task management methods."""
        # Add task
        task = {
            "task_id": "task_001",
            "agent_id": 0,
            "location": "section_alpha",
            "progress": 0.5,
            "completion_turn": 3
        }
        success = self.state.add_task(task)
        self.assertTrue(success)
        self.assertEqual(len(self.state.active_tasks), 1)
        
        # Get task
        retrieved_task = self.state.get_task("task_001")
        self.assertIsNotNone(retrieved_task)
        self.assertEqual(retrieved_task["progress"], 0.5)
        
        # Update task
        success = self.state.update_task("task_001", {"progress": 0.75})
        self.assertTrue(success)
        self.assertEqual(self.state.get_task("task_001")["progress"], 0.75)
        
        # Remove task
        success = self.state.remove_task("task_001")
        self.assertTrue(success)
        self.assertEqual(len(self.state.active_tasks), 0)
    
    def test_task_duplicate_id(self):
        """Test that duplicate task IDs are rejected."""
        task = {"task_id": "task_001", "agent_id": 0}
        self.state.add_task(task)
        success = self.state.add_task(task)
        self.assertFalse(success)
    
    def test_get_tasks_by_agent(self):
        """Test getting tasks assigned to an agent."""
        self.state.add_task({"task_id": "task_001", "agent_id": 0})
        self.state.add_task({"task_id": "task_002", "agent_id": 0})
        self.state.add_task({"task_id": "task_003", "agent_id": 1})
        
        agent_0_tasks = self.state.get_tasks_by_agent(0)
        self.assertEqual(len(agent_0_tasks), 2)
        
        agent_1_tasks = self.state.get_tasks_by_agent(1)
        self.assertEqual(len(agent_1_tasks), 1)
    
    def test_consume_agent_resources(self):
        """Test per-agent resource consumption."""
        self.state.add_agent(self.valid_agent, validate=False)
        success = self.state.consume_agent_resources(0, {"oxygen": -10.0, "calories": -5.0})
        self.assertTrue(success)
        self.assertEqual(self.state.agents[0]["oxygen"], 65.0)
        self.assertEqual(self.state.agents[0]["calories"], 55.0)
    
    def test_consume_agent_resources_nonexistent(self):
        """Test consuming resources for non-existent agent."""
        success = self.state.consume_agent_resources(999, {"oxygen": -10.0})
        self.assertFalse(success)
    
    def test_consume_agent_resources_below_zero(self):
        """Test that agent resources cannot go below zero."""
        self.state.add_agent(self.valid_agent, validate=False)
        self.state.consume_agent_resources(0, {"oxygen": -200.0})
        self.assertEqual(self.state.agents[0]["oxygen"], 0.0)
    
    def test_validate_state_valid(self):
        """Test state validation with valid state."""
        self.state.add_agent(self.valid_agent, validate=False)
        is_valid, errors = self.state.validate_state()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_state_invalid_resources(self):
        """Test state validation with invalid resources."""
        self.state.resources["oxygen"] = 150.0  # Invalid: > 100
        is_valid, errors = self.state.validate_state()
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_validate_state_duplicate_agent_ids(self):
        """Test state validation detects duplicate agent IDs."""
        self.state.add_agent(self.valid_agent, validate=False)
        self.state.add_agent({**self.valid_agent, "name": "Duplicate"}, validate=False)
        is_valid, errors = self.state.validate_state()
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate agent ID" in e for e in errors))
    
    def test_validate_state_invalid_task_reference(self):
        """Test state validation detects tasks referencing non-existent agents."""
        self.state.add_task({"task_id": "task_001", "agent_id": 999})  # Agent doesn't exist
        is_valid, errors = self.state.validate_state()
        self.assertFalse(is_valid)
        self.assertTrue(any("non-existent agent" in e for e in errors))
    
    def test_is_valid(self):
        """Test quick validation check."""
        self.assertTrue(self.state.is_valid())
        self.state.resources["oxygen"] = -10.0
        self.assertFalse(self.state.is_valid())
    
    def test_copy(self):
        """Test state copying."""
        self.state.add_agent(self.valid_agent, validate=False)
        self.state.add_infrastructure("section_alpha", {"integrity": 85.0})
        self.state.consume_resources({"oxygen": -10.0})
        
        copied_state = self.state.copy()
        
        # Should have same data
        self.assertEqual(len(copied_state.agents), len(self.state.agents))
        self.assertEqual(copied_state.resources["oxygen"], self.state.resources["oxygen"])
        
        # Should be independent
        copied_state.consume_resources({"oxygen": -5.0})
        self.assertNotEqual(copied_state.resources["oxygen"], self.state.resources["oxygen"])
    
    def test_to_json(self):
        """Test JSON serialization."""
        self.state.add_agent(self.valid_agent, validate=False)
        json_str = self.state.to_json()
        self.assertIsInstance(json_str, str)
        # Should be able to parse it back
        new_state = ColonyState.from_json(json_str)
        self.assertEqual(new_state.turn_number, self.state.turn_number)
        self.assertEqual(len(new_state.agents), len(self.state.agents))
    
    def test_json_round_trip_complex(self):
        """Test complex JSON round-trip with all features."""
        # Set up complex state
        self.state.add_agent(self.valid_agent, validate=False)
        self.state.add_infrastructure("section_alpha", {"integrity": 85.0})
        self.state.add_task({"task_id": "task_001", "agent_id": 0})
        self.state.consume_resources({"oxygen": -10.0})
        self.state.next_turn()
        
        # Round-trip
        json_str = self.state.to_json()
        new_state = ColonyState.from_json(json_str)
        
        # Verify all data preserved
        self.assertEqual(new_state.turn_number, self.state.turn_number)
        self.assertEqual(new_state.resources, self.state.resources)
        self.assertEqual(len(new_state.agents), len(self.state.agents))
        self.assertEqual(len(new_state.infrastructure), len(self.state.infrastructure))
        self.assertEqual(len(new_state.active_tasks), len(self.state.active_tasks))
    
    def test_next_turn(self):
        """Test turn advancement."""
        initial_turn = self.state.turn_number
        self.state.next_turn()
        self.assertEqual(self.state.turn_number, initial_turn + 1)
