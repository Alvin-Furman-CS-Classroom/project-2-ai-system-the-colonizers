from __future__ import annotations

"""
Game Engine

Main game loop that coordinates all modules through the four phases:
1. Logic: Rule enforcement (Module 3)
2. Planning: Task optimization (Module 2)
3. Adversarial: AI event selection (Module 4)
4. Resolution: Resource consumption and event application (Modules 1, 5)
"""

from typing import Any, Dict, List, Optional, Tuple
import heapq
import math
from src.module1_state.colony_state import ColonyState
from src.module1_state.tree_generation import maybe_spawn_progression_tree, required_wood_for_quota
from src.module2_search.task_planner import TaskPlanner, Task
from src.module3_logic.rule_engine import RuleEngine
from src.module4_game_theory.ai_director import AIDirector, Event
from src.module4_game_theory.budget_director import BudgetRLDirector, ACTION_SAVE
from src.module5_events.event_resolver import EventResolver
from src.module6_rl.survival_assessor import SurvivalAssessor

BASE_REPAIR_TURNS = 4
MAX_EFFECTIVE_REPAIR_AGENTS = 3

# When colony wood >= wood_quota, adversarial phase selects this event instead of the Director.
NO_ADVERSARY_EVENT = Event(
    "no_adversarial_event",
    "n/a",
    0.0,
    {},
    "Wood quota met; no new disasters this turn.",
    cost=0.0,
)

def director_income_per_turn(difficulty: str, floor_index: int) -> float:
    """
    Points gained each turn for the Director disaster budget.

    Tuned so small hazards happen regularly, while station breakdowns require saving.
    """
    d = (difficulty or "normal").lower()
    base = {"easy": 1.3, "normal": 1.7, "hard": 2.2}.get(d, 1.7)
    depth = 0.08 * max(0, int(floor_index) - 1)
    return base + depth


def director_budget_cap(difficulty: str) -> float:
    d = (difficulty or "normal").lower()
    return {"easy": 10.0, "normal": 12.0, "hard": 15.0}.get(d, 12.0)


