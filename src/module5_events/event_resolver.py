"""
Event Resolution & State Update

This module applies events to the colony state, calculating damage,
updating resources, and handling cascading effects.

Input: Selected event from Module 4, current colony state
Output: Modified colony state after event application
"""

from typing import Dict, Any, List
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import Event


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
    
    def _initialize_handlers(self) -> Dict[str, callable]:
        """
        Initialize handlers for different event types.
        
        Returns:
            Dictionary mapping event types to handler functions
        """
        return {
            "hull_breach": self._handle_hull_breach,
            "resource_shortage": self._handle_resource_shortage,
            "equipment_failure": self._handle_equipment_failure,
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
        # Apply direct resource impacts
        colony_state.consume_resources(event.resource_impact)
        
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
        
        damage = event.severity * 50.0  # Scale damage by severity
        colony_state.infrastructure[event.location]["integrity"] -= damage
        effects["infrastructure_damaged"].append({
            "location": event.location,
            "damage": damage
        })
        
        # Agents in affected location may be harmed
        for i, agent in enumerate(colony_state.agents):
            if agent.get("location") == event.location:
                # Agents exposed to vacuum take damage
                agent["integrity"] = agent.get("integrity", 100.0) - (event.severity * 20.0)
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
            "efficiency_reduction": event.severity * 0.3  # 30% max reduction
        }
        
        # Mark equipment as failed in infrastructure
        if event.location not in colony_state.infrastructure:
            colony_state.infrastructure[event.location] = {}
        
        colony_state.infrastructure[event.location]["status"] = "failed"
        colony_state.infrastructure[event.location]["efficiency"] = 1.0 - effects["efficiency_reduction"]
        
        return effects
    
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
        if event.event_type == "hull_breach" and event.severity > 0.7:
            # High severity breaches may spread
            adjacent_locations = self._get_adjacent_locations(event.location)
            for adj_location in adjacent_locations:
                if adj_location in colony_state.infrastructure:
                    # Apply minor damage to adjacent areas
                    minor_damage = event.severity * 10.0
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
        Get list of adjacent locations to a given location.
        
        Args:
            location: Location identifier
            
        Returns:
            List of adjacent location identifiers
        """
        # TODO: Implement location adjacency logic
        # This depends on your colony layout structure
        # For now, return empty list
        return []
