# Part A — Module 6 status briefing (pre–multi-floor work)

**Repository:** project-2-ai-system-the-colonizers (The Colony Manager).  
**Course alignment:** `README.md` and `AGENTS.md` place Module 6 (Reinforcement Learning / Heuristics) at **Checkpoint 4–5 (April 2–16)**.

## What Module 6 does today

- **Purpose:** Turn a `ColonyState` into a **survival assessment** (probability-like score, critical threats, optional time-to-failure, discrete state id) for dashboards and turn reports.
- **Main types (`src/module6_rl/`):**
  - `SurvivalAssessor` — `use_rl=False` uses weighted heuristics over colony pools + agent count; `use_rl=True` uses **tabular Q-learning** (`TabularQAgent`) with offline training on a surrogate MDP (`q_learning.train_tabular_q` / `apply_pressure_step`). Unseen Q-states fall back to heuristics. A **vitals cap** blends in weakest colonist oxygen/calories so pool-only discretization cannot report “safe” when a colonist is starving.
  - `discretize_colony_state` — maps pooled O₂/calories/integrity into buckets plus living-agent count (extended in Part B for multi-floor indices).
- **Rubric I/O (Module row):** **Input:** colony state (+ optional history via summaries in state after Part B). **Output:** survival / risk assessment (and interpretable metrics in the returned dict).

## GameEngine wiring

- `GameEngine` constructs `SurvivalAssessor`, optionally runs offline `train_q_learning` at startup, and calls `assess_survival(self.state)` after each `execute_turn`, attaching the result to `turn_report["survival_assessment"]`.

## Tests

- **Unit:** `unit_tests/test_module6_rl.py` — heuristics, vitals cap, injected Q-values, one-step Q backup, short training smoke.
- **Integration:** `integration_tests/module6_rl/test_rl_with_state.py` — assessment reacts to depleted state.

## Coverage gap vs multi-floor (before Part B)

- No explicit tests for **floor index** or **cross-floor stress** in the discretization (addressed in Part B).
- Offline RL still trains on the **pressure MDP**, not full Director + events; multi-floor **summaries** document prior-floor difficulty for assessment and knob derivation, not a full end-to-end simulator.
