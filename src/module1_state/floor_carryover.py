"""
Cross-floor difficulty carryover (Module 6 RL / progression).

Computes a compact summary when a floor ends and deterministic knobs for the next floor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.module1_state.colony_state import ColonyState


def compute_stress_bin(summary: Dict[str, Any]) -> int:
    """
    Map ended-floor summary to 0..3 for RL discretization (higher = rougher prior floor).
    """
    disasters = int(summary.get("disasters_total", 0))
    deaths = int(summary.get("deaths_total", 0))
    avg = float(summary.get("avg_pool_resources", 70.0))
    stress = disasters + 2 * deaths + max(0.0, (80.0 - avg) / 25.0)
    return int(max(0, min(3, round(stress / 3.0))))


def summarize_finished_floor(
    state: ColonyState,
    floor_start_turn: int,
    disasters_total: int,
    deaths_total: int,
    turn_wood_quota_met: Optional[int],
) -> Dict[str, Any]:
    """Compact record stored in prior_floor_summaries."""
    r = state.resources
    avg_pool = (
        float(r.get("oxygen", 0.0)) + float(r.get("calories", 0.0)) + float(r.get("integrity", 0.0))
    ) / 3.0
    return {
        "floor_index": int(getattr(state, "floor_index", 1)),
        "turns_played": max(0, int(state.turn_number) - int(floor_start_turn)),
        "disasters_total": disasters_total,
        "deaths_total": deaths_total,
        "avg_pool_resources": avg_pool,
        "wood_final": float(state.resources.get("wood", 0.0)),
        "wood_quota": float(getattr(state, "wood_quota", 0.0)),
        "turn_wood_quota_met": turn_wood_quota_met,
        "wood_turns_to_quota": (
            None
            if turn_wood_quota_met is None
            else max(0, turn_wood_quota_met - int(floor_start_turn))
        ),
    }


def next_floor_knobs(
    prior_summaries: List[Dict[str, Any]],
    next_floor_index: int,
    difficulty: str,
) -> Dict[str, Any]:
    """
    Deterministic next-floor parameters from history.

    Knobs:
      - tree_density_multiplier: <1 easier scatter, >1 denser (actually inverted below:
        higher stress → fewer trees)
      - wood_quota_adjust: added to base quota (harder floors require more wood)
      - director_aggression_delta: added to normalized aggression in GameEngine
      - extra_repair_turns: added to per-station repair lengths
    """
    stress = 0.0
    if prior_summaries:
        last = prior_summaries[-1]
        stress = (
            0.45 * float(last.get("disasters_total", 0))
            + 0.9 * float(last.get("deaths_total", 0))
            + max(0.0, (75.0 - float(last.get("avg_pool_resources", 75.0))) / 30.0)
        )
    floor_boost = 0.12 * max(0, int(next_floor_index) - 1)
    tree_density_multiplier = max(0.55, 1.15 - 0.04 * stress - floor_boost)
    wood_quota_adjust = 0.5 * stress + 1.0 * floor_boost
    director_aggression_delta = 0.04 * stress + 0.06 * floor_boost
    extra_repair_turns = int(min(3, round(stress / 2.0 + floor_boost * 2.0)))

    d = (difficulty or "normal").lower()
    if d == "hard":
        wood_quota_adjust += 0.5
        director_aggression_delta += 0.03
    elif d == "easy":
        director_aggression_delta -= 0.02
        tree_density_multiplier += 0.08

    return {
        "tree_density_multiplier": float(tree_density_multiplier),
        "wood_quota_adjust": float(wood_quota_adjust),
        "director_aggression_delta": float(director_aggression_delta),
        "extra_repair_turns": int(extra_repair_turns),
    }
