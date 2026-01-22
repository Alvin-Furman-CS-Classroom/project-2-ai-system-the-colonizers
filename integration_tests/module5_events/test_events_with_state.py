"""
Integration test: Module 5 (Events) with Modules 1 & 4

Tests that events from AI Director are correctly applied to state.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import Event
from src.module5_events.event_resolver import EventResolver


class TestEventsStateIntegration(unittest.TestCase):
    """Integration tests for Events + State modules."""
    
    def test_event_application_updates_state(self):
        """Test that events properly modify colony state."""
        state = ColonyState()
        initial_oxygen = state.resources["oxygen"]
        
        event = Event("hull_breach", "section_alpha", 0.5, {"oxygen": -25.0}, "Test")
        resolver = EventResolver()
        result = resolver.apply_event(state, event)
        
        # State should be modified
        self.assertLess(state.resources["oxygen"], initial_oxygen)
        self.assertEqual(result["event_applied"], "hull_breach")
        self.assertIn("state_after", result)


if __name__ == "__main__":
    unittest.main()
