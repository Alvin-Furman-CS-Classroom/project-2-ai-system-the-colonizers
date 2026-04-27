"""
Event Resolution & State Update

This module applies events to the colony state, calculating damage,
updating resources, and handling cascading effects.

Input: Selected event from Module 4, current colony state
Output: Modified colony state after event application

Live catalog vs. legacy handlers:
    The default ``GameEngine`` event catalog uses agent-targeted hazards
    (see ``GameEngine._create_default_events``) and station breakdown
    events chosen by the Director. Handlers for ``hull_breach``,
    ``resource_shortage``, and ``equipment_failure`` remain supported for
    tests and custom Director catalogs; they are not in the default catalog.
"""

from typing import Any, Callable, Dict, List
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import Event

BASE_REPAIR_TURNS = 4

# Softens agent-targeted hazards (trip / puncture / spoilage) for playability.
AGENT_HAZARD_DAMAGE_SCALE = 0.76
WARNING_TO_FAILURE_TURNS = 1
PER_AGENT_DEPLETION_PERCENT_MULTIPLIER = 1.2
PER_AGENT_DEPLETION_PERCENT_MIN = 0.10
PER_AGENT_DEPLETION_PERCENT_MAX = 0.60

HULL_BREACH_INFRA_DAMAGE_SCALE = 50.0
HULL_BREACH_AGENT_INTEGRITY_SCALE = 20.0
HULL_BREACH_CASCADE_DAMAGE_SCALE = 10.0
HULL_BREACH_CASCADE_SEVERITY_THRESHOLD = 0.7
EQUIPMENT_EFFICIENCY_REDUCTION_MAX = 0.3

def _effective_repair_turns(colony_state: ColonyState) -> int:
    return BASE_REPAIR_TURNS + int(getattr(colony_state, "floor_repair_turns_extra", 0))


AGENT_HAZARD_TYPES = {
    "agent_trip_over_rock",
    "agent_oxygen_tank_puncture",
    "agent_ration_spoilage",
}


