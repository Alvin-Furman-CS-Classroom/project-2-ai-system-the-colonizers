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

Agent Schema:
    Each agent dictionary should contain:
    - "id": int - Unique identifier
    - "name": str - Agent name
    - "location": tuple[int, int] - (x, y) coordinates
    - "oxygen": float - Individual oxygen level (0-100)
    - "calories": float - Individual calories (0-100)
    - "integrity": float - Health/integrity (0-100)
    - "status": str - "active", "incapacitated", or "dead"
    - "skills": dict - Agent capabilities (optional)
    - "current_task": str or None - Currently assigned task ID (optional)
    - "speed": float - Movement speed multiplier (optional)
    - "efficiency": float - Task efficiency multiplier (optional)

Infrastructure Schema:
    Each infrastructure location is a dictionary that may contain:
    - "integrity": float - Structural integrity (0-100)
    - "status": str - "operational", "damaged", "failed"
    - "efficiency": float - Efficiency multiplier (0-1)
    - Additional location-specific fields

Task Schema:
    Each task dictionary should contain:
    - "task_id": str - Unique task identifier
    - "agent_id": int - Assigned agent ID
    - "location": str - Location where task is performed
    - "progress": float - Completion progress (0-1)
    - "completion_turn": int - Expected completion turn
    - Additional task-specific fields
