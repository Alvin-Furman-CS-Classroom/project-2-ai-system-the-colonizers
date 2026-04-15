"""
Standard tabular Q-learning (off-policy).

Update rule:
    Q(s,a) ← Q(s,a) + α [ r + γ max_a' Q(s',a') − Q(s,a) ]

State space is a discretized summary of ColonyState; action space is a small
set of abstract "environment pressure" levels used for training simulation.
"""

from __future__ import annotations

import copy
import json
import math
import os
import random
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, Tuple

from src.module1_state.colony_state import ColonyState

# Abstract actions: higher pressure → larger resource drain in the training simulator.
STANDARD_ACTIONS: Tuple[str, ...] = ("mild", "normal", "harsh")

_DRAIN_BY_ACTION = {"mild": 2.0, "normal": 5.0, "harsh": 9.0}

# Base discretization: 4^3 * 6 living-agent buckets = 384.
_BASE_STATE_COUNT = 384


def bucket_resource(level: float) -> int:
    """Four bins for each global resource (0 critical … 3 comfortable)."""
    if level < 20.0:
        return 0
    if level < 50.0:
        return 1
    if level < 80.0:
        return 2
    return 3


def discretize_colony_state(state: ColonyState) -> int:
    """
    Map colony state to an integer id for the Q-table.

    Axes: oxygen, calories, integrity buckets (4 each), living-agent count capped at 5,
    floor depth bucket (4), prior-floor stress bin from multi-floor carryover (4).
    Total states: 384 * 16 = 6144.
    """
    r = state.resources
    o = bucket_resource(float(r.get("oxygen", 0.0)))
    c = bucket_resource(float(r.get("calories", 0.0)))
    i = bucket_resource(float(r.get("integrity", 0.0)))
    alive = 0
    for a in state.agents:
        if a.get("status") != "dead":
            alive += 1
    ac = min(alive, 5)
    base = o + 4 * (c + 4 * (i + 4 * ac))
    fi = max(1, int(getattr(state, "floor_index", 1)))
    floor_bucket = min(fi, 4) - 1  # 0..3 for floors 1–4+
    stress = int(getattr(state, "rl_carryover_stress_bin", 0))
    stress_bin = max(0, min(3, stress))
    meta = floor_bucket + 4 * stress_bin
    return base + _BASE_STATE_COUNT * meta


def colony_is_terminal(state: ColonyState) -> bool:
    """Episode ends if any core resource hits zero or any agent is dead."""
    for k in ("oxygen", "calories", "integrity"):
        v = state.resources.get(k, 100.0)
        if float(v) <= 0.0:
            return True
    for a in state.agents:
        if a.get("status") == "dead":
            return True
        if float(a.get("oxygen", 100.0)) <= 0.0:
            return True
        if float(a.get("calories", 100.0)) <= 0.0:
            return True
    return False


def transition_reward(_prev: ColonyState, nxt: ColonyState) -> float:
    """+1 per step alive; large penalty when colony fails after the step."""
    if colony_is_terminal(nxt):
        return -10.0
    return 1.0


def apply_pressure_step(state: ColonyState, action: str, rng: random.Random) -> ColonyState:
    """
    Copy state and apply one abstract pressure step (training-only dynamics).
    Drain scales with action: mild < normal < harsh.
    """
    if action not in _DRAIN_BY_ACTION:
        action = "normal"
    pressure = _DRAIN_BY_ACTION[action]
    data = copy.deepcopy(state.to_dict())
    new_state = ColonyState(data)
    u = rng.uniform
    for key in new_state.resources:
        if key == "wood":
            continue
        new_state.resources[key] = max(
            0.0, float(new_state.resources[key]) - pressure * u(0.3, 1.0)
        )
    for agent in new_state.agents:
        if agent.get("status") == "dead":
            continue
        for fld in ("oxygen", "calories", "integrity"):
            if fld in agent:
                agent[fld] = max(
                    0.0, float(agent[fld]) - pressure * 0.25 * u(0.3, 1.0)
                )
        if float(agent.get("oxygen", 1.0)) <= 0.0 or float(agent.get("calories", 1.0)) <= 0.0:
            agent["status"] = "dead"
    return new_state


