"""
Cost-based adversarial director (budget "shop") with simple tabular Q-learning policy.

This intentionally mirrors Module 6's RL style: discrete state → tabular Q over a small
action set. At runtime, the director chooses an event "kind" to buy subject to budget
constraints; the core engine still applies the purchased event via EventResolver.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import random

from src.module1_state.colony_state import ColonyState
from src.module4_game_theory.ai_director import Event
from src.module6_rl.q_learning import bucket_resource


Action = str

# Small, stable action set (buy a category or save points).
ACTION_SAVE: Action = "save"
ACTION_AGENT_OXYGEN: Action = "agent_oxygen"
ACTION_AGENT_CALORIES: Action = "agent_calories"
ACTION_AGENT_INTEGRITY: Action = "agent_integrity"
ACTION_STATION_BREAKDOWN: Action = "station_breakdown"

STANDARD_ACTIONS: Tuple[Action, ...] = (
    ACTION_SAVE,
    ACTION_AGENT_OXYGEN,
    ACTION_AGENT_CALORIES,
    ACTION_AGENT_INTEGRITY,
    ACTION_STATION_BREAKDOWN,
)


def _count_station_status(state: ColonyState) -> Tuple[int, int]:
    """Return (warning_count, failed_count) for resource stations only."""
    warn = 0
    failed = 0
    infra = state.infrastructure or {}
    for _sid, info in infra.items():
        if not isinstance(info, dict):
            continue
        if info.get("kind") != "resource_station":
            continue
        st = info.get("status")
        if st == "warning":
            warn += 1
        elif st == "failed":
            failed += 1
    return warn, failed


def discretize_director_state(state: ColonyState) -> int:
    """
    Compact director state id.

    Axes:
      - buckets for colony pool oxygen/calories/integrity (4^3)
      - living agent bucket (0..5)
      - station warning bucket (0..2) and failed bucket (0..2)
      - budget bucket (0..3)
      - floor bucket (0..3)
    """
    r = state.resources or {}
    o = bucket_resource(float(r.get("oxygen", 0.0)))
    c = bucket_resource(float(r.get("calories", 0.0)))
    i = bucket_resource(float(r.get("integrity", 0.0)))
    alive = sum(1 for a in state.agents if a.get("status") != "dead")
    a = min(alive, 5)
    warn, failed = _count_station_status(state)
    w = min(warn, 2)
    f = min(failed, 2)
    pts = float(getattr(state, "director_points", 0.0) or 0.0)
    budget_bucket = 0 if pts < 2.0 else 1 if pts < 4.0 else 2 if pts < 7.0 else 3
    fi = max(1, int(getattr(state, "floor_index", 1)))
    floor_bucket = min(fi, 4) - 1

    base = o + 4 * (c + 4 * (i + 4 * a))
    station = w + 3 * f
    meta = station + 9 * (budget_bucket + 4 * floor_bucket)
    return base + 384 * meta


@dataclass
class TabularDirectorQ:
    learning_rate: float = 0.15
    discount_factor: float = 0.92
    q: Dict[int, Dict[Action, float]] = None

    def __post_init__(self) -> None:
        if self.q is None:
            self.q = {}

    def _ensure(self, sid: int) -> Dict[Action, float]:
        row = self.q.get(sid)
        if row is None:
            row = {a: 0.0 for a in STANDARD_ACTIONS}
            self.q[sid] = row
        return row

    def best_action(self, sid: int, allowed: List[Action]) -> Action:
        row = self._ensure(sid)
        best = allowed[0]
        best_v = float("-inf")
        for a in allowed:
            v = float(row.get(a, 0.0))
            if v > best_v:
                best_v = v
                best = a
        return best

    def update(self, s: int, a: Action, r: float, s2: int) -> None:
        row = self._ensure(s)
        nxt = self._ensure(s2)
        max_next = max(float(nxt.get(ax, 0.0)) for ax in STANDARD_ACTIONS)
        old = float(row.get(a, 0.0))
        row[a] = old + self.learning_rate * (r + self.discount_factor * max_next - old)

    def to_jsonable(self) -> Dict[str, Any]:
        q_out: Dict[str, Dict[str, float]] = {}
        for sid, row in (self.q or {}).items():
            q_out[str(int(sid))] = {str(a): float(v) for a, v in (row or {}).items()}
        return {
            "version": 1,
            "learning_rate": float(self.learning_rate),
            "discount_factor": float(self.discount_factor),
            "q": q_out,
        }

    def load_jsonable(self, payload: Dict[str, Any], *, merge: bool = True) -> None:
        if not isinstance(payload, dict):
            return
        q_in = payload.get("q")
        if not isinstance(q_in, dict):
            return
        if self.q is None or not merge:
            self.q = {}
        for sid_s, row in q_in.items():
            try:
                sid = int(sid_s)
            except (TypeError, ValueError):
                continue
            if not isinstance(row, dict):
                continue
            dst = self._ensure(sid)
            for a, v in row.items():
                try:
                    dst[str(a)] = float(v)
                except (TypeError, ValueError):
                    continue

    def save_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_jsonable(), f, indent=2, sort_keys=True)

    def try_load_json(self, path: str, *, merge: bool = True) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.load_jsonable(payload, merge=merge)
            return True
        except Exception:
            return False


def reward_from_event_effects(resolution_report: Dict[str, object]) -> float:
    """
    Turn report → bounded reward for the Director.

    Prefers events that cause concrete harm (resource drops, station warnings/fails, deaths).
    """
    r = 0.0
    # Resource impact magnitude
    changes = resolution_report.get("resource_changes") or {}
    if isinstance(changes, dict):
        for _k, v in changes.items():
            try:
                dv = float(v)
            except (TypeError, ValueError):
                continue
            if dv < 0:
                r += min(3.0, abs(dv) / 15.0)
    # Station breakdown progression
    specific = resolution_report.get("specific_effects") or {}
    if isinstance(specific, dict):
        status = specific.get("status")
        if status == "warning":
            r += 0.8
        elif status == "failed":
            r += 1.6
    # Deaths
    if isinstance(resolution_report.get("state_after"), dict):
        agents = resolution_report["state_after"].get("agents") or []
        if isinstance(agents, list):
            dead = sum(1 for a in agents if isinstance(a, dict) and a.get("status") == "dead")
            r += min(3.0, 1.5 * dead)
    # Clamp reward
    return max(-2.0, min(6.0, r))


class BudgetRLDirector:
    """
    Wraps an existing candidate generator by selecting which "kind" to buy via Q-learning.
    """

    def __init__(
        self,
        *,
        epsilon: float = 0.05,
        seed: int = 42,
        persist_path: Optional[str] = None,
    ):
        self.epsilon = float(epsilon)
        self.rng = random.Random(int(seed))
        self.q = TabularDirectorQ()
        self.persist_path = persist_path
        if self.persist_path:
            self.q.try_load_json(self.persist_path, merge=True)

    def _allowed_actions(self, state: ColonyState, affordable_points: float) -> List[Action]:
        # Always allow save.
        allowed = [ACTION_SAVE]
        pts = float(affordable_points)
        # Costs must match the catalog for these event kinds.
        if pts >= 2.0:
            allowed.extend([ACTION_AGENT_OXYGEN, ACTION_AGENT_CALORIES, ACTION_AGENT_INTEGRITY])
        if pts >= 6.0:
            allowed.append(ACTION_STATION_BREAKDOWN)
        return allowed

    def choose_action(self, state: ColonyState, affordable_points: float) -> Action:
        sid = discretize_director_state(state)
        allowed = self._allowed_actions(state, affordable_points)
        if len(allowed) == 1:
            return ACTION_SAVE
        if self.rng.random() < self.epsilon:
            return self.rng.choice(allowed)
        return self.q.best_action(sid, allowed)

    def action_to_event_preference(self, action: Action) -> Dict[str, object]:
        """Translate action into a filter preference used by the caller."""
        if action == ACTION_AGENT_OXYGEN:
            return {"event_type": "agent_oxygen_tank_puncture"}
        if action == ACTION_AGENT_CALORIES:
            return {"event_type": "agent_ration_spoilage"}
        if action == ACTION_AGENT_INTEGRITY:
            return {"event_type": "agent_trip_over_rock"}
        if action == ACTION_STATION_BREAKDOWN:
            return {"event_type": "station_breakdown"}
        return {"event_type": None}

    def learn_from_turn(
        self,
        prev_state: ColonyState,
        action: Action,
        resolution_report: Dict[str, object],
        next_state: ColonyState,
    ) -> None:
        r = reward_from_event_effects(resolution_report)
        s = discretize_director_state(prev_state)
        s2 = discretize_director_state(next_state)
        self.q.update(s, action, r, s2)
        self._persist_if_configured()

    def _persist_if_configured(self) -> None:
        if not self.persist_path:
            return
        try:
            self.q.save_json(self.persist_path)
        except Exception:
            pass

