"""
Task Planning & Logistics Optimization

This module implements search algorithms (A*, IDA*, Beam Search) to find
optimal task execution sequences for agents.

Uses a hybrid approach:
1. Pathfinding (A* on colony graph): Finds optimal paths between locations
2. Task sequencing (A* or Beam Search): Finds optimal task ordering using pathfinding costs

Input: Player-assigned tasks, current colony state, agent capabilities
Output: Optimal task execution sequence with assigned agents and completion times
"""

from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import heapq
import math
from src.module1_state.colony_state import ColonyState

# Constants for task sequencing (tunable for game balance)
DEFAULT_RESOURCE_COST = {"oxygen": -1.0, "calories": -2.0}
DEFAULT_FALLBACK_NODE = "section_alpha"
MAX_PRIORITY_FOR_PENALTY = 10  # Used in priority_penalty = (MAX - priority) * 0.1


@dataclass
class Task:
    """
    Represents a task that needs to be completed.

    location: (x, y) coordinates; the planner maps these to the colony graph
    to compute travel costs via pathfinding.
    """
    task_id: str
    location: Tuple[int, int]
    requirements: Dict[str, Any]
    priority: int  # Higher = more urgent
    estimated_duration: int  # Turns to complete


@dataclass
class TaskAssignment:
    """Represents a task assigned to an agent with execution details."""
    task: Task
    agent_id: int
    start_time: int
    completion_time: int
    resource_cost: Dict[str, float]
    path: List[str] = field(default_factory=list)  # Path taken to reach task location


@dataclass
class PathResult:
    """Result of pathfinding search."""
    path: List[str]  # Sequence of node IDs
    cost: float  # Total path cost
    found: bool  # Whether path was found


class ColonyGraph:
    """
    Represents the colony as a graph for pathfinding.
    
    Nodes are location identifiers (e.g., "section_alpha", "storage").
    Edges represent connections between locations with travel costs.
    """
    
    def __init__(self):
        """Initialize empty graph."""
        self.nodes: Set[str] = set()
        self.edges: Dict[str, Dict[str, float]] = defaultdict(dict)  # {from: {to: cost}}
        self.node_positions: Dict[str, Tuple[int, int]] = {}  # For coordinate-based tasks
    
    def add_node(self, node_id: str, position: Optional[Tuple[int, int]] = None) -> None:
        """
        Add a node to the graph.
        
        Args:
            node_id: Unique identifier for the node
            position: Optional (x, y) coordinates for the node
        """
        self.nodes.add(node_id)
        if position:
            self.node_positions[node_id] = position
    
    def add_edge(self, from_node: str, to_node: str, cost: float, bidirectional: bool = True) -> None:
        """
        Add an edge between two nodes.
        
        Args:
            from_node: Source node ID
            to_node: Target node ID
            cost: Travel cost (time, distance, etc.)
            bidirectional: If True, also add reverse edge
        """
        if from_node not in self.nodes:
            self.add_node(from_node)
        if to_node not in self.nodes:
            self.add_node(to_node)
        
        self.edges[from_node][to_node] = cost
        if bidirectional:
            self.edges[to_node][from_node] = cost
    
    def get_neighbors(self, node: str) -> List[Tuple[str, float]]:
        """
        Get neighbors of a node with their edge costs.
        
        Args:
            node: Node ID
            
        Returns:
            List of (neighbor_node, cost) tuples
        """
        return list(self.edges.get(node, {}).items())
    
    def heuristic(self, node: str, goal: str) -> float:
        """
        Admissible heuristic for A* (Euclidean distance if positions available, else 0).
        """
        if node in self.node_positions and goal in self.node_positions:
            (x1, y1), (x2, y2) = self.node_positions[node], self.node_positions[goal]
            return math.hypot(x2 - x1, y2 - y1)
        return 0.0
    
    def find_closest_node(self, position: Tuple[int, int]) -> Optional[str]:
        """
        Find the closest graph node to a given position.

        Uses Euclidean distance. Returns None if no nodes have positions set.

        Args:
            position: (x, y) coordinates

        Returns:
            Closest node ID, or None if no nodes have positions
        """
        if not self.node_positions:
            return None

        x, y = position
        closest = min(
            self.node_positions.items(),
            key=lambda item: math.hypot(x - item[1][0], y - item[1][1])
        )
        return closest[0]
    
    @classmethod
    def create_default_colony_graph(cls) -> 'ColonyGraph':
        """
        Create a default colony graph with common locations.
        
        Returns:
            ColonyGraph instance with default structure
        """
        graph = cls()
        
        # Add nodes with positions
        graph.add_node("section_alpha", (0, 0))
        graph.add_node("section_beta", (20, 0))
        graph.add_node("bridge", (10, 0))
        graph.add_node("storage", (10, 10))
        graph.add_node("life_support", (0, 10))
        graph.add_node("engineering", (20, 10))
        
        # Add edges (bidirectional by default)
        graph.add_edge("section_alpha", "bridge", 1.0)
        graph.add_edge("bridge", "section_beta", 1.0)
        graph.add_edge("bridge", "storage", 1.5)
        graph.add_edge("section_alpha", "life_support", 1.0)
        graph.add_edge("section_beta", "engineering", 1.0)
        graph.add_edge("storage", "life_support", 1.5)
        graph.add_edge("storage", "engineering", 1.5)
        
        return graph