"""

from typing import Dict, List, Any, Optional, Tuple, Union
import json
import copy

from .procedural_tiles import get_tile


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
        self.world_seed: int = state_data.get("world_seed", 0)
    
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
            "turn_number": self.turn_number,
            "world_seed": self.world_seed
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
    
    @staticmethod
    def _normalize_location(loc: Any) -> Union[Tuple[int, int], str]:
        """
        Normalize location for comparison. (x, y) -> (int, int); string -> str.
        """
        if isinstance(loc, str):
            return loc
        if isinstance(loc, (tuple, list)) and len(loc) == 2:
            return (int(loc[0]), int(loc[1]))
        return loc  # fallback for invalid; comparison will fail as needed
    
    def get_agent_at_location(self, location: Any) -> Optional[Dict[str, Any]]:
        """
        Return the first agent at the given location, or None.
        Used for collision checks: no two agents may share a location.
        """
        norm = self._normalize_location(location)
        for agent in self.agents:
            if "location" not in agent:
                continue
            if self._normalize_location(agent["location"]) == norm:
                return agent
        return None
    
    def get_tile_at(self, x: int, y: int) -> Dict[str, Any]:
        """
        Return procedurally generated tile data at world coordinates (x, y).
        No map bounds: any (x, y) is valid; same coordinates always yield the same tile.
        """
        return get_tile(int(x), int(y), self.world_seed)
    
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
    
    def update_agent(self, agent_id: int, updates: Dict[str, Any], validate: bool = True) -> Tuple[bool, List[str]]:
        """
        Update a specific agent's status.
        
        Args:
            agent_id: Index of agent in agents list
            updates: Dictionary of fields to update
            validate: If True, validate updates before applying
            
        Returns:
            Tuple of (success, list_of_errors)
        """
        if not (0 <= agent_id < len(self.agents)):
            return False, [f"Invalid agent_id: {agent_id}"]
        
        if validate:
            # Create a copy of the agent with updates to validate
            test_agent = self.agents[agent_id].copy()
            test_agent.update(updates)
            is_valid, errors = self.validate_agent(test_agent)
            if not is_valid:
                return False, errors
            # Collision: no other agent at the new location (if location is being updated)
            if "location" in updates:
                other = self.get_agent_at_location(updates["location"])
                if other is not None and other is not self.agents[agent_id]:
                    return False, [f"Location {updates['location']} already occupied by another agent"]
        
        self.agents[agent_id].update(updates)
        return True, []
    
    def validate_agent(self, agent_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that an agent dictionary has required fields.
        
        Args:
            agent_data: Agent dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        required_fields = ["id", "name", "location"]
        
        # Check required fields
        for field in required_fields:
            if field not in agent_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate field types if present
        if "id" in agent_data and not isinstance(agent_data["id"], int):
            errors.append("Field 'id' must be an integer")
        
        if "name" in agent_data and not isinstance(agent_data["name"], str):
            errors.append("Field 'name' must be a string")
        
        if "location" in agent_data:
            loc = agent_data["location"]
            if not isinstance(loc, (tuple, list)) or len(loc) != 2:
                errors.append("Field 'location' must be a tuple/list of 2 numbers")
            elif not all(isinstance(x, (int, float)) for x in loc):
                errors.append("Field 'location' must contain numbers")
        
        # Validate resource ranges if present
        for resource in ["oxygen", "calories", "integrity"]:
            if resource in agent_data:
                value = agent_data[resource]
                if not isinstance(value, (int, float)):
                    errors.append(f"Field '{resource}' must be a number")
                elif value < 0 or value > 100:
                    errors.append(f"Field '{resource}' must be between 0 and 100")
        
        # Validate status if present
        if "status" in agent_data:
            valid_statuses = ["active", "incapacitated", "dead"]
            if agent_data["status"] not in valid_statuses:
                errors.append(f"Field 'status' must be one of: {valid_statuses}")
        
        return len(errors) == 0, errors
    
    def get_agent_by_id(self, agent_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an agent by its ID.
        
        Args:
            agent_id: The ID of the agent to find
            
        Returns:
            Agent dictionary if found, None otherwise
        """
        for agent in self.agents:
            if agent.get("id") == agent_id:
                return agent
        return None
    
    def add_agent(self, agent_data: Dict[str, Any], validate: bool = True) -> Tuple[bool, List[str]]:
        """
        Add a new agent to the colony.
        
        Args:
            agent_data: Dictionary containing agent information
            validate: If True, validate agent data before adding
            
        Returns:
            Tuple of (success, list_of_errors). If validate=False, returns (True, [])
        """
        if validate:
            is_valid, errors = self.validate_agent(agent_data)
            if not is_valid:
                return False, errors
            
            # Check for duplicate ID
            if self.get_agent_by_id(agent_data.get("id")) is not None:
                return False, [f"Agent with id {agent_data.get('id')} already exists"]
            
            # Collision: no other agent at the same location
            loc = agent_data.get("location")
            if loc is not None and self.get_agent_at_location(loc) is not None:
                return False, [f"Location {loc} already occupied by another agent"]
        
        self.agents.append(agent_data)
        return True, []
    
    def remove_agent(self, agent_id: int) -> None:
        """
        Remove an agent from the colony (e.g., after death).
        
        Args:
            agent_id: Index of agent to remove
        """
        if 0 <= agent_id < len(self.agents):
            self.agents.pop(agent_id)
    
    def add_infrastructure(self, location: str, infra_data: Dict[str, Any]) -> None:
        """
        Add or update infrastructure at a location.
        
        Args:
            location: Location identifier (e.g., "section_alpha")
            infra_data: Dictionary containing infrastructure data
        """
        if location not in self.infrastructure:
            self.infrastructure[location] = {}
        self.infrastructure[location].update(infra_data)
    
    def update_infrastructure(self, location: str, updates: Dict[str, Any]) -> bool:
        """
        Update infrastructure at a location.
        
        Args:
            location: Location identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if location exists and was updated, False otherwise
        """
        if location not in self.infrastructure:
            return False
        self.infrastructure[location].update(updates)
        return True
    
    def get_infrastructure(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Get infrastructure data for a location.
        
        Args:
            location: Location identifier
            
        Returns:
            Infrastructure dictionary if location exists, None otherwise
        """
        return self.infrastructure.get(location)
    
    def remove_infrastructure(self, location: str) -> bool:
        """
        Remove infrastructure at a location.
        
        Args:
            location: Location identifier
            
        Returns:
            True if location existed and was removed, False otherwise
        """
        if location in self.infrastructure:
            del self.infrastructure[location]
            return True
        return False
    
    def add_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Add a new active task.
        
        Args:
            task_data: Dictionary containing task information (must include "task_id")
            
        Returns:
            True if task was added, False if task_id already exists
        """
        task_id = task_data.get("task_id")
        if task_id is None:
            return False
        
        # Check for duplicate task_id
        if self.get_task(task_id) is not None:
            return False
        
        self.active_tasks.append(task_data)
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task by its ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was found and removed, False otherwise
        """
        for i, task in enumerate(self.active_tasks):
            if task.get("task_id") == task_id:
                self.active_tasks.pop(i)
                return True
        return False
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a task by its ID.
        
        Args:
            task_id: Task identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if task was found and updated, False otherwise
        """
        task = self.get_task(task_id)
        if task is None:
            return False
        task.update(updates)
        return True
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by its ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task dictionary if found, None otherwise
        """
        for task in self.active_tasks:
            if task.get("task_id") == task_id:
                return task
        return None
    
    def get_tasks_by_agent(self, agent_id: int) -> List[Dict[str, Any]]:
        """
        Get all tasks assigned to a specific agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of task dictionaries assigned to the agent
        """
        return [task for task in self.active_tasks if task.get("agent_id") == agent_id]
    
    def consume_agent_resources(self, agent_id: int, consumption: Dict[str, float]) -> bool:
        """
        Consume resources for a specific agent.
        
        Args:
            agent_id: Agent ID (not index)
            consumption: Dictionary with resource names and amounts to consume
                        (e.g., {"oxygen": -5.0, "calories": -10.0})
        
        Returns:
            True if agent was found and resources consumed, False otherwise
        """
        agent = self.get_agent_by_id(agent_id)
        if agent is None:
            return False
        
        for resource, amount in consumption.items():
            if resource in agent:
                agent[resource] = max(0.0, agent[resource] + amount)
        
        return True
    
    def validate_state(self) -> Tuple[bool, List[str]]:
        """
        Validate state integrity.
        
        Checks:
        - Resources are in valid range (0-100)
        - Agents have required fields
        - Agent IDs are unique
        - Task IDs are unique
        - Task agent_ids reference valid agents
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate resources
        for resource, value in self.resources.items():
            if not isinstance(value, (int, float)):
                errors.append(f"Resource '{resource}' must be a number")
            elif value < 0 or value > 100:
                errors.append(f"Resource '{resource}' must be between 0 and 100, got {value}")
        
        # Validate agents
        agent_ids = set()
        for i, agent in enumerate(self.agents):
            is_valid, agent_errors = self.validate_agent(agent)
            if not is_valid:
                errors.extend([f"Agent {i}: {e}" for e in agent_errors])
            
            # Check for duplicate IDs
            agent_id = agent.get("id")
            if agent_id is not None:
                if agent_id in agent_ids:
                    errors.append(f"Duplicate agent ID: {agent_id}")
                agent_ids.add(agent_id)
        
        # Collision: no two agents at the same location
        seen_locations: Dict[Any, int] = {}
        for i, agent in enumerate(self.agents):
            loc = agent.get("location")
            if loc is not None:
                norm = self._normalize_location(loc)
                if norm in seen_locations:
                    errors.append(
                        f"Agents {seen_locations[norm]} and {i} share the same location {loc}"
                    )
                else:
                    seen_locations[norm] = i
        
        # Validate tasks
        task_ids = set()
        for i, task in enumerate(self.active_tasks):
            task_id = task.get("task_id")
            if task_id is None:
                errors.append(f"Task {i}: Missing 'task_id' field")
            elif task_id in task_ids:
                errors.append(f"Duplicate task ID: {task_id}")
            else:
                task_ids.add(task_id)
            
            # Check that task agent_id references a valid agent
            task_agent_id = task.get("agent_id")
            if task_agent_id is not None:
                if self.get_agent_by_id(task_agent_id) is None:
                    errors.append(f"Task {task_id}: References non-existent agent {task_agent_id}")
        
        # Validate turn number
        if not isinstance(self.turn_number, int) or self.turn_number < 0:
            errors.append(f"Turn number must be a non-negative integer, got {self.turn_number}")
        
        return len(errors) == 0, errors
    
    def is_valid(self) -> bool:
        """
        Quick check if state is valid.
        
        Returns:
            True if state is valid, False otherwise
        """
        return self.validate_state()[0]
    
    def copy(self) -> 'ColonyState':
        """
        Create a deep copy of the state.
        
        Useful for simulations (e.g., Module 4 game theory).
        
        Returns:
            New ColonyState instance with copied data
        """
        return ColonyState(copy.deepcopy(self.to_dict()))
    
    def next_turn(self) -> None:
        """Increment turn counter."""
        self.turn_number += 1