class GameEngine:
    """
    Main game engine that orchestrates all modules.
    
    Runs the four-phase turn cycle:
    - Logic: Check rules and apply violations
    - Planning: Optimize task assignments
    - Adversarial: AI selects disruptive event
    - Resolution: Apply resource consumption and events
    """
    
    def __init__(
        self,
        initial_state: ColonyState = None,
        *,
        survival_use_rl: bool = True,
        survival_train_episodes: int = 800,
        director_use_rl: bool = False,
    ):
        """
        Initialize game engine with modules.
        
        Args:
            initial_state: Starting colony state (or None for default)
            survival_use_rl: If True (default), Module 6 uses tabular Q-learning after offline training.
            survival_train_episodes: Offline RL episodes when survival_use_rl is True.
        """
        self.state = initial_state or ColonyState()
        self.rule_engine = RuleEngine()
        self.task_planner = TaskPlanner(self.state)
        self.event_resolver = EventResolver()
        self.survival_assessor = SurvivalAssessor(use_rl=survival_use_rl)
        if survival_use_rl:
            self.survival_assessor.train_q_learning(
                episodes=survival_train_episodes,
                max_steps_per_episode=12,
                epsilon=0.15,
                seed=42,
            )

        # Initialize AI Director with available events
        self.available_events = self._create_default_events()
        self.ai_director = AIDirector(self.available_events)
        self.director_use_rl = bool(director_use_rl)
        self.budget_rl_director = BudgetRLDirector(seed=42) if self.director_use_rl else None
        self._director_prev_state: Optional[ColonyState] = None
        self._director_last_action: Optional[str] = None

        # Precomputed terrain move_speed grid (invalidated when world/seed/floor/difficulty changes).
        self._terrain_key: Optional[Tuple[Any, ...]] = None
        self._terrain_move_speeds: Optional[List[float]] = None
        self._terrain_wx0: int = 0
        self._terrain_wy0: int = 0
        self._terrain_w: int = 0
        self._terrain_h: int = 0

    def invalidate_terrain_cache(self) -> None:
        """Call after clear_tile_cache or any change to world bounds / seed / floor / difficulty."""
        self._terrain_key = None
        self._terrain_move_speeds = None

    def warm_terrain_cache(self) -> None:
        """Precompute move_speed grid (call after load / floor change to avoid a first-interaction hitch)."""
        self._ensure_terrain_grid()

    def _terrain_identity_key(self) -> Tuple[Any, ...]:
        s = self.state
        return (
            int(s.world_min_x),
            int(s.world_max_x),
            int(s.world_min_y),
            int(s.world_max_y),
            int(s.world_seed),
            str(s.difficulty or "normal"),
            int(getattr(s, "floor_index", 1)),
        )

    def _ensure_terrain_grid(self) -> None:
        key = self._terrain_identity_key()
        if self._terrain_key == key and self._terrain_move_speeds is not None:
            return
        from src.module1_state.procedural_tiles import build_move_speed_grid

        ms, wx0, wy0, w, h = build_move_speed_grid(
            key[0], key[1], key[2], key[3], key[4], key[5]
        )
        self._terrain_move_speeds = ms
        self._terrain_wx0 = wx0
        self._terrain_wy0 = wy0
        self._terrain_w = w
        self._terrain_h = h
        self._terrain_key = key

    def terrain_move_speed_at(self, x: int, y: int) -> float:
        """O(1) terrain movement multiplier at world (x,y); builds grid once per world identity."""
        self._ensure_terrain_grid()
        if not self._terrain_move_speeds or self._terrain_w <= 0:
            return 1.0
        xi, yi = int(x), int(y)
        if not (
            self._terrain_wx0 <= xi < self._terrain_wx0 + self._terrain_w
            and self._terrain_wy0 <= yi < self._terrain_wy0 + self._terrain_h
        ):
            return 1.0
        idx = (yi - self._terrain_wy0) * self._terrain_w + (xi - self._terrain_wx0)
        return self._terrain_move_speeds[idx]

    def _effective_base_repair_turns(self) -> int:
        return BASE_REPAIR_TURNS + int(getattr(self.state, "floor_repair_turns_extra", 0))

    def _adversary_suppressed_by_wood_quota(self) -> bool:
        q = required_wood_for_quota(float(getattr(self.state, "wood_quota", 0.0) or 0.0))
        if q <= 0:
            return False
        return float(self.state.resources.get("wood", 0.0)) >= float(q)

    def _create_default_events(self) -> list[Event]:
        """Create default catalog of available events."""
        return [
            Event(
                event_type="agent_trip_over_rock",
                location="agent",
                severity=0.5,
                resource_impact={"integrity": -17.0},
                description="Agent trips over rough terrain and damages equipment",
                cost=2.0,
                cooldown_turns=0,
                tags=["agent", "integrity"],
            ),
            Event(
                event_type="agent_oxygen_tank_puncture",
                location="agent",
                severity=0.45,
                resource_impact={"oxygen": -20.0},
                description="An agent's oxygen tank is punctured",
                cost=2.0,
                cooldown_turns=0,
                tags=["agent", "oxygen"],
            ),
            Event(
                event_type="agent_ration_spoilage",
                location="agent",
                severity=0.4,
                resource_impact={"calories": -18.0},
                description="An agent's ration pack spoils unexpectedly",
                cost=2.0,
                cooldown_turns=0,
                tags=["agent", "calories"],
            ),
        ]

    def set_ai_director_settings(
        self,
        aggression: Optional[float] = None,
        randomness: Optional[float] = None,
        repetition_window: Optional[int] = None,
    ) -> None:
        """Update AI director behavior settings at runtime."""
        self.ai_director.configure(
            aggression=aggression,
            randomness=randomness,
            repetition_window=repetition_window,
        )
    
    def run_logic_phase(self) -> Dict[str, Any]:
        """
        Run the **Logic phase** (Module 3: `RuleEngine`) on the current state.

        Returns:
            Dictionary report from `RuleEngine.evaluate_state`, including any
            violations found and consequences that were applied.
        """
        return self.rule_engine.evaluate_state(self.state)

    def run_planning_phase(
        self, player_tasks: list[Task] | None, algorithm: str = "astar"
    ) -> Dict[str, Any]:
        """
        Run the **Planning phase** (Module 2: `TaskPlanner`) for a set of tasks.

        Args:
            player_tasks: Tasks assigned by the player; if None or empty, no planning is performed.
            algorithm: Which search algorithm to use for task sequencing:
                - \"astar\" (default)
                - \"beam_search\"
                - \"idastar\" (uses A* for sequencing, IDA* only for pathfinding)

        Returns:
            Dictionary with a summary of task assignments, suitable for UI consumption:
            - \"tasks_assigned\": int
            - \"assignments\": list of dicts with task_id, agent_id, completion_time, path_coords, task_location
        """
        if not player_tasks:
            return {"tasks_assigned": 0}

        if algorithm == "beam_search":
            task_assignments = self.task_planner.plan_with_beam_search(player_tasks, beam_width=3)
        elif algorithm == "idastar":
            # IDA* is for pathfinding; task sequencing still uses A*
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

        return {
            "tasks_assigned": len(task_assignments),
            "assignments": assignments_data,
        }

    def run_adversarial_phase(self) -> Tuple[Event, Dict[str, Any]]:
        """
        Run the **Adversarial phase** (Module 4: `AIDirector`) on the current state.

        If ``wood >= wood_quota`` on the current floor, the Director is skipped and a
        no-op event is returned (no new disasters until the next floor).

        Returns:
            Tuple of:
                - The selected `Event` instance.
                - A small dictionary summary (type, location, severity) for reporting/visuals.
        """
        # Cooldowns tick even when the Director is suppressed (so the next floor isn't blocked).
        self.ai_director.tick_cooldowns(self.state)

        if self._adversary_suppressed_by_wood_quota():
            summary = {
                "event_selected": NO_ADVERSARY_EVENT.event_type,
                "location": NO_ADVERSARY_EVENT.location,
                "severity": NO_ADVERSARY_EVENT.severity,
                "target_station_id": None,
                "target_agent_id": None,
                "suppressed_by_wood_quota": True,
                "director_points": float(getattr(self.state, "director_points", 0.0)),
                "director_income": director_income_per_turn(
                    self.state.difficulty, int(getattr(self.state, "floor_index", 1))
                ),
            }
            return NO_ADVERSARY_EVENT, summary

        # Budget accrues every turn (even if nothing affordable is selected).
        income = director_income_per_turn(self.state.difficulty, int(getattr(self.state, "floor_index", 1)))
        cap = director_budget_cap(self.state.difficulty)
        cur_pts = float(getattr(self.state, "director_points", 0.0))
        cur_pts = min(cap, cur_pts + income)
        self.state.director_points = cur_pts

        preferred = None
        director_action = None
        if self.director_use_rl and self.budget_rl_director:
            self._director_prev_state = self.state.copy()
            director_action = self.budget_rl_director.choose_action(self.state, cur_pts)
            self._director_last_action = director_action
            pref = self.budget_rl_director.action_to_event_preference(director_action)
            preferred = pref.get("event_type")
            if director_action == ACTION_SAVE:
                preferred = None

        selected_event = self.ai_director.select_event_with_constraints(
            self.state,
            affordable_points=cur_pts,
            preferred_event_type=preferred,
        )

        # Spend points if a real event was purchased.
        spend = float(getattr(selected_event, "cost", 0.0) or 0.0)
        if selected_event.event_type != NO_ADVERSARY_EVENT.event_type and spend > 0.0:
            self.state.director_points = max(0.0, float(self.state.director_points) - spend)
            self.state.director_last_purchase_turn = int(self.state.turn_number)
            self.state.director_last_purchase_type = str(selected_event.event_type)

        summary = {
            "event_selected": selected_event.event_type,
            "location": selected_event.location,
            "severity": selected_event.severity,
            # For station_breakdown, this is the concrete station target.
            "target_station_id": selected_event.target_station_id,
            "target_agent_id": selected_event.target_agent_id,
            "suppressed_by_wood_quota": False,
            "director_income": float(income),
            "director_points": float(getattr(self.state, "director_points", 0.0)),
            "director_event_cost": float(spend),
            "director_action": director_action,
        }
        return selected_event, summary

    def run_resolution_phase(self, selected_event: Event) -> Dict[str, Any]:
        """
        Run the **Resolution phase** (Modules 1 and 5) on the current state.

        This applies per-turn resource consumption and then applies the
        selected event via the `EventResolver`.

        Args:
            selected_event: Event chosen by the AI Director in the Adversarial phase.

        Returns:
            Dictionary report from `EventResolver.apply_event`, including the
            updated state snapshot and any cascading effects.
        """
        # Apply resource consumption from agent activity
        base_consumption = {"oxygen": -5.0, "calories": -3.0}
        self.state.consume_resources(base_consumption)

        # Apply selected event
        return self.event_resolver.apply_event(self.state, selected_event)

    def execute_turn(self, player_tasks: list[Task] = None, algorithm: str = "astar") -> Dict[str, Any]:
        """
        Execute one complete turn through all four phases using the orchestration:
        Logic → Planning → Adversarial → Resolution (+ Survival Assessment).

        Args:
            player_tasks: Tasks assigned by player (optional).
            algorithm: Algorithm to use for task planning (\"astar\", \"beam_search\", \"idastar\").

        Returns:
            Turn report with results from each phase and a survival assessment, in the form:
            {
                \"turn_number\": int,
                \"phases\": {
                    \"logic\": {...},
                    \"planning\": {...},
                    \"adversarial\": {...},
                    \"resolution\": {...},
                },
                \"survival_assessment\": {...},
            }
        """
        turn_report: Dict[str, Any] = {
            "turn_number": self.state.turn_number,
            "phases": {},
        }

        # Phase 1: Logic - Rule Enforcement (Module 3)
        logic_result = self.run_logic_phase()
        turn_report["phases"]["logic"] = logic_result

        # Warning-stage stations tick down to full breakdown.
        warning_result = self._advance_station_failure_warnings()
        turn_report["phases"]["warning_progression"] = warning_result

        # Station repair progression (player-driven, time-based; scales with agents present)
        repair_result = self._advance_station_repairs()
        turn_report["phases"]["repairs"] = repair_result

        # Phase 2: Planning - Task Optimization (Module 2)
        planning_result = self.run_planning_phase(player_tasks, algorithm=algorithm)
        turn_report["phases"]["planning"] = planning_result

        # Phase 3: Adversarial - AI Event Selection (Module 4)
        selected_event, adversarial_summary = self.run_adversarial_phase()
        turn_report["phases"]["adversarial"] = adversarial_summary
        if selected_event.event_type != NO_ADVERSARY_EVENT.event_type:
            self.state.floor_disasters_count = int(getattr(self.state, "floor_disasters_count", 0)) + 1

        # Phase 4: Resolution - Resource Consumption & Event Application (Modules 1 & 5)
        resolution_result = self.run_resolution_phase(selected_event)
        turn_report["phases"]["resolution"] = resolution_result

        # Optional: learn director policy online from realized event effects.
        if (
            self.director_use_rl
            and self.budget_rl_director
            and self._director_prev_state is not None
            and self._director_last_action is not None
        ):
            try:
                self.budget_rl_director.learn_from_turn(
                    self._director_prev_state,
                    self._director_last_action,
                    resolution_result,
                    self.state,
                )
            except Exception:
                # Training must never crash gameplay.
                pass
        self._director_prev_state = None
        self._director_last_action = None

        # Survival Assessment (Module 6)
        survival_assessment = self.survival_assessor.assess_survival(self.state)
        turn_report["survival_assessment"] = survival_assessment

        # First turn wood reached quota (before incrementing turn counter)
        wq = required_wood_for_quota(float(getattr(self.state, "wood_quota", 0.0) or 0.0))
        if wq > 0 and float(self.state.resources.get("wood", 0.0)) >= float(wq):
            if getattr(self.state, "turn_wood_quota_met", None) is None:
                self.state.turn_wood_quota_met = int(self.state.turn_number)

        # Slow extra trees on grass/dirt if quota is otherwise unreachable this floor.
        tree_spawned = maybe_spawn_progression_tree(self.state)
        turn_report["phases"]["tree_regrowth"] = {"spawned": tree_spawned}

        # Advance to next turn
        self.state.next_turn()

        return turn_report

    def _resource_stations(self) -> List[Dict[str, Any]]:
        """Return infrastructure entries that represent resource stations."""
        stations: List[Dict[str, Any]] = []
        infra = self.state.infrastructure or {}
        for station_id, info in infra.items():
            if not isinstance(info, dict):
                continue
            if info.get("kind") != "resource_station":
                continue
            center = info.get("center")
            size = info.get("size")
            if not isinstance(center, (tuple, list)) or len(center) != 2:
                continue
            if not isinstance(size, int):
                continue
            stations.append({
                "station_id": station_id,
                "center_x": int(center[0]),
                "center_y": int(center[1]),
                "size": int(size),
                "status": info.get("status", "operational"),
                "repair_remaining_turns": int(info.get("repair_remaining_turns", 0)),
                "repair_agent_id": info.get("repair_agent_id"),
            })
        return stations

    def _station_tiles(self, center_x: int, center_y: int, size: int) -> List[Tuple[int, int]]:
        """Return all world tiles occupied by a station footprint."""
        offset = size // 2
        tiles: List[Tuple[int, int]] = []
        for x in range(center_x - offset, center_x + offset + 1):
            for y in range(center_y - offset, center_y + offset + 1):
                tiles.append((x, y))
        return tiles

    def _is_failed_station_tile(self, x: int, y: int) -> bool:
        """True if tile (x, y) belongs to a failed resource station footprint."""
        for station in self._resource_stations():
            if station["status"] != "failed":
                continue
            if (x, y) in self._station_tiles(station["center_x"], station["center_y"], station["size"]):
                return True
        return False

    def _agents_on_station(self, center_x: int, center_y: int, size: int) -> List[Dict[str, Any]]:
        """Return living agents currently standing on the given station footprint."""
        tiles = set(self._station_tiles(center_x, center_y, size))
        present: List[Dict[str, Any]] = []
        for agent in self.state.agents:
            if agent.get("status") == "dead":
                continue
            loc = agent.get("location")
            if not isinstance(loc, (tuple, list)) or len(loc) != 2:
                continue
            if (int(loc[0]), int(loc[1])) in tiles:
                present.append(agent)
        return present

    def _advance_station_repairs(self) -> Dict[str, Any]:
        """
        Advance time-based repair progress for failed resource stations.

        Rules:
        - Repair progresses only while one or more living agents are on-station.
        - Progress per turn scales with number of agents present, capped.
        - Repair can pause/resume and allows handoff between agents.
        """
        repaired: List[str] = []
        progressed: List[Dict[str, Any]] = []
        paused: List[str] = []

        infra = self.state.infrastructure or {}
        for station in self._resource_stations():
            station_id = station["station_id"]
            if station["status"] != "failed":
                continue
            info = infra.get(station_id)
            if not isinstance(info, dict):
                continue

            eff_base = self._effective_base_repair_turns()
            remaining = int(info.get("repair_remaining_turns", 0))
            if remaining <= 0:
                remaining = eff_base
                info["repair_remaining_turns"] = remaining
            if int(info.get("repair_total_turns", 0)) <= 0:
                info["repair_total_turns"] = max(remaining, eff_base)

            on_station = self._agents_on_station(station["center_x"], station["center_y"], station["size"])
            if not on_station:
                info["repair_agent_id"] = None
                paused.append(station_id)
                continue

            # Handoff allowed: choose deterministic owner among present agents.
            sorted_present = sorted(on_station, key=lambda a: int(a.get("id", 10**9)))
            repair_agent_id = sorted_present[0].get("id")
            info["repair_agent_id"] = repair_agent_id

            effective_agents = min(len(on_station), MAX_EFFECTIVE_REPAIR_AGENTS)
            remaining = max(0, remaining - effective_agents)
            info["repair_remaining_turns"] = remaining
            progressed.append({
                "station_id": station_id,
                "repair_agent_id": repair_agent_id,
                "agents_on_station": len(on_station),
                "effective_agents": effective_agents,
                "remaining_turns": remaining,
            })

            if remaining <= 0:
                info["status"] = "operational"
                info["repair_agent_id"] = None
                repaired.append(station_id)

        return {"repaired": repaired, "progressed": progressed, "paused": paused}

    def _advance_station_failure_warnings(self) -> Dict[str, Any]:
        """Advance warning stations and escalate to failed when timer expires."""
        escalated: List[str] = []
        ticking: List[Dict[str, Any]] = []
        infra = self.state.infrastructure or {}
        for station in self._resource_stations():
            if station["status"] != "warning":
                continue
            station_id = station["station_id"]
            info = infra.get(station_id)
            if not isinstance(info, dict):
                continue
            remaining = max(0, int(info.get("warning_turns_remaining", 1)) - 1)
            info["warning_turns_remaining"] = remaining
            ticking.append({"station_id": station_id, "warning_turns_remaining": remaining})
            if remaining <= 0:
                info["status"] = "failed"
                info["warning_turns_remaining"] = 0
                eff_base = self._effective_base_repair_turns()
                if int(info.get("repair_remaining_turns", 0)) <= 0:
                    info["repair_remaining_turns"] = eff_base
                if int(info.get("repair_total_turns", 0)) <= 0:
                    info["repair_total_turns"] = eff_base
                info["repair_agent_id"] = None
                escalated.append(station_id)
        return {"warning_ticking": ticking, "escalated_to_failed": escalated}
    
    def _is_tile_passable(self, x: int, y: int, exclude_agent_id: Optional[int] = None) -> bool:
        """
        Check if a tile is passable (terrain check only - agents can pass through each other).
        
        Args:
            x, y: Tile coordinates
            exclude_agent_id: Not used (kept for compatibility)
        
        Returns:
            True if tile is passable
        """
        mn_x = int(getattr(self.state, "world_min_x", -25))
        mx_x = int(getattr(self.state, "world_max_x", 25))
        mn_y = int(getattr(self.state, "world_min_y", -25))
        mx_y = int(getattr(self.state, "world_max_y", 25))
        if not (mn_x <= x < mx_x and mn_y <= y < mx_y):
            return False
        # Procedural terrain marks all tile types passable; skip get_tile_at (hot in A*).
        return True
    
    def _grid_pathfind(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        exclude_agent_id: Optional[int] = None,
        allow_blocked_goal: bool = True,
    ) -> List[Tuple[int, int]]:
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
        
        goal_blocked = not self._is_tile_passable(goal[0], goal[1], exclude_agent_id)

        # Allow targeting a blocked goal tile (used for repairing failed stations),
        # but still prevent passing through blocked tiles.
        if goal_blocked and not allow_blocked_goal:
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

        # Admissible octile heuristic for 8-neighbor moves with cost 1 (cardinal) / sqrt(2) (diagonal).
        d_diag = 1.4142135623730951

        def heuristic(pos: Tuple[int, int]) -> float:
            dx = abs(goal[0] - pos[0])
            dy = abs(goal[1] - pos[1])
            dmin = min(dx, dy)
            dmax = max(dx, dy)
            return d_diag * dmin + (dmax - dmin)

        # 8-directional movement (cardinal + diagonal)
        neighbors = [
            (0, 1), (1, 0), (0, -1), (-1, 0),  # Cardinal
            (1, 1), (-1, 1), (1, -1), (-1, -1)  # Diagonal
        ]

        mn_x = int(getattr(self.state, "world_min_x", -25))
        mx_x = int(getattr(self.state, "world_max_x", 25))
        mn_y = int(getattr(self.state, "world_min_y", -25))
        mx_y = int(getattr(self.state, "world_max_y", 25))
        w = max(1, mx_x - mn_x)
        h = max(1, mx_y - mn_y)
        area = w * h
        # Many duplicate heap entries possible; cap scales with map size (fixes long paths on 200×200+).
        max_iterations = min(max(area * 12, 50_000), 3_000_000)
        iterations = 0

        self._ensure_terrain_grid()
        ms = self._terrain_move_speeds
        twx0, twy0, tw, th = self._terrain_wx0, self._terrain_wy0, self._terrain_w, self._terrain_h
        
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
                    # Blocked goal tile is allowed only as final destination.
                    if not (allow_blocked_goal and neighbor == goal):
                        continue
                
                # Movement cost from precomputed grid (avoids get_tile dict per neighbor)
                nx_, ny_ = int(neighbor[0]), int(neighbor[1])
                if ms is not None and tw > 0 and twx0 <= nx_ < twx0 + tw and twy0 <= ny_ < twy0 + th:
                    tile_move_speed = ms[(ny_ - twy0) * tw + (nx_ - twx0)]
                else:
                    tile_move_speed = float(
                        self.state.get_tile_at(nx_, ny_).get("move_speed", 1.0)
                    )

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
        path_coords = self._grid_pathfind(
            start,
            goal,
            exclude_agent_id=agent_id,
            allow_blocked_goal=True,
        )
        
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
        Check if game is over (no agents or all agents dead).
        
        Returns:
            True if game should end
        """
        if len(self.state.agents) == 0:
            return True
        
        # All agents dead (no living agents left)
        living = [a for a in self.state.agents if a.get("status") != "dead"]
        if not living:
            return True
        
        return False
