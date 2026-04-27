"""Pure helpers for per-agent movement speed (usable without Pygame)."""


from __future__ import annotations

from typing import Any, Dict, List


def effective_move_multiplier(agent: Dict[str, Any], current_turn: int) -> float:
    """Movement multiplier from agent ``speed`` (permanent; default 1.0). ``current_turn`` unused."""
    _ = current_turn
    return max(0.05, float(agent.get("speed") or 1.0))


def prune_expired_speed_boosts(agents: List[Dict[str, Any]], current_turn: int) -> None:
    """Remove speed boost keys after the inclusive end turn has passed."""
    for a in agents:
        end = a.get("speed_boost_end_turn")
        if end is None:
            continue
        if current_turn > int(end):
            a.pop("speed_boost_end_turn", None)
            a.pop("speed_boost_mult", None)
