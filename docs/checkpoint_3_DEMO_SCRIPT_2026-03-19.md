# Checkpoint 3: Demo Script (Module 4 + Module 5)

**Date:** March 19, 2026  
**Goal:** Provide a short, reliable demo plan that showcases **Module 4 (Game Theory / Director)** selecting disasters and **Module 5 (Event application)** applying those disasters to the colony state.

---

## Quick Demo (Engine-Only)

1. Run:

```bash
python main.py
```

2. Observe per-turn output:
   - **Adversarial Phase** shows the selected event type.
   - **Resolution Phase** shows event application details (location / effects).

This demo is deterministic enough for grading and does not require Pygame.

---

## Visual Demo (Pygame Client)

1. Run:

```bash
python visual_game.py
```

2. Start a new run and let a few turns pass.
3. Watch for:
   - **Disaster popups** describing events (Director selections).
   - **State impact** in the sidebar (resources dropping; station warnings/failures; agent impacts).

---

## Suggested Talking Points (30–60 seconds)

- “The Director selects an event based on the current colony vulnerabilities (Module 4).”
- “The event is represented as a structured object and applied by a centralized resolver (Module 5).”
- “The engine ties modules together in the turn cycle and produces a structured report each turn.”