class EventResolver:
    """
    Resolves events by applying them to colony state.
    
    Handles:
    - Direct resource impacts
    - Infrastructure damage
    - Agent status changes
    - Cascading effects (e.g., hull breach affects adjacent areas)
    """
    
    def __init__(self):
        """Initialize event resolver with event handlers."""
        self.event_handlers = self._initialize_handlers()
    
    def _initialize_handlers(self) -> Dict[str, Callable[..., Any]]:
        """
        Initialize handlers for different event types.
        
        Returns:
            Dictionary mapping event types to handler functions
        """
        return {
            "hull_breach": self._handle_hull_breach,
            "resource_shortage": self._handle_resource_shortage,
            "equipment_failure": self._handle_equipment_failure,
            "no_adversarial_event": self._handle_no_adversarial_event,
            "station_breakdown": self._handle_station_breakdown,
            "agent_trip_over_rock": self._handle_agent_trip_over_rock,
            "agent_oxygen_tank_puncture": self._handle_agent_oxygen_tank_puncture,
            "agent_ration_spoilage": self._handle_agent_ration_spoilage,
            # Add more event handlers as needed
        }
    
    def apply_event(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """
        Apply an event to the colony state.
        
        This is called during the Resolution phase to apply
        the event selected by the AI Director.
        
        Args:
            colony_state: Current state to modify
            event: Event to apply
            
        Returns:
            Report of changes made
        """
        # Agent hazards target one specific agent, not global state pools.
        if event.event_type not in AGENT_HAZARD_TYPES:
            colony_state.consume_resources(event.resource_impact)
            # Resource-depleting events should also hit each living agent's personal resources.
            self._apply_agent_resource_depletion(colony_state, event)
        
        # Apply event-specific effects
        handler = self.event_handlers.get(event.event_type, self._handle_generic)
        specific_effects = handler(colony_state, event)
        
        # Check for cascading effects
        cascading_effects = self._check_cascading_effects(colony_state, event)
        
        return {
            "event_applied": event.event_type,
            "location": event.location,
            "severity": event.severity,
            "resource_changes": event.resource_impact,
            "specific_effects": specific_effects,
            "cascading_effects": cascading_effects,
            "state_after": colony_state.to_dict()
        }

    def _apply_agent_resource_depletion(self, colony_state: ColonyState, event: Event) -> None:
        """Apply percentage-based per-agent depletion for negative resource-impact events."""
        if not event.resource_impact:
            return
        depletion_percent: Dict[str, float] = {}
        for resource, impact in event.resource_impact.items():
            if impact >= 0:
                continue
            percent = min(
                PER_AGENT_DEPLETION_PERCENT_MAX,
                max(
                    PER_AGENT_DEPLETION_PERCENT_MIN,
                    (abs(float(impact)) / 100.0) * PER_AGENT_DEPLETION_PERCENT_MULTIPLIER,
                ),
            )
            depletion_percent[resource] = percent
        if not depletion_percent:
            return
        for agent in colony_state.agents:
            if agent.get("status") == "dead":
                continue
            agent_id = agent.get("id")
            if agent_id is None:
                continue
            per_agent_depletion: Dict[str, float] = {}
            for resource, percent in depletion_percent.items():
                current_value = float(agent.get(resource, 0.0))
                per_agent_depletion[resource] = -(current_value * percent)
            colony_state.consume_agent_resources(int(agent_id), per_agent_depletion)
    
    def _handle_hull_breach(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """
        Handle hull breach event.
        
        Hull breaches cause oxygen loss and may affect infrastructure.
        
        Args:
            colony_state: State to modify
            event: Hull breach event
            
        Returns:
            Effects applied
        """
        effects = {
            "infrastructure_damaged": [],
            "agents_affected": []
        }
        
        # Damage infrastructure at location
        if event.location not in colony_state.infrastructure:
            colony_state.infrastructure[event.location] = {"integrity": 100.0}
        
        damage = event.severity * HULL_BREACH_INFRA_DAMAGE_SCALE
        colony_state.infrastructure[event.location]["integrity"] -= damage
        effects["infrastructure_damaged"].append({
            "location": event.location,
            "damage": damage
        })
        
        # Agents in affected location may be harmed
        for i, agent in enumerate(colony_state.agents):
            if agent.get("location") == event.location:
                # Agents exposed to vacuum take damage
                agent["integrity"] = agent.get("integrity", 100.0) - (
                    event.severity * HULL_BREACH_AGENT_INTEGRITY_SCALE
                )
                effects["agents_affected"].append(i)
        
        return effects
    
    def _handle_resource_shortage(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """
        Handle resource shortage event.
        
        Resource shortages directly reduce available resources.
        
        Args:
            colony_state: State to modify
            event: Resource shortage event
            
        Returns:
            Effects applied
        """
        # Resource impacts already applied in apply_event
        return {
            "shortage_type": list(event.resource_impact.keys()),
            "severity": event.severity
        }
    
    def _handle_equipment_failure(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """
        Handle equipment failure event.
        
        Equipment failures reduce system efficiency and may cause
        increased resource consumption.
        
        Args:
            colony_state: State to modify
            event: Equipment failure event
            
        Returns:
            Effects applied
        """
        effects = {
            "equipment_failed": event.location,
            "efficiency_reduction": event.severity * EQUIPMENT_EFFICIENCY_REDUCTION_MAX,
        }
        
        # Mark equipment as failed in infrastructure
        if event.location not in colony_state.infrastructure:
            colony_state.infrastructure[event.location] = {}
        
        colony_state.infrastructure[event.location]["status"] = "failed"
        colony_state.infrastructure[event.location]["efficiency"] = 1.0 - effects["efficiency_reduction"]
        
        return effects
    
    def _handle_no_adversarial_event(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """Director suppressed when colony wood >= per-floor quota; no disaster effect."""
        return {"suppressed": True, "reason": "wood_quota_met"}

    def _handle_generic(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """
        Generic handler for unknown event types.
        
        Args:
            colony_state: State to modify
            event: Generic event
            
        Returns:
            Basic effects
        """
        return {
            "event_type": event.event_type,
            "note": "Generic handler applied"
        }

    def _handle_station_breakdown(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """
        Handle resource station breakdown events.

        Marks the targeted station as failed and initializes repair metadata.
        """
        station_id = event.target_station_id or event.location
        if not station_id:
            return {"error": "Missing target station id for station_breakdown"}

        station = colony_state.infrastructure.get(station_id)
        if not isinstance(station, dict) or station.get("kind") != "resource_station":
            return {"error": f"Invalid station target: {station_id}"}

        prior_status = station.get("status", "operational")
        if prior_status == "operational":
            # Stage 1: visible warning state before full breakdown.
            station["status"] = "warning"
            station["warning_turns_remaining"] = WARNING_TO_FAILURE_TURNS
            return {
                "station_id": station_id,
                "status": station["status"],
                "warning_turns_remaining": station["warning_turns_remaining"],
            }

        # Stage 2: full breakdown (either already warning or directly escalated).
        station["status"] = "failed"
        station["warning_turns_remaining"] = 0
        eff = _effective_repair_turns(colony_state)
        if int(station.get("repair_remaining_turns", 0)) <= 0:
            station["repair_remaining_turns"] = eff
        station["repair_total_turns"] = max(
            int(station.get("repair_total_turns", eff)),
            int(station.get("repair_remaining_turns", eff)),
        )
        station["repair_agent_id"] = None

        return {
            "station_id": station_id,
            "status": station["status"],
            "repair_remaining_turns": station["repair_remaining_turns"],
        }

    def _resolve_target_agent_id(self, colony_state: ColonyState, event: Event, resource: str) -> Any:
        """Pick explicit target agent id or fallback to weakest living agent in a resource."""
        if event.target_agent_id is not None:
            return int(event.target_agent_id)
        living = [a for a in colony_state.agents if a.get("status") != "dead" and a.get("id") is not None]
        if not living:
            return None
        weakest = min(living, key=lambda a: float(a.get(resource, 100.0)))
        return int(weakest.get("id"))

    def _apply_targeted_agent_impact(
        self, colony_state: ColonyState, event: Event, resource: str, base_impact: float
    ) -> Dict[str, Any]:
        """Apply a negative impact to one targeted living agent's resource."""
        target_id = self._resolve_target_agent_id(colony_state, event, resource)
        if target_id is None:
            return {"error": "No living agent available"}
        severity_term = 0.75 + (0.48 * float(event.severity))
        magnitude = (
            abs(float(base_impact)) * severity_term * AGENT_HAZARD_DAMAGE_SCALE
        )
        applied = -magnitude
        ok = colony_state.consume_agent_resources(target_id, {resource: applied})
        if not ok:
            return {"error": f"Target agent not found: {target_id}"}
        return {
            "target_agent_id": target_id,
            "resource": resource,
            "applied_delta": applied,
            "severity": event.severity,
        }

    def _handle_agent_trip_over_rock(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """Targeted integrity damage to one agent."""
        return self._apply_targeted_agent_impact(
            colony_state,
            event,
            resource="integrity",
            base_impact=float((event.resource_impact or {}).get("integrity", -17.0)),
        )

    def _handle_agent_oxygen_tank_puncture(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """Targeted oxygen damage to one agent."""
        return self._apply_targeted_agent_impact(
            colony_state,
            event,
            resource="oxygen",
            base_impact=float((event.resource_impact or {}).get("oxygen", -25.0)),
        )

    def _handle_agent_ration_spoilage(self, colony_state: ColonyState, event: Event) -> Dict[str, Any]:
        """Targeted calories damage to one agent."""
        return self._apply_targeted_agent_impact(
            colony_state,
            event,
            resource="calories",
            base_impact=float((event.resource_impact or {}).get("calories", -18.0)),
        )
    
    def _check_cascading_effects(self, colony_state: ColonyState, event: Event) -> List[Dict[str, Any]]:
        """
        Check for cascading effects from the event.
        
        Some events trigger additional effects:
        - Hull breach in one section may affect adjacent sections
        - Equipment failure may cause increased resource consumption
        - System failures may compound
        
        Args:
            colony_state: Current state
            event: Event that was applied
            
        Returns:
            List of cascading effects
        """
        cascading = []
        
        # Example: Hull breach affects adjacent sections
        if (
            event.event_type == "hull_breach"
            and event.severity > HULL_BREACH_CASCADE_SEVERITY_THRESHOLD
        ):
            adjacent_locations = self._get_adjacent_locations(event.location)
            for adj_location in adjacent_locations:
                if adj_location in colony_state.infrastructure:
                    minor_damage = event.severity * HULL_BREACH_CASCADE_DAMAGE_SCALE
                    if "integrity" not in colony_state.infrastructure[adj_location]:
                        colony_state.infrastructure[adj_location]["integrity"] = 100.0
                    colony_state.infrastructure[adj_location]["integrity"] -= minor_damage
                    
                    cascading.append({
                        "type": "adjacent_damage",
                        "location": adj_location,
                        "damage": minor_damage
                    })
        
        return cascading
    
    def _get_adjacent_locations(self, location: str) -> List[str]:
        """
        Named infrastructure sections in this project do not carry a graph of
        neighbors. High-severity hull breach therefore has no adjacent sections
        to spread to unless a future layout model supplies adjacency here.

        Args:
            location: Current section identifier (unused until a graph exists)

        Returns:
            Adjacent location ids; currently always empty.
        """
        return []
