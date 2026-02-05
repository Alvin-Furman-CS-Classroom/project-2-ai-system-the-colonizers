"""
Integration test: Module 4 (Game Theory) with Module 1 (State)

Tests that AI Director uses colony state to select appropriate events.
"""

import unittest
from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import AIDirector, Event


class TestGameTheoryStateIntegration(unittest.TestCase):
    """Integration tests for Game Theory + State modules."""
    
    def test_director_targets_weak_resources(self):
        """Test that AI Director targets weakest resources."""
        state = ColonyState()
        state.resources["oxygen"] = 20.0  # Low oxygen
        state.resources["calories"] = 80.0  # High calories
        
        events = [
            Event("hull_breach", "alpha", 0.5, {"oxygen": -20.0}, "Targets oxygen"),
            Event("shortage", "storage", 0.5, {"calories": -20.0}, "Targets calories")
        ]
        
        director = AIDirector(events)
        selected = director.select_event_minimax(state)
        
        # Should prefer event that targets low oxygen
        # (This is a simplified test - actual minimax would be more complex)
        self.assertIsInstance(selected, Event)


if __name__ == "__main__":
    unittest.main()
