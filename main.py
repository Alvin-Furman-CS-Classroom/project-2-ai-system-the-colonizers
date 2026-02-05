"""
Main entry point for The Colony Manager game.

This script demonstrates the game engine running a few turns.
"""

from src.game_engine import GameEngine
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import Task


def main():
    """Run a simple game demonstration."""
    print("=" * 60)
    print("The Colony Manager: AI-Adversarial Survival System")
    print("=" * 60)
    print()
    
    # Create initial state with some agents
    initial_state = ColonyState()
    success, errors = initial_state.add_agent({
        "id": 0,
        "name": "Agent Alpha",
        "oxygen": 80.0,
        "calories": 70.0,
        "location": (0, 0)
    })
    if not success:
        print(f"Warning: Failed to add agent: {errors}")
    
    success, errors = initial_state.add_agent({
        "id": 1,
        "name": "Agent Beta",
        "oxygen": 90.0,
        "calories": 85.0,
        "location": (5, 5)
    })
    if not success:
        print(f"Warning: Failed to add agent: {errors}")
    
    # Initialize game engine
    game = GameEngine(initial_state)
    
    print("Starting colony state:")
    print(f"  Agents: {len(game.get_state().agents)}")
    print(f"  Oxygen: {game.get_state().resources['oxygen']:.1f}%")
    print(f"  Calories: {game.get_state().resources['calories']:.1f}%")
    print(f"  Integrity: {game.get_state().resources['integrity']:.1f}%")
    print()
    
    # Run a few turns
    max_turns = 5
    for turn in range(max_turns):
        print(f"--- Turn {turn + 1} ---")
        
        # Player assigns some tasks (optional)
        player_tasks = [
            Task("repair_1", (10, 10), {}, priority=1, estimated_duration=2),
            Task("explore_1", (15, 15), {}, priority=2, estimated_duration=3)
        ]
        
        # Execute turn
        turn_report = game.execute_turn(player_tasks)
        
        # Display results
        print(f"Logic Phase: {turn_report['phases']['logic']['violations_found']} violations found")
        print(f"Planning Phase: {turn_report['phases']['planning']['tasks_assigned']} tasks assigned")
        print(f"Adversarial Phase: {turn_report['phases']['adversarial']['event_selected']} event selected")
        print(f"Resolution Phase: Event applied at {turn_report['phases']['resolution']['location']}")
        
        state = game.get_state()
        print(f"Survival Probability: {turn_report['survival_assessment']['survival_probability']:.2%}")
        print(f"Current Resources - O2: {state.resources['oxygen']:.1f}%, "
              f"Cal: {state.resources['calories']:.1f}%, "
              f"Int: {state.resources['integrity']:.1f}%")
        print()
        
        # Check for game over
        if game.is_game_over():
            print("Game Over! Colony has failed.")
            break
    
    print("=" * 60)
    print("Game demonstration complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
