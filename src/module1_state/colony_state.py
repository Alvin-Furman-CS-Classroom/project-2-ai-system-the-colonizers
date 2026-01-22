"""
Colony State Management

This module defines the core state representation for the colony system.
The state includes:
- Agents: array with health/resource status
- Resources: oxygen, calories, integrity levels
- Infrastructure: state of colony systems
- Active tasks: currently assigned tasks

Input: Previous turn's colony state (JSON structure)
Output: Updated colony state after resource consumption (JSON structure)
"""

from typing import Dict, List, Any
import json


class ColonyState:
    """
    Represents the complete state of the colony at a given turn.
    
    This is the foundational data structure that all other modules
    read from and modify.
    """
    
    def __init__(self, state_data: Dict[str, Any] = None):
        """
        Initialize colony state from JSON data or create empty state.
        
        Args:
            state_data: Dictionary containing colony state (agents, resources, etc.)
        """
        if state_data is None:
            state_data = self._create_empty_state()
        
        self.agents: List[Dict[str, Any]] = state_data.get("agents", [])
        self.resources: Dict[str, float] = state_data.get("resources", {
            "oxygen": 100.0,
            "calories": 100.0,
            "integrity": 100.0
        })
        self.infrastructure: Dict[str, Any] = state_data.get("infrastructure", {})
        self.active_tasks: List[Dict[str, Any]] = state_data.get("active_tasks", [])
        self.turn_number: int = state_data.get("turn_number", 0)
    
    def _create_empty_state(self) -> Dict[str, Any]:
        """Create an empty/default colony state."""
        return {
            "agents": [],
            "resources": {
                "oxygen": 100.0,
                "calories": 100.0,
                "integrity": 100.0
            },
            "infrastructure": {},
            "active_tasks": [],
            "turn_number": 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary format (for JSON serialization).
        
        Returns:
            Dictionary representation of the colony state
        """
        return {
            "agents": self.agents,
            "resources": self.resources,
            "infrastructure": self.infrastructure,
            "active_tasks": self.active_tasks,
            "turn_number": self.turn_number
        }
    
    def to_json(self) -> str:
        """
        Serialize state to JSON string.
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ColonyState':
        """
        Create ColonyState from JSON string.
        
        Args:
            json_str: JSON string containing colony state
            
        Returns:
            ColonyState instance
        """
        data = json.loads(json_str)
        return cls(data)
    
    def consume_resources(self, consumption: Dict[str, float]) -> None:
        """
        Apply resource consumption for the current turn.
        
        This is called during the Resolution phase to update resources
        based on agent activity and environmental factors.
        
        Args:
            consumption: Dictionary with resource names and amounts to consume
                        (e.g., {"oxygen": -5.0, "calories": -10.0})
        """
        for resource, amount in consumption.items():
            if resource in self.resources:
                self.resources[resource] = max(0.0, self.resources[resource] + amount)
    
    def update_agent(self, agent_id: int, updates: Dict[str, Any]) -> None:
        """
        Update a specific agent's status.
        
        Args:
            agent_id: Index of agent in agents list
            updates: Dictionary of fields to update
        """
        if 0 <= agent_id < len(self.agents):
            self.agents[agent_id].update(updates)
    
    def add_agent(self, agent_data: Dict[str, Any]) -> None:
        """
        Add a new agent to the colony.
        
        Args:
            agent_data: Dictionary containing agent information
        """
        self.agents.append(agent_data)
    
    def remove_agent(self, agent_id: int) -> None:
        """
        Remove an agent from the colony (e.g., after death).
        
        Args:
            agent_id: Index of agent to remove
        """
        if 0 <= agent_id < len(self.agents):
            self.agents.pop(agent_id)
    
    def next_turn(self) -> None:
        """Increment turn counter."""
        self.turn_number += 1
