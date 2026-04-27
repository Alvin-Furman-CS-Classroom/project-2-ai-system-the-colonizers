# Full Project: Code Elegance + Module Report (Modules 1–6)

**Date:** April 9, 2026  
**System title:** The Colony Manager (AI-Adversarial Survival System)  
**External rubrics:** [Code elegance](https://csc-343.path.app/rubrics/code-elegance.rubric.md), [AI System](https://csc-343.path.app/projects/project-2-ai-system/ai-system.rubric.md).

---

## Executive Summary

This document is a project-wide, module-by-module report covering **all six course topics** implemented in the system, with an emphasis on **code elegance**, **clear inputs/outputs**, and **test evidence**.

**Test evidence:** `python run_tests.py` → **118 tests, 0 failures** (run on Apr 15, 2026).

---

## Architecture Overview

### Core dependency direction

- `module1_state` defines the canonical state (`ColonyState`) used everywhere.
- `module2_search`, `module3_logic`, `module4_game_theory`, `module5_events`, and `module6_rl` consume and/or mutate `ColonyState` through clearly defined APIs.
- `GameEngine` wires the modules into a deterministic turn cycle and returns structured per-turn reports.
- `visual_game.py` is a Pygame front-end that drives the engine/state for demonstrations, while keeping core logic testable without UI.

### Turn-cycle (system pipeline)

1. **Logic** (Module 3)
2. **Planning / Search** (Module 2)
3. **Adversarial selection** (Module 4)
4. **Resolution / Event application** (Module 5)
5. **Assessment** (Module 6)

---

## Module-by-Module Report

## Module 1 — State Representation

### Responsibilities

- Defines `ColonyState`: agents, resources, world seed/bounds, infrastructure, tasks, and cross-floor metadata.
- Supports serialization/deserialization and validation.

### Inputs / Outputs

- **Inputs:** prior turn state (in-memory or JSON)
- **Outputs:** updated state (in-memory) + JSON-compatible dict/string forms

### Elegance highlights

- Central “single source of truth” state object reduces ad-hoc globals.
- Validation routines prevent invalid game states (duplicate IDs, collisions, missing required fields).

### Test evidence

- Broad unit test coverage for add/update/remove operations, validation, serialization, and edge cases (e.g., null lists in JSON).

---

## Module 2 — Search (A\*, IDA\*, Beam)

### Responsibilities

- Implements graph-based pathfinding and task planning via `TaskPlanner`.
- Uses multiple algorithms and exposes selection via configuration/UI.

### Inputs / Outputs

- **Inputs:** `ColonyState`, agent locations, tasks (goals)
- **Outputs:** routes/plans with costs and assignments

### Elegance highlights

- Algorithms are kept in dedicated methods; shared helpers are factored for readability.
- Tests ensure correctness across algorithms and special cases.

---

## Module 3 — Propositional Logic

### Responsibilities

- Encodes survival constraints as rules, detects violations, applies consequences.

### Inputs / Outputs

- **Inputs:** `ColonyState`
- **Outputs:** violation report + state mutations (e.g., marking agents dead)

### Elegance highlights

- Rules are explicit and test-driven.
- Consequence application remains readable and deterministic.

---

## Module 4 — Game Theory / Adversarial Director

### Responsibilities

- Selects adversarial events to challenge the colony.
- Supports constraint-based selection (e.g., affordability, cooldowns) and an optional RL bias to adapt event preferences.

### Inputs / Outputs

- **Inputs:** `ColonyState`, available event templates
- **Outputs:** selected `Event` object (or “no event”)

### Elegance highlights

- Events are represented as dataclasses with explicit fields (including cost/cooldowns).
- Constraint filtering prevents “free” or spammy disasters and improves fairness/readability.

---

## Module 5 — Event Application Logic (State Transitions)

### Responsibilities

- Applies events to the state via `EventResolver`, returning a structured resolution report.

### Inputs / Outputs

- **Inputs:** `ColonyState`, `Event`
- **Outputs:** mutated `ColonyState` + report dict describing effects

### Elegance highlights

- Centralized event application avoids scattering state mutations across the codebase.
- Targeted agent hazards are handled explicitly and tested to avoid unintended global side effects.

---

## Module 6 — RL / Heuristics

### Responsibilities

- Produces survival/risk assessment for the colony and provides RL-ready discretization and learning hooks.
- Provides **persistent** tabular policies (saved/loaded) so learning occurs across floors and across runs.

### Inputs / Outputs

- **Inputs:** `ColonyState` (+ optional learning signals / prior state)
- **Outputs:** assessment dict and/or updated policy tables (tabular)

### Elegance highlights

- RL components are bounded and readable (tabular Q-learning with discretization).
- Heuristic fallback keeps the system interpretable and robust.

### RL defense (why this qualifies as reinforcement learning)

- **Policy representation**: tabular \(Q(s,a)\) over a discrete state space derived from the game’s real state object.
- **Experience**: the engine produces real transitions \((s,a,r,s')\) during play; both the survival assessor and the disaster-purchasing Director update their Q-tables online.
- **Objective**:
  - Survival assessor learns value under realized pressure (used as a bounded survival estimate with safety caps).
  - Director learns which disaster “purchases” are most effective against the colony given budget constraints and observed outcomes.
- **Persistence**: learned tables are stored in `.rl_cache/*.json`, so the system improves floor-to-floor and run-to-run rather than resetting each session.

---

## Documentation & Discoverability

- Checkpoint reports are stored in `docs/` with consistent naming.
- A docs index exists at `docs/README.md` that links checkpoint 1–5 reports and the full project report.

---

## Known Non-Blocking Improvements (future polish)

- `visual_game.py` can be split into smaller UI modules (rendering/input/state sync) if continued iteration increases file size.
- Director learning can be expanded beyond tabular discretization; current version is intentionally simple for clarity and rubric alignment.

