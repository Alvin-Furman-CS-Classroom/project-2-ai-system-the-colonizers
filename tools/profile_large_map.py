"""
Profile pathfinding / turn on a ~250×250-style world (run from repo root).

  python tools/profile_large_map.py

Outputs cumulative time ranking (stdlib cProfile). Use this to verify hotspots
before/after optimization work.
"""

from __future__ import annotations

import cProfile
import pstats
import io
import sys
from pathlib import Path

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.module1_state.colony_state import ColonyState
from src.game_engine import GameEngine


def main() -> None:
    half = 125
    state = ColonyState(
        {
            "world_seed": 424242,
            "difficulty": "normal",
            "floor_index": 1,
            "world_min_x": -half,
            "world_max_x": half,
            "world_min_y": -half,
            "world_max_y": half,
            "resources": {
                "oxygen": 90.0,
                "calories": 90.0,
                "integrity": 90.0,
                "wood": 0.0,
            },
            "infrastructure": {},
            "active_tasks": [],
        }
    )
    state.add_agent(
        {
            "id": 0,
            "name": "P",
            "location": (-10, -10),
            "oxygen": 80.0,
            "calories": 70.0,
            "integrity": 90.0,
            "status": "active",
        },
        validate=False,
    )
    eng = GameEngine(state, survival_use_rl=False)
    eng.warm_terrain_cache()

    pr = cProfile.Profile()
    pr.enable()
    # Grid already warm — measures mostly A* + heap, not full-map terrain build
    eng.get_path_for_agent_to_location(0, 100, 100)
    eng.get_path_for_agent_to_location(0, -80, 80)
    for _ in range(8):
        eng.get_path_for_agent_to_location(0, 50, -60)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(25)
    print(s.getvalue())


if __name__ == "__main__":
    main()
