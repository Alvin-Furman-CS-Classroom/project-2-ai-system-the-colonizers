"""
Unit tests for Module 5: Event Resolution & State Update

Tests event application and state transitions.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import Event
from src.module5_events.event_resolver import EventResolver


class TestEventResolver(unittest.TestCase):
    """Test cases for EventResolver class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ColonyState()
        self.resolver = EventResolver()
    
    def test_apply_event_hull_breach(self):
        """Test applying hull breach event."""
        event = Event("hull_breach", "section_alpha", 0.5, {"oxygen": -20.0}, "Test breach")
        initial_oxygen = self.state.resources["oxygen"]
        result = self.resolver.apply_event(self.state, event)
        # Oxygen should be reduced
        self.assertLess(self.state.resources["oxygen"], initial_oxygen)
        self.assertEqual(result["event_applied"], "hull_breach")
    
    def test_apply_event_resource_shortage(self):
        """Test applying resource shortage event."""
        event = Event("resource_shortage", "storage", 0.3, {"calories": -15.0}, "Test shortage")
        initial_calories = self.state.resources["calories"]
        result = self.resolver.apply_event(self.state, event)
        self.assertLess(self.state.resources["calories"], initial_calories)
    
    def test_cascading_effects(self):
        """Test cascading effects from high-severity events."""
        # High severity hull breach should trigger cascading effects
        event = Event("hull_breach", "section_alpha", 0.8, {"oxygen": -30.0}, "Severe breach")
        result = self.resolver.apply_event(self.state, event)
        # Should have cascading effects if severity > 0.7
        if event.severity > 0.7:
            self.assertIn("cascading_effects", result)

    def test_station_breakdown_marks_station_failed(self):
        """Station breakdown should mark targeted station failed and initialize repair metadata."""
        self.state.infrastructure["oxy_station_1"] = {
            "kind": "resource_station",
            "station_id": "oxy_station_1",
            "resource_type": "oxygen",
            "center": (0, 0),
            "size": 2,
            "status": "operational",
            "repair_remaining_turns": 0,
            "repair_agent_id": None,
        }
        event = Event(
            "station_breakdown",
            "oxy_station_1",
            0.6,
            {},
            "Oxygen station failure",
            target_station_id="oxy_station_1",
        )
        result = self.resolver.apply_event(self.state, event)
        station = self.state.infrastructure["oxy_station_1"]
        self.assertEqual(result["event_applied"], "station_breakdown")
        self.assertEqual(station.get("status"), "failed")
        self.assertGreater(int(station.get("repair_remaining_turns", 0)), 0)


if __name__ == "__main__":
    unittest.main()