class TabularQAgent:
    """Tabular Q-learning with fixed discrete actions."""

    def __init__(
        self,
        actions: Iterable[str] = STANDARD_ACTIONS,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
    ):
        self.actions: Tuple[str, ...] = tuple(actions)
        self.alpha = float(learning_rate)
        self.gamma = float(discount_factor)
        # Q[state_id][action] = value
        self.q: Dict[int, Dict[str, float]] = defaultdict(dict)

    def q_sa(self, state_id: int, action: str) -> float:
        return float(self.q[state_id].get(action, 0.0))

    def max_over_actions(self, state_id: int) -> float:
        row = self.q[state_id]
        if not row:
            return 0.0
        return max(row.values())

    def best_action(self, state_id: int) -> str:
        """Break ties lexicographically on action name for determinism."""
        best_a = self.actions[0]
        best_v = self.q_sa(state_id, best_a)
        for a in self.actions[1:]:
            v = self.q_sa(state_id, a)
            if v > best_v:
                best_v = v
                best_a = a
        return best_a

    def q_learning_step(
        self,
        state_id: int,
        action: str,
        reward: float,
        next_state_id: int,
        terminal: bool = False,
    ) -> None:
        """
        Standard Q-learning backup. If terminal, max_a' Q(s',a') is 0.
        """
        current = self.q_sa(state_id, action)
        max_next = 0.0 if terminal else self.max_over_actions(next_state_id)
        target = float(reward) + self.gamma * max_next
        self.q[state_id][action] = current + self.alpha * (target - current)

    def epsilon_greedy(
        self, state_id: int, epsilon: float, rng: random.Random
    ) -> str:
        if rng.random() < epsilon:
            return rng.choice(self.actions)
        return self.best_action(state_id)

    def max_value_state(self, state_id: int) -> float:
        """max_a Q(s,a); 0 if unseen."""
        return self.max_over_actions(state_id)

    def to_jsonable(self) -> Dict[str, Any]:
        """
        Return a JSON-serializable snapshot of this agent's Q-table.
        Keys are converted to strings for JSON compatibility.
        """
        q_out: Dict[str, Dict[str, float]] = {}
        for sid, row in self.q.items():
            q_out[str(int(sid))] = {str(a): float(v) for a, v in (row or {}).items()}
        return {
            "version": 1,
            "actions": list(self.actions),
            "alpha": float(self.alpha),
            "gamma": float(self.gamma),
            "q": q_out,
        }

    def load_jsonable(self, payload: Dict[str, Any], *, merge: bool = True) -> None:
        """
        Load Q-table from a JSONable dict created by to_jsonable.
        If merge=True, merges into existing table; otherwise replaces.
        """
        if not isinstance(payload, dict):
            return
        q_in = payload.get("q")
        if not isinstance(q_in, dict):
            return
        if not merge:
            self.q = defaultdict(dict)
        for sid_s, row in q_in.items():
            try:
                sid = int(sid_s)
            except (TypeError, ValueError):
                continue
            if not isinstance(row, dict):
                continue
            dst = self.q[sid]
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


def survival_probability_from_max_q(max_q: float) -> float:
    """Map best-action value to (0,1) for reporting (logistic)."""
    if max_q == 0.0:
        return 0.5
    return 1.0 / (1.0 + math.exp(-max_q))


def train_tabular_q(
    agent: TabularQAgent,
    episodes: int,
    max_steps: int,
    epsilon: float,
    seed: int,
    start_state_factory: Callable[[random.Random], ColonyState],
) -> None:
    """
    Run offline Q-learning over the abstract pressure MDP.
    Mutates agent.q in place.
    """
    rng = random.Random(seed)
    for _ in range(episodes):
        state = start_state_factory(rng)
        for _step in range(max_steps):
            if colony_is_terminal(state):
                break
            s_id = discretize_colony_state(state)
            a = agent.epsilon_greedy(s_id, epsilon, rng)
            nxt = apply_pressure_step(state, a, rng)
            r = transition_reward(state, nxt)
            terminal = colony_is_terminal(nxt)
            s_next_id = discretize_colony_state(nxt)
            agent.q_learning_step(s_id, a, r, s_next_id, terminal=terminal)
            state = nxt