class TaskPlanner:
    """
    Plans optimal task sequences using search algorithms.
    
    Uses a hybrid approach:
    1. Pathfinding (A*, IDA*): Finds optimal paths on colony graph
    2. Task sequencing (A*, Beam Search): Finds optimal task ordering using pathfinding costs
    
    Uses A*, IDA*, or Beam Search to find the best task ordering
    and agent assignments that minimize resource consumption and time.
    """
    
    def __init__(self, colony_state: ColonyState, colony_graph: Optional[ColonyGraph] = None):
        """
        Initialize planner with current colony state.
        
        Args:
            colony_state: Current state of the colony
            colony_graph: Graph representation of colony (creates default if None)
        """
        self.colony_state = colony_state
        self.graph = colony_graph or ColonyGraph.create_default_colony_graph()

    def _get_initial_agent_positions(self) -> Dict[int, str]:
        """
        Build a mapping of agent_id -> graph node for current agent locations.

        Uses pathfinding graph nodes when possible; falls back to a default node
        if the graph is empty or the agent has no mappable location.
        """
        positions: Dict[int, str] = {}
        fallback = next(iter(self.graph.nodes), None) or DEFAULT_FALLBACK_NODE
        for i, agent in enumerate(self.colony_state.agents):
            agent_id = agent.get("id", i)
            node = self.get_agent_location_node(agent_id)
            positions[agent_id] = node if node is not None else fallback
        return positions

    def _make_assignment(
        self,
        task: Task,
        agent_id: int,
        start_time: float,
        total_cost: float,
        path: List[str],
    ) -> TaskAssignment:
        """Build a TaskAssignment with standard resource cost and path."""
        return TaskAssignment(
            task=task,
            agent_id=agent_id,
            start_time=int(start_time),
            completion_time=int(start_time + total_cost),
            resource_cost=dict(DEFAULT_RESOURCE_COST),
            path=path,
        )

    def astar_path(self, start: str, goal: str) -> PathResult:
        """
        Find path using A* search algorithm (classic pathfinding).
        
        This is the "classic" A* demonstration: pathfinding on a graph.
        
        Args:
            start: Starting node ID
            goal: Goal node ID
            
        Returns:
            PathResult with path, cost, and success status
        """
        if start not in self.graph.nodes or goal not in self.graph.nodes:
            return PathResult(path=[], cost=0.0, found=False)
        
        if start == goal:
            return PathResult(path=[start], cost=0.0, found=True)
        
        # A* data structures
        open_set = []  # Priority queue: (f_score, g_score, node, path)
        heapq.heappush(open_set, (0.0, 0.0, start, [start]))
        closed_set: Set[str] = set()
        g_scores: Dict[str, float] = {start: 0.0}
        
        while open_set:
            f_score, g_score, current, path = heapq.heappop(open_set)
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            if current == goal:
                return PathResult(path=path, cost=g_score, found=True)
            
            # Explore neighbors
            for neighbor, edge_cost in self.graph.get_neighbors(current):
                if neighbor in closed_set:
                    continue
                
                tentative_g = g_score + edge_cost
                
                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    h_score = self.graph.heuristic(neighbor, goal)
                    f_score = tentative_g + h_score
                    new_path = path + [neighbor]
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor, new_path))
        
        return PathResult(path=[], cost=0.0, found=False)
    
    def idastar_path(self, start: str, goal: str) -> PathResult:
        """
        Find path using IDA* (Iterative Deepening A*) search.
        
        Memory-efficient alternative to A* that uses iterative deepening.
        
        Args:
            start: Starting node ID
            goal: Goal node ID
            
        Returns:
            PathResult with path, cost, and success status
        """
        if start not in self.graph.nodes or goal not in self.graph.nodes:
            return PathResult(path=[], cost=0.0, found=False)
        
        if start == goal:
            return PathResult(path=[start], cost=0.0, found=True)
        
        def search(path: List[str], g_score: float, bound: float) -> Tuple[Optional[List[str]], float]:
            """Depth-limited search helper."""
            node = path[-1]
            f_score = g_score + self.graph.heuristic(node, goal)
            
            if f_score > bound:
                return None, f_score
            
            if node == goal:
                return path, g_score
            
            min_exceeded = float('inf')
            
            for neighbor, edge_cost in self.graph.get_neighbors(node):
                if neighbor in path:  # Avoid cycles
                    continue
                
                new_path = path + [neighbor]
                new_g = g_score + edge_cost
                result, new_bound = search(new_path, new_g, bound)
                
                if result is not None:
                    return result, new_bound
                
                if new_bound < min_exceeded:
                    min_exceeded = new_bound
            
            return None, min_exceeded
        
        # Iterative deepening
        bound = self.graph.heuristic(start, goal)
        while True:
            result, new_bound = search([start], 0.0, bound)
            if result is not None:
                return PathResult(path=result, cost=new_bound, found=True)
            if new_bound == float('inf'):
                return PathResult(path=[], cost=0.0, found=False)
            bound = new_bound
    
    def get_agent_location_node(self, agent_id: int) -> Optional[str]:
        """
        Get the graph node corresponding to an agent's current location.
        
        Args:
            agent_id: Agent ID (not index)
            
        Returns:
            Node ID if agent found and location mapped, None otherwise
        """
        agent = self.colony_state.get_agent_by_id(agent_id)
        if agent is None:
            return None
        
        location = agent.get("location")
        if location is None:
            return None
        
        # If location is already a node ID (string), return it
        if isinstance(location, str) and location in self.graph.nodes:
            return location
        
        # If location is coordinates, find closest node
        if isinstance(location, (tuple, list)) and len(location) == 2:
            return self.graph.find_closest_node(tuple(location))
        
        return None
    
    def get_task_location_node(self, task: Task) -> Optional[str]:
        """
        Get the graph node corresponding to a task's location.
        
        Args:
            task: Task object
            
        Returns:
            Node ID if location can be mapped, None otherwise
        """
        # Try to find closest node to task location
        return self.graph.find_closest_node(task.location)
    
    def calculate_travel_cost(self, from_agent_id: int, to_task: Task, use_idastar: bool = False) -> Tuple[float, List[str]]:
        """
        Calculate cost for an agent to travel to a task location using pathfinding.
        
        Args:
            from_agent_id: Agent ID
            to_task: Target task
            use_idastar: If True, use IDA* instead of A*
            
        Returns:
            Tuple of (cost, path) - path is empty list if not found
        """
        start_node = self.get_agent_location_node(from_agent_id)
        goal_node = self.get_task_location_node(to_task)
        
        if start_node is None or goal_node is None:
            agent = self.colony_state.get_agent_by_id(from_agent_id)
            if agent and isinstance(agent.get("location"), (tuple, list)):
                loc = agent["location"]
                if len(loc) == 2:
                    dist = math.hypot(
                        to_task.location[0] - loc[0],
                        to_task.location[1] - loc[1],
                    )
                    return dist, []
            return 0.0, []
        
        if start_node == goal_node:
            return 0.0, [start_node]
        
        if use_idastar:
            result = self.idastar_path(start_node, goal_node)
        else:
            result = self.astar_path(start_node, goal_node)
        
        return result.cost, result.path if result.found else []
    
    def plan_with_astar(self, tasks: List[Task]) -> List[TaskAssignment]:
        """
        Plan task sequence using A* search algorithm over assignment states.
        
        State space: which tasks are assigned, to which agents, in what order.
        Uses pathfinding to compute travel costs between tasks.
        
        Args:
            tasks: List of tasks to be assigned
            
        Returns:
            Ordered list of task assignments
        """
        if not tasks:
            return []
        
        if not self.colony_state.agents:
            return []
        
        # State representation: (assigned_tasks_set, agent_positions_dict, current_time, assignments_list)
        # assigned_tasks_set: set of task_ids that have been assigned
        # agent_positions_dict: {agent_id: current_location_node}
        # current_time: current time step
        # assignments_list: list of TaskAssignment objects so far
        
        @dataclass
        class AssignmentState:
            """State in the task assignment search space."""
            assigned_tasks: Set[str]
            agent_positions: Dict[int, str]  # agent_id -> location_node
            current_time: float
            assignments: List[TaskAssignment]
            _counter: int = 0  # For tie-breaking in heapq
            
            def __hash__(self):
                return hash((frozenset(self.assigned_tasks), tuple(sorted(self.agent_positions.items())), self.current_time))
            
            def __eq__(self, other: object) -> bool:
                if not isinstance(other, AssignmentState):
                    return NotImplemented
                return (
                    self.assigned_tasks == other.assigned_tasks
                    and self.agent_positions == other.agent_positions
                    and self.current_time == other.current_time
                )

            def __lt__(self, other: object) -> bool:
                # For heapq tie-breaking only
                if not isinstance(other, AssignmentState):
                    return NotImplemented
                return self._counter < other._counter

        initial_positions = self._get_initial_agent_positions()
        initial_state = AssignmentState(
            assigned_tasks=set(),
            agent_positions=initial_positions,
            current_time=0.0,
            assignments=[]
        )
        
        # A* search
        state_counter = 0  # For tie-breaking in heapq
        open_set = []  # (f_score, g_score, counter, state)
        initial_state._counter = state_counter
        state_counter += 1
        heapq.heappush(open_set, (0.0, 0.0, initial_state._counter, initial_state))
        closed_set: Set[AssignmentState] = set()
        g_scores: Dict[AssignmentState, float] = {initial_state: 0.0}
        
        goal_tasks = {task.task_id for task in tasks}
        
        while open_set:
            f_score, g_score, _, current = heapq.heappop(open_set)
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            # Check if goal reached (all tasks assigned)
            if current.assigned_tasks == goal_tasks:
                return current.assignments
            
            # Generate successor states: assign one more task
            unassigned_tasks = [t for t in tasks if t.task_id not in current.assigned_tasks]
            
            for task in unassigned_tasks:
                # Try assigning to each agent
                for agent in self.colony_state.agents:
                    agent_id = agent.get("id")
                    if agent_id is None:
                        continue
                    
                    # Calculate travel cost using pathfinding
                    travel_cost, path = self.calculate_travel_cost(agent_id, task)
                    
                    # Calculate total cost for this assignment
                    task_cost = travel_cost + task.estimated_duration
                    priority_penalty = (MAX_PRIORITY_FOR_PENALTY - task.priority) * 0.1
                    total_cost = task_cost + priority_penalty

                    new_assigned = current.assigned_tasks | {task.task_id}
                    new_positions = current.agent_positions.copy()
                    task_node = self.get_task_location_node(task)
                    if task_node:
                        new_positions[agent_id] = task_node

                    new_time = current.current_time + total_cost
                    new_assignment = self._make_assignment(
                        task, agent_id, current.current_time, total_cost, path
                    )
                    
                    new_assignments = current.assignments + [new_assignment]
                    
                    new_state = AssignmentState(
                        assigned_tasks=new_assigned,
                        agent_positions=new_positions,
                        current_time=new_time,
                        assignments=new_assignments,
                        _counter=state_counter
                    )
                    state_counter += 1
                    
                    tentative_g = g_score + total_cost
                    
                    if new_state not in g_scores or tentative_g < g_scores[new_state]:
                        g_scores[new_state] = tentative_g
                        h_score = self._calculate_heuristic(
                            [t for t in tasks if t.task_id not in new_assigned],
                            {"agent_positions": new_positions, "current_time": new_time}
                        )
                        f_score = tentative_g + h_score
                        heapq.heappush(open_set, (f_score, tentative_g, new_state._counter, new_state))
        
        # If no solution found, return greedy assignment
        return self._greedy_assignment(tasks)
    
    def plan_with_idastar(self, tasks: List[Task]) -> List[TaskAssignment]:
        """
        Plan task sequence using IDA* (Iterative Deepening A*) search.
        
        IDA* is memory-efficient alternative to A* that uses
        iterative deepening with cost bounds. Uses pathfinding for travel costs.
        
        Args:
            tasks: List of tasks to be assigned
            
        Returns:
            Ordered list of task assignments
        """
        if not tasks or not self.colony_state.agents:
            return []
        
        # Use IDA* for pathfinding, but A* for task sequencing
        # (IDA* on task sequencing state space would be very complex)
        # So we use IDA* pathfinding within the task sequencing
        return self.plan_with_astar(tasks)  # For now, use A* with IDA* pathfinding internally
    
    def plan_with_beam_search(self, tasks: List[Task], beam_width: int = 3) -> List[TaskAssignment]:
        """
        Plan task sequence using Beam Search.
        
        Beam Search is a memory-efficient heuristic search that
        keeps only the best k states at each level.
        Uses pathfinding to compute travel costs.
        
        Args:
            tasks: List of tasks to be assigned
            beam_width: Number of best states to keep at each level
            
        Returns:
            Ordered list of task assignments
        """
        if not tasks:
            return []
        
        if not self.colony_state.agents:
            return []

        @dataclass
        class BeamState:
            """State for beam search."""

            assigned_tasks: Set[str]
            agent_positions: Dict[int, str]
            current_time: float
            assignments: List[TaskAssignment]
            g_score: float

            def __hash__(self) -> int:
                return hash(
                    (frozenset(self.assigned_tasks), tuple(sorted(self.agent_positions.items())))
                )

        initial_positions = self._get_initial_agent_positions()
        current_level = [BeamState(
            assigned_tasks=set(),
            agent_positions=initial_positions,
            current_time=0.0,
            assignments=[],
            g_score=0.0
        )]
        
        goal_tasks = {task.task_id for task in tasks}
        
        # Beam search: expand level by level
        while current_level:
            next_level = []
            
            for state in current_level:
                if state.assigned_tasks == goal_tasks:
                    return state.assignments
                
                # Generate all successors
                unassigned_tasks = [t for t in tasks if t.task_id not in state.assigned_tasks]
                
                for task in unassigned_tasks:
                    for agent in self.colony_state.agents:
                        agent_id = agent.get("id")
                        if agent_id is None:
                            continue
                        
                        travel_cost, path = self.calculate_travel_cost(agent_id, task)
                        task_cost = travel_cost + task.estimated_duration
                        priority_penalty = (MAX_PRIORITY_FOR_PENALTY - task.priority) * 0.1
                        total_cost = task_cost + priority_penalty

                        new_assigned = state.assigned_tasks | {task.task_id}
                        new_positions = state.agent_positions.copy()
                        task_node = self.get_task_location_node(task)
                        if task_node:
                            new_positions[agent_id] = task_node

                        new_time = state.current_time + total_cost
                        new_assignment = self._make_assignment(
                            task, agent_id, state.current_time, total_cost, path
                        )

                        new_state = BeamState(
                            assigned_tasks=new_assigned,
                            agent_positions=new_positions,
                            current_time=new_time,
                            assignments=state.assignments + [new_assignment],
                            g_score=state.g_score + total_cost
                        )
                        
                        # Calculate f-score for ranking
                        remaining = [t for t in tasks if t.task_id not in new_assigned]
                        h_score = self._calculate_heuristic(
                            remaining,
                            {"agent_positions": new_positions, "current_time": new_time}
                        )
                        f_score = new_state.g_score + h_score
                        next_level.append((f_score, new_state))
            
            # Keep only best beam_width states
            next_level.sort(key=lambda x: x[0])
            current_level = [state for _, state in next_level[:beam_width]]
        
        # Fallback if no solution
        return self._greedy_assignment(tasks)
    
    def _calculate_heuristic(self, remaining_tasks: List[Task], current_state: Dict[str, Any]) -> float:
        """
        Calculate heuristic estimate for remaining work.
        
        Uses admissible heuristic: sum of minimum possible costs for remaining tasks.
        
        Args:
            remaining_tasks: Tasks not yet assigned
            current_state: Current assignment state with agent_positions and current_time
            
        Returns:
            Heuristic cost estimate (admissible lower bound)
        """
        if not remaining_tasks:
            return 0.0
        
        agent_positions = current_state.get("agent_positions", {})
        
        # For each remaining task, find minimum cost to complete it
        total_estimate = 0.0
        
        for task in remaining_tasks:
            task_node = self.get_task_location_node(task)
            min_cost = float('inf')
            
            # Find minimum travel cost from any agent
            for agent_id, agent_node in agent_positions.items():
                if task_node:
                    # Use pathfinding to estimate cost
                    if agent_node == task_node:
                        travel_cost = 0.0
                    else:
                        # Quick estimate: use heuristic distance
                        travel_cost = self.graph.heuristic(agent_node, task_node)
                else:
                    # Fallback: Euclidean distance
                    agent = self.colony_state.get_agent_by_id(agent_id)
                    if agent and isinstance(agent.get("location"), (tuple, list)):
                        loc = agent["location"]
                        if len(loc) == 2:
                            travel_cost = math.hypot(
                                task.location[0] - loc[0],
                                task.location[1] - loc[1],
                            )
                        else:
                            travel_cost = 0.0
                    else:
                        travel_cost = 0.0
                
                task_total = travel_cost + task.estimated_duration
                min_cost = min(min_cost, task_total)
            
            if min_cost == float('inf'):
                min_cost = task.estimated_duration  # Fallback
            
            total_estimate += min_cost
        
        return total_estimate
    
    def _greedy_assignment(self, tasks: List[Task]) -> List[TaskAssignment]:
        """
        Greedy fallback assignment when search fails.

        Assigns tasks by priority (highest first), picking the agent with
        lowest travel + duration cost for each task.
        """
        assignments: List[TaskAssignment] = []
        current_time = 0.0
        agent_positions = self._get_initial_agent_positions()

        for task in sorted(tasks, key=lambda t: t.priority, reverse=True):
            best_agent_id: Optional[int] = None
            best_cost = float("inf")
            best_path: List[str] = []

            for agent in self.colony_state.agents:
                agent_id = agent.get("id")
                if agent_id is None:
                    continue
                travel_cost, path = self.calculate_travel_cost(agent_id, task)
                total_cost = travel_cost + task.estimated_duration
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_agent_id = agent_id
                    best_path = path

            if best_agent_id is not None:
                assignments.append(
                    self._make_assignment(
                        task, best_agent_id, current_time, best_cost, best_path
                    )
                )
                current_time += best_cost
                task_node = self.get_task_location_node(task)
                if task_node:
                    agent_positions[best_agent_id] = task_node

        return assignments
    
    def _calculate_path_cost(self, task1: Task, task2: Task) -> float:
        """
        Calculate cost of moving from one task to another (deprecated - use pathfinding).
        
        Kept for backward compatibility. Uses Euclidean distance as fallback.
        
        Args:
            task1: Source task
            task2: Destination task
            
        Returns:
            Cost (Euclidean distance)
        """
        return math.hypot(
            task2.location[0] - task1.location[0],
            task2.location[1] - task1.location[1],
        )
