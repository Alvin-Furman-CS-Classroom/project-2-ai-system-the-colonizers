"""
Survival Assessment & Adaptation (Module 6)

Provides survival probability and risk assessment using either:
  - Heuristic scoring over resources and agents, or
  - Standard tabular Q-learning over a discretized state space (see q_learning.py).

Q-learning is trained offline on a simple pressure MDP; at runtime assess_survival
reads max_a Q(s,a) for the discretized state (with heuristic fallback if unseen).

Training uses abstract “pressure” steps on colony clones, not the full four-phase
game loop; the Q-table still summarizes resource and population pressure relevant
to live turns via discretize_colony_state.
"""

from __future__ import annotations

import random
import copy
import os
from typing import Any, Callable, Dict, List, Optional

from src.module1_state.colony_state import ColonyState

from src.module6_rl.q_learning import (
    TabularQAgent,
    colony_is_terminal,
    discretize_colony_state,
    survival_probability_from_max_q,
    train_tabular_q,
)


class SurvivalAssessor:
    """
    Assesses colony survival probability and identifies risks.

    use_rl=False: weighted heuristic (original behavior).
    use_rl=True: values from tabular Q after offline training; unseen states fall back to heuristics.
    """

    def __init__(self, use_rl: bool = False, *, persist_path: Optional[str] = None):
        self.use_rl = bool(use_rl)
        self.heuristic_weights = self._initialize_heuristic_weights()
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.persist_path = persist_path
        self._q_agent = TabularQAgent(
            learning_rate=self.learning_rate,
            discount_factor=self.discount_factor,
        )
        if self.persist_path:
            # Best-effort load; never block gameplay on persistence.
            self._q_agent.try_load_json(self.persist_path, merge=True)

    def _initialize_heuristic_weights(self) -> Dict[str, float]:
        return {
            "oxygen": 0.4,
            "calories": 0.3,
            "integrity": 0.2,
            "agent_count": 0.1,
        }

    def assess_survival(self, colony_state: ColonyState) -> Dict[str, Any]:
        if self.use_rl:
            survival_prob = self._assess_with_q_learning(colony_state)
        else:
            survival_prob = self._assess_with_heuristics(colony_state)

        # Q-learning and the discretization only see colony pool resources, not per-agent
        # vitals (game-over is when colonists starve). Cap so we never show ~90% while
        # someone is about to die from low O2/food.
        vitals_cap = self._vitals_survival_cap(colony_state)
        survival_prob = max(0.0, min(1.0, min(survival_prob, vitals_cap)))

        critical_threats = self._identify_critical_threats(colony_state)
        time_to_failure = self._estimate_time_to_failure(colony_state, survival_prob)

        return {
            "survival_probability": survival_prob,
            "critical_threats": critical_threats,
            "time_to_failure": time_to_failure,
            "assessment_method": "Q-Learning" if self.use_rl else "Heuristic",
            "discrete_state_id": discretize_colony_state(colony_state),
        }

    def _vitals_survival_cap(self, colony_state: ColonyState) -> float:
        """
        Upper bound on believable survival from shared stores and living colonists.

        Uses the weakest link: min(colony resource fractions, worst living agent's min(O2, food)).
        """
        r = colony_state.resources
        colony_frac = min(
            float(r.get("oxygen", 100.0)) / 100.0,
            float(r.get("calories", 100.0)) / 100.0,
            float(r.get("integrity", 100.0)) / 100.0,
        )
        living = [a for a in colony_state.agents if a.get("status") != "dead"]
        if not colony_state.agents:
            # Tests / uninitialized state: no colonists modeled; don't zero the cap.
            return max(0.0, min(1.0, colony_frac))
        if not living:
            return 0.0
        agent_frac = min(
            min(
                float(a.get("oxygen", 100.0)),
                float(a.get("calories", 100.0)),
            )
            / 100.0
            for a in living
        )
        return max(0.0, min(1.0, min(colony_frac, agent_frac)))

    def _assess_with_heuristics(self, colony_state: ColonyState) -> float:
        score = 0.0
        for resource, weight in self.heuristic_weights.items():
            if resource in colony_state.resources:
                level = colony_state.resources[resource]
                normalized = min(1.0, level / 100.0)
                score += weight * normalized
            elif resource == "agent_count":
                agent_count = len(colony_state.agents)
                normalized = min(1.0, agent_count / 5.0)
                score += weight * normalized
        return max(0.0, min(1.0, score))

    def _assess_with_q_learning(self, colony_state: ColonyState) -> float:
        sid = discretize_colony_state(colony_state)
        row = self._q_agent.q.get(sid)
        if not row:
            return self._assess_with_heuristics(colony_state)
        max_q = max(row.values())
        if max_q == 0.0 and all(v == 0.0 for v in row.values()):
            return self._assess_with_heuristics(colony_state)
        return max(0.0, min(1.0, survival_probability_from_max_q(max_q)))

    def _identify_critical_threats(self, colony_state: ColonyState) -> List[str]:
        threats: List[str] = []
        for resource, level in colony_state.resources.items():
            if level < 20.0:
                threats.append(f"{resource}_depletion")
            elif level < 50.0:
                threats.append(f"{resource}_low")
        living = [a for a in colony_state.agents if a.get("status") != "dead"]
        if living:
            for fld, depl, low in (
                ("oxygen", "agent_oxygen_depletion", "agent_oxygen_low"),
                ("calories", "agent_calories_depletion", "agent_calories_low"),
            ):
                worst = min(float(a.get(fld, 100.0)) for a in living)
                if worst < 20.0:
                    threats.append(depl)
                elif worst < 50.0:
                    threats.append(low)
        if len(colony_state.agents) < 2:
            threats.append("insufficient_agents")
        if colony_state.resources.get("integrity", 100.0) < 30.0:
            threats.append("structural_failure_risk")
        return threats

    def _estimate_time_to_failure(
        self, colony_state: ColonyState, survival_prob: float
    ) -> Optional[int]:
        if survival_prob > 0.8:
            return None
        min_turns = float("inf")
        for _resource, level in colony_state.resources.items():
            consumption_rate = 5.0
            if consumption_rate > 0:
                turns_until_zero = level / consumption_rate
                min_turns = min(min_turns, turns_until_zero)
        return int(min_turns) if min_turns != float("inf") else None

    def train_q_learning(
        self,
        episodes: int = 800,
        max_steps_per_episode: int = 12,
        epsilon: float = 0.15,
        seed: int = 42,
        start_state_factory: Optional[Callable[[random.Random], ColonyState]] = None,
    ) -> None:
        """
        Offline training for the Q-table (standard Q-learning backups).

        Updates use the surrogate MDP in q_learning.apply_pressure_step, not a
        full simulation of Module 2–5.

        If use_rl is False, still trains the table so you can switch use_rl on later.
        """
        if start_state_factory is None:
            start_state_factory = self._default_training_start_state

        train_tabular_q(
            self._q_agent,
            episodes=episodes,
            max_steps=max_steps_per_episode,
            epsilon=epsilon,
            seed=seed,
            start_state_factory=start_state_factory,
        )
        self._persist_if_configured()

    def _default_training_start_state(self, rng: random.Random) -> ColonyState:
        """Random but plausible colonies for exploration."""
        o = rng.uniform(35.0, 100.0)
        cal = rng.uniform(35.0, 100.0)
        inte = rng.uniform(35.0, 100.0)
        n_agents = rng.randint(1, 4)
        agents = []
        for i in range(n_agents):
            agents.append(
                {
                    "id": i,
                    "name": f"Train{i}",
                    "location": (0, 0),
                    "oxygen": rng.uniform(50.0, 100.0),
                    "calories": rng.uniform(50.0, 100.0),
                    "integrity": rng.uniform(50.0, 100.0),
                    "status": "active",
                }
            )
        return ColonyState(
            {
                "agents": agents,
                "resources": {"oxygen": o, "calories": cal, "integrity": inte},
                "infrastructure": {},
                "active_tasks": [],
                "turn_number": 0,
                "world_seed": 0,
                "difficulty": "normal",
            }
        )

    def update_rl(
        self, state: ColonyState, action: str, reward: float, next_state: ColonyState
    ) -> None:
        """
        One standard Q-learning update from an external transition
        (s, a, r, s') — e.g. after a real game step.

        Q(s,a) ← Q(s,a) + α [ r + γ max_a' Q(s',a') − Q(s,a) ]
        """
        sid = discretize_colony_state(state)
        s_next_id = discretize_colony_state(next_state)
        terminal = colony_is_terminal(next_state)
        self._q_agent.q_learning_step(sid, action, reward, s_next_id, terminal=terminal)
        self._persist_if_configured()

    def update_from_real_turn(
        self, prev_state: ColonyState, pressure_action: str, next_state: ColonyState
    ) -> None:
        """
        Online learning hook using a real game transition (floor-to-floor and run-to-run).

        The "action" is an abstract pressure label ("mild"|"normal"|"harsh") derived from
        realized adversity intensity; reward is +1 for surviving the step, else -10.
        """
        # Copy to avoid surprises if caller passes references that mutate later.
        s = ColonyState(copy.deepcopy(prev_state.to_dict()))
        s2 = ColonyState(copy.deepcopy(next_state.to_dict()))
        r = -10.0 if colony_is_terminal(s2) else 1.0
        self.update_rl(s, pressure_action, r, s2)

    def _persist_if_configured(self) -> None:
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
            self._q_agent.save_json(self.persist_path)
        except Exception:
            pass
