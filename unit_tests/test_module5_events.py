"""
Unit tests for Module 5: Event Resolution & State Update

Tests event application and state transitions.
"""

import copy
import unittest
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import Event
from src.module5_events.event_resolver import EventResolver


def _colony_with_two_agents() -> ColonyState:
    return ColonyState(
        {
            "agents": [
                {
                    "id": 0,
                    "name": "Strong",
                    "location": (0, 0),
                    "status": "active",
                    "oxygen": 88.0,
                    "calories": 88.0,
                    "integrity": 90.0,
                },
                {
                    "id": 1,
                    "name": "Weak",
                    "location": (1, 0),
                    "status": "active",
                    "oxygen": 40.0,
                    "calories": 70.0,
                    "integrity": 50.0,
                },
            ],
            "resources": {"oxygen": 100.0, "calories": 100.0, "integrity": 100.0},
            "infrastructure": {},
            "active_tasks": [],
            "turn_number": 0,
            "world_seed": 0,
            "difficulty": "normal",
        }
    )


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

    def test_station_breakdown_has_warning_then_failed(self):
        """Station breakdown should pass through warning before becoming failed."""
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
        result = self.resolver.apply_event(self.state, event)  # Stage 1
        station = self.state.infrastructure["oxy_station_1"]
        self.assertEqual(result["event_applied"], "station_breakdown")
        self.assertEqual(station.get("status"), "warning")
        self.assertGreaterEqual(int(station.get("warning_turns_remaining", 0)), 0)

        self.resolver.apply_event(self.state, event)  # Stage 2
        self.assertEqual(station.get("status"), "failed")
        self.assertGreater(int(station.get("repair_remaining_turns", 0)), 0)

    def test_agent_hazards_skip_colony_pools_and_percent_sweep(self):
        """Agent-targeted events must not alter shared resources or all agents via depletion."""
        state = _colony_with_two_agents()
        pools_before = copy.deepcopy(state.resources)
        integ_before = [float(a["integrity"]) for a in state.agents]
        event = Event(
            "agent_trip_over_rock",
            "agent",
            0.5,
            {"integrity": -22.0},
            "trip",
        )
        self.resolver.apply_event(state, event)
        self.assertEqual(state.resources, pools_before)
        # Only one agent should lose integrity materially; the other unchanged.
        deltas = [float(state.agents[i]["integrity"]) - integ_before[i] for i in (0, 1)]
        self.assertTrue(any(d < -1.0 for d in deltas))
        self.assertTrue(any(d > -1.0 for d in deltas))

    def test_agent_trip_targets_weakest_integrity(self):
        state = _colony_with_two_agents()
        event = Event(
            "agent_trip_over_rock",
            "agent",
            0.5,
            {"integrity": -22.0},
            "trip",
        )
        w0, w1 = float(state.agents[0]["integrity"]), float(state.agents[1]["integrity"])
        self.resolver.apply_event(state, event)
        self.assertLess(state.agents[1]["integrity"], w1)
        self.assertEqual(state.agents[0]["integrity"], w0)

    def test_agent_trip_respects_explicit_target_agent_id(self):
        state = _colony_with_two_agents()
        event = Event(
            "agent_trip_over_rock",
            "agent",
            0.5,
            {"integrity": -22.0},
            "trip",
            target_agent_id=0,
        )
        w0, w1 = float(state.agents[0]["integrity"]), float(state.agents[1]["integrity"])
        self.resolver.apply_event(state, event)
        self.assertLess(state.agents[0]["integrity"], w0)
        self.assertEqual(state.agents[1]["integrity"], w1)

    def test_agent_oxygen_puncture_targets_weakest_oxygen(self):
        state = _colony_with_two_agents()
        event = Event(
            "agent_oxygen_tank_puncture",
            "agent",
            0.45,
            {"oxygen": -26.0},
            "puncture",
        )
        o0, o1 = float(state.agents[0]["oxygen"]), float(state.agents[1]["oxygen"])
        self.resolver.apply_event(state, event)
        self.assertLess(state.agents[1]["oxygen"], o1)
        self.assertEqual(state.agents[0]["oxygen"], o0)

    def test_agent_ration_spoilage_targets_weakest_calories(self):
        state = _colony_with_two_agents()
        event = Event(
            "agent_ration_spoilage",
            "agent",
            0.4,
            {"calories": -24.0},
            "spoiled",
        )
        c0, c1 = float(state.agents[0]["calories"]), float(state.agents[1]["calories"])
        self.resolver.apply_event(state, event)
        self.assertLess(state.agents[1]["calories"], c1)
        self.assertEqual(state.agents[0]["calories"], c0)


if __name__ == "__main__":
    unittest.main()
