"""
Game Engine

Main game loop that coordinates all modules through the four phases:
1. Logic: Rule enforcement (Module 3)
2. Planning: Task optimization (Module 2)
3. Adversarial: AI event selection (Module 4)
4. Resolution: Resource consumption and event application (Modules 1, 5)
"""

from typing import Dict, Any
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
    
    def execute_turn(self, player_tasks: list[Task] = None) -> Dict[str, Any]:
        """
        Execute one complete turn through all four phases.
        
        Args:
            player_tasks: Tasks assigned by player (optional)
            
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
            task_assignments = self.task_planner.plan_with_astar(player_tasks)
            turn_report["phases"]["planning"] = {
                "tasks_assigned": len(task_assignments),
                "assignments": [
                    {
                        "task_id": a.task.task_id,
                        "agent_id": a.agent_id,
                        "completion_time": a.completion_time
                    }
                    for a in task_assignments
                ]
            }
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
