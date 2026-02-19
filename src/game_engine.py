"""
Game Engine

Main game loop that coordinates all modules through the four phases:
1. Logic: Rule enforcement (Module 3)
2. Planning: Task optimization (Module 2)
3. Adversarial: AI event selection (Module 4)
4. Resolution: Resource consumption and event application (Modules 1, 5)
"""

from typing import Dict, Any, List, Tuple, Optional
import heapq
import math
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import TaskPlanner, Task
from src.module3_logic.rule_engine import RuleEngine
from src.module4_game_theory.ai_director import AIDirector, Event
from src.module5_events.event_resolver import EventResolver
from src.module6_rl.survival_assessor import SurvivalAssessor


class GameEngine:
    """
    Main game engine that orchestrates all modules.
    
    Runs the four-phase turn cycle:
    - Logic: Check rules and apply violations
    - Planning: Optimize task assignments
    - Adversarial: AI selects disruptive event
    - Resolution: Apply resource consumption and events
    """
    
    def __init__(self, initial_state: ColonyState = None):
        """
        Initialize game engine with modules.
        
        Args:
            initial_state: Starting colony state (or None for default)
        """
        self.state = initial_state or ColonyState()
        self.rule_engine = RuleEngine()
        self.task_planner = TaskPlanner(self.state)
        self.event_resolver = EventResolver()
        self.survival_assessor = SurvivalAssessor(use_rl=False)
        
        # Initialize AI Director with available events
        self.available_events = self._create_default_events()
        self.ai_director = AIDirector(self.available_events)
    
    def _create_default_events(self) -> list[Event]:
        """Create default catalog of available events."""
        return [
            Event(
                event_type="hull_breach",
                location="section_alpha",
                severity=0.5,
                resource_impact={"oxygen": -20.0},
                description="Hull breach in section alpha"
            ),
            Event(
                event_type="resource_shortage",
                location="storage",
                severity=0.3,
                resource_impact={"calories": -15.0},
                description="Resource shortage in storage"
            ),
            Event(
                event_type="equipment_failure",
                location="life_support",
                severity=0.4,
                resource_impact={"integrity": -10.0},
                description="Life support equipment failure"
            ),
        ]
    
    def execute_turn(self, player_tasks: list[Task] = None, algorithm: str = "astar") -> Dict[str, Any]:
        """
        Execute one complete turn through all four phases.
        
        Args:
            player_tasks: Tasks assigned by player (optional)
            algorithm: Algorithm to use for task planning ("astar", "beam_search", "idastar")
            
        Returns:
            Turn report with results from each phase
        """
        turn_report = {
            "turn_number": self.state.turn_number,
            "phases": {}
        }
        
        # Phase 1: Logic - Rule Enforcement
        logic_result = self.rule_engine.evaluate_state(self.state)
        turn_report["phases"]["logic"] = logic_result
        
        # Phase 2: Planning - Task Optimization
        if player_tasks:
            if algorithm == "beam_search":
                task_assignments = self.task_planner.plan_with_beam_search(player_tasks, beam_width=3)
            elif algorithm == "idastar":
                # IDA* is for pathfinding, use A* for task sequencing
                task_assignments = self.task_planner.plan_with_astar(player_tasks)
            else:  # astar (default)
                task_assignments = self.task_planner.plan_with_astar(player_tasks)
            
            # Build path coordinates for each assignment (for visual walking, not teleporting)
            graph = self.task_planner.graph
            assignments_data = []
            for a in task_assignments:
                path_coords: List[Tuple[int, int]] = []
                for node_id in (a.path or []):
                    pos = graph.node_positions.get(node_id)
                    if pos is not None:
                        path_coords.append(tuple(pos))
                # Ensure destination is included (path may end at a graph node near task)
                dest = a.task.location
                if path_coords and path_coords[-1] != dest:
                    path_coords.append(dest)
                elif not path_coords:
                    path_coords = [dest]
                assignments_data.append({
                    "task_id": a.task.task_id,
                    "agent_id": a.agent_id,
                    "completion_time": a.completion_time,
                    "path_coords": path_coords,
                    "task_location": dest,
                })
            turn_report["phases"]["planning"] = {
                "tasks_assigned": len(task_assignments),
                "assignments": assignments_data
            }
            # Do NOT move agents here — visual game advances them along paths each turn
        else:
            turn_report["phases"]["planning"] = {"tasks_assigned": 0}
        
        # Phase 3: Adversarial - AI Event Selection
        selected_event = self.ai_director.select_event_minimax(self.state)
        turn_report["phases"]["adversarial"] = {
            "event_selected": selected_event.event_type,
            "location": selected_event.location,
            "severity": selected_event.severity
        }
        
        # Phase 4: Resolution - Resource Consumption & Event Application
        # Apply resource consumption from agent activity
        base_consumption = {"oxygen": -5.0, "calories": -3.0}
        self.state.consume_resources(base_consumption)
        
        # Apply selected event
        event_result = self.event_resolver.apply_event(self.state, selected_event)
        turn_report["phases"]["resolution"] = event_result
        
        # Survival Assessment
        survival_assessment = self.survival_assessor.assess_survival(self.state)
        turn_report["survival_assessment"] = survival_assessment
        
        # Advance to next turn
        self.state.next_turn()
        
        return turn_report
    
    def _grid_pathfind(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        A* pathfinding directly on the tile grid.
        Falls back to this when graph-based pathfinding fails.
        """
        if start == goal:
            return [start]
        
        # A* on grid
        open_set = [(0, start)]
        closed_set: set = set()
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}
        
        def heuristic(pos: Tuple[int, int]) -> float:
            return math.hypot(goal[0] - pos[0], goal[1] - pos[1])
        
        neighbors = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
        
        max_iterations = 10000  # Prevent infinite loops
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(open_set)[1]
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            if current == goal:
                # Reconstruct path
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                return list(reversed(path))
            
            for dx, dy in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                
                if neighbor in closed_set:
                    continue
                
                # Check bounds (world is -25 to +25, but allow some margin for pathfinding)
                if not (-30 <= neighbor[0] <= 30 and -30 <= neighbor[1] <= 30):
                    continue
                
                tile = self.state.get_tile_at(neighbor[0], neighbor[1])
                if not tile.get("passable", True):
                    continue
                
                # Cost: 1.0 for cardinal, 1.414 for diagonal
                move_cost = 1.0 if abs(dx) + abs(dy) == 1 else 1.414
                tentative_g = g_score[current] + move_cost
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor)
                    heapq.heappush(open_set, (f_score, neighbor))
        
        # No path found - try to find closest passable tile to goal
        # Check goal itself first
        goal_tile = self.state.get_tile_at(goal[0], goal[1])
        if goal_tile.get("passable", True):
            return [start, goal]
        
        # Search for nearest passable tile to goal
        search_radius = 10
        best_alt = None
        best_dist = float('inf')
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                alt = (goal[0] + dx, goal[1] + dy)
                if not (-30 <= alt[0] <= 30 and -30 <= alt[1] <= 30):
                    continue
                alt_tile = self.state.get_tile_at(alt[0], alt[1])
                if alt_tile.get("passable", True):
                    dist = math.hypot(dx, dy)
                    if dist < best_dist:
                        best_dist = dist
                        best_alt = alt
        
        if best_alt:
            # Try pathfinding to alternative location
            alt_path = self._grid_pathfind(start, best_alt)
            if len(alt_path) > 1:
                return alt_path
        
        # No path found - return empty list to indicate failure
        return []
    
    def get_path_for_agent_to_location(self, agent_id: int, world_x: int, world_y: int) -> List[Tuple[int, int]]:
        """
        Get path from agent to world coordinates immediately (for instant movement commands).
        Returns list of (x, y) coordinates; agent will walk along this path.
        Uses graph-based pathfinding first, falls back to grid-based if needed.
        """
        agent = self.state.get_agent_by_id(agent_id)
        if not agent:
            return [(world_x, world_y)]
        
        agent_loc = agent.get("location")
        if not agent_loc or not isinstance(agent_loc, (tuple, list)) or len(agent_loc) != 2:
            return [(world_x, world_y)]
        
        start = (int(agent_loc[0]), int(agent_loc[1]))
        goal = (world_x, world_y)
        
        # Try graph-based pathfinding first
        task = Task(f"_immediate_{world_x}_{world_y}", goal, {}, 1, 1)
        _, path = self.task_planner.calculate_travel_cost(agent_id, task, use_idastar=False)
        
        graph = self.task_planner.graph
        path_coords: List[Tuple[int, int]] = []
        
        if path:
            # Convert graph nodes to coordinates
            for node_id in path:
                pos = graph.node_positions.get(node_id)
                if pos is not None:
                    path_coords.append(tuple(pos))
        
        # If graph pathfinding failed or returned empty, use grid-based
        if not path_coords:
            path_coords = self._grid_pathfind(start, goal)
        else:
            # Ensure we start from agent's actual position
            if path_coords and path_coords[0] != start:
                path_coords.insert(0, start)
            # Ensure we end at goal
            if path_coords and path_coords[-1] != goal:
                path_coords.append(goal)
        
        # If grid pathfinding also failed (returned empty), return empty list to indicate failure
        if not path_coords:
            return []
        
        # Verify path actually reaches goal (within 1 tile)
        path_end = path_coords[-1]
        if abs(path_end[0] - goal[0]) > 1 or abs(path_end[1] - goal[1]) > 1:
            # Path doesn't reach goal - pathfinding failed
            return []
        
        return path_coords
    
    def get_state(self) -> ColonyState:
        """Get current colony state."""
        return self.state
    
    def is_game_over(self) -> bool:
        """
        Check if game is over (all agents dead or colony destroyed).
        
        Returns:
            True if game should end
        """
        if len(self.state.agents) == 0:
            return True
        
        if self.state.resources.get("integrity", 100.0) <= 0:
            return True
        
        return False
