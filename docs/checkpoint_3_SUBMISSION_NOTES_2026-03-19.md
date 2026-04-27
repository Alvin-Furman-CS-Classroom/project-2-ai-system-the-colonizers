# Checkpoint 3: Submission Notes

**Date:** March 19, 2026  
**Checkpoint scope:** Module 4 (Game Theory / Director) + Module 5 (Event Application) with end-to-end integration via `src/game_engine.py`.

---

## What to Run

### Automated tests

```bash
python run_tests.py
```

### Engine-only demonstration

```bash
python main.py
```

### Visual demonstration (Pygame)

```bash
python visual_game.py
```

---

## What to Look For (Grading Notes)

- **Module 4 (Game Theory / adversary selection)**
  - An AI Director chooses disruptive events in the adversarial phase using a weakness-aware evaluation policy.
  - Events are represented as explicit `Event` objects with a stable shape (type, target, severity).

- **Module 5 (Event application / state transitions)**
  - The selected event is applied in a centralized resolver that mutates `ColonyState` in controlled, test-backed ways.
  - Station status transitions (e.g., warning → failed) and repairs are handled deterministically.

- **Integration**
  - `GameEngine.execute_turn(...)` demonstrates the multi-module pipeline and returns a structured per-turn report.

---

## Evidence Files

- Code elegance report: `docs/checkpoint_3_CODE_ELEGANCE_REPORT_2026-03-19.md`
- Demo script: `docs/checkpoint_3_DEMO_SCRIPT_2026-03-19.md`

