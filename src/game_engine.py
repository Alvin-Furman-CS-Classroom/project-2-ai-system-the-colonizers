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
    
    def _is_tile_passable(self, x: int, y: int, exclude_agent_id: Optional[int] = None) -> bool:
        """
        Check if a tile is passable (terrain check only - agents can pass through each other).
        
        Args:
            x, y: Tile coordinates
            exclude_agent_id: Not used (kept for compatibility)
        
        Returns:
            True if tile is passable
        """
        # Check world bounds (world is -25 to +25)
        if not (-25 <= x < 25 and -25 <= y < 25):
            return False
        
        # Check terrain passability only (agents can overlap)
        tile = self.state.get_tile_at(x, y)
        if not tile.get("passable", True):
            return False
        
        return True
    
    def _grid_pathfind(self, start: Tuple[int, int], goal: Tuple[int, int], exclude_agent_id: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        A* pathfinding directly on the tile grid.
        Finds optimal path from start to goal, avoiding obstacles and occupied tiles.
        
        Args:
            start: Starting (x, y) coordinates
            goal: Goal (x, y) coordinates
            exclude_agent_id: Agent ID to exclude from occupancy checks (for pathfinding own agent)
        
        Returns:
            List of (x, y) coordinates representing the path, or empty list if no path found
        """
        start = (int(start[0]), int(start[1]))
        goal = (int(goal[0]), int(goal[1]))
        
        # If start and goal are the same, return single point path
        if start == goal:
            return [start]
        
        # Check if goal is passable
        if not self._is_tile_passable(goal[0], goal[1], exclude_agent_id):
            # Goal is blocked - try to find nearest passable tile
            best_alt = None
            best_dist = float('inf')
            search_radius = 5  # Search nearby tiles
            for dx in range(-search_radius, search_radius + 1):
                for dy in range(-search_radius, search_radius + 1):
                    if dx == 0 and dy == 0:
                        continue
                    alt_x, alt_y = goal[0] + dx, goal[1] + dy
                    if self._is_tile_passable(alt_x, alt_y, exclude_agent_id):
                        dist = math.hypot(dx, dy)
                        if dist < best_dist:
                            best_dist = dist
                            best_alt = (alt_x, alt_y)
            if best_alt:
                goal = best_alt
            else:
                # No nearby passable tile found
                return []
        
        # A* algorithm
        open_set = [(0, start)]
        closed_set: set = set()
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}
        
        def heuristic(pos: Tuple[int, int]) -> float:
            """Euclidean distance heuristic."""
            return math.hypot(goal[0] - pos[0], goal[1] - pos[1])
        
        # 8-directional movement (cardinal + diagonal)
        neighbors = [
            (0, 1), (1, 0), (0, -1), (-1, 0),  # Cardinal
            (1, 1), (-1, 1), (1, -1), (-1, -1)  # Diagonal
        ]
        
        max_iterations = 5000  # Prevent infinite loops
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Get node with lowest f_score
            current_f, current = heapq.heappop(open_set)
            
            # Skip if already processed
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            # Check if we reached the goal
            if current == goal:
                # Reconstruct path
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                return list(reversed(path))
            
            # Explore neighbors
            for dx, dy in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                
                # Skip if already processed
                if neighbor in closed_set:
                    continue
                
                # Check if neighbor is passable
                if not self._is_tile_passable(neighbor[0], neighbor[1], exclude_agent_id):
                    continue
                
                # Get tile to check movement speed (water is slow)
                tile = self.state.get_tile_at(neighbor[0], neighbor[1])
                tile_move_speed = tile.get("move_speed", 1.0)  # Default 1.0 for normal terrain
                
                # Base movement cost (1.0 for cardinal, ~1.414 for diagonal)
                base_cost = 1.0 if abs(dx) + abs(dy) == 1 else 1.414
                # Water is 0.2x speed, so cost is 5x (1/0.2 = 5) to discourage water paths
                move_cost = base_cost / tile_move_speed
                tentative_g = g_score[current] + move_cost
                
                # Update if we found a better path to this neighbor
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor)
                    heapq.heappush(open_set, (f_score, neighbor))
        
        # No path found after max iterations
        return []
    
    def get_path_for_agent_to_location(self, agent_id: int, world_x: int, world_y: int) -> List[Tuple[int, int]]:
        """
        Get path from agent to world coordinates immediately (for instant movement commands).
        Returns list of (x, y) coordinates; agent will walk along this path.
        Uses grid-based A* pathfinding directly on the tile grid.
        
        Args:
            agent_id: ID of the agent to pathfind for
            world_x, world_y: Target coordinates
        
        Returns:
            List of (x, y) coordinates representing the path, or empty list if no path found
        """
        agent = self.state.get_agent_by_id(agent_id)
        if not agent:
            return []
        
        agent_loc = agent.get("location")
        if not agent_loc or not isinstance(agent_loc, (tuple, list)) or len(agent_loc) != 2:
            return []
        
        start = (int(agent_loc[0]), int(agent_loc[1]))
        goal = (int(world_x), int(world_y))
        
        # Use grid-based pathfinding (more reliable for arbitrary coordinates)
        # Exclude this agent from occupancy checks so it can pathfind through its own position
        path_coords = self._grid_pathfind(start, goal, exclude_agent_id=agent_id)
        
        # If pathfinding failed, return empty list
        if not path_coords:
            return []
        
        # Verify path reaches goal (within 1 tile tolerance)
        path_end = path_coords[-1]
        if abs(path_end[0] - goal[0]) > 1 or abs(path_end[1] - goal[1]) > 1:
            return []
        
        return path_coords
    
    def get_state(self) -> ColonyState:
        """Get current colony state."""
        return self.state
    
    def is_game_over(self) -> bool:
        """
        Check if game is over (no agents, all agents dead, or colony destroyed).
        
        Returns:
            True if game should end
        """
        if len(self.state.agents) == 0:
            return True
        
        # All agents dead (no living agents left)
        living = [a for a in self.state.agents if a.get("status") != "dead"]
        if not living:
            return True
        
        if self.state.resources.get("integrity", 100.0) <= 0:
            return True
        
        return False
