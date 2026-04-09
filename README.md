# The Colony Manager: AI-Adversarial Survival System

## Overview

The Colony Manager is a turn-based survival simulation where a player manages a group of agents (colonists) in a hostile environment. The system tracks critical resources—Oxygen, Calories, and Integrity—which must remain above zero to keep agents alive. The player assigns tasks to agents, manages resource allocation, and responds to disruptions. The AI acts as an adversarial "Director" that evaluates colony weaknesses and selects disasters (e.g., hull breaches, resource shortages, equipment failures) using game-theoretic decision-making to challenge the player.

Each turn follows four phases: Logic (rule enforcement checking constraints), Planning (task optimization via A* search), Adversarial (AI disaster selection via Minimax), and Resolution (resource consumption and event application). The system uses Propositional Logic to encode survival constraints (e.g., "no oxygen implies agent death") and Search algorithms to optimize task sequencing and logistics planning. The AI Director uses Minimax to evaluate colony states and choose disruptions that maximally challenge current resource vulnerabilities.

This theme naturally integrates multiple AI techniques: state representation for colony management, Search for logistics optimization, Propositional Logic for constraint checking, and Game Theory for adversarial decision-making. The system demonstrates how AI can model both cooperative planning and adversarial dynamics within a unified survival framework.

## Team

- Rick T. (project owner)

## Proposal

See `proposal.md` for the full project proposal.

## Module Plan

| Module | Topic(s) | Inputs | Outputs | Depends On | Checkpoint |
| ------ | -------- | ------ | ------- | ---------- | ---------- |
| 1 | State Representation | Previous turn's colony state (JSON) | Updated colony state after resource consumption | None | Checkpoint 1 (Feb 11) |
| 2 | Search (A*, IDA*, Beam Search) | Player-assigned tasks, colony state, agent capabilities | Optimal task execution sequence | Module 1 | Checkpoint 1-2 (Feb 11-26) |
| 3 | Propositional Logic | Current colony state | Constraint violation report with consequences | Module 1 | Checkpoint 1-2 (Feb 11-26) |
| 4 | Game Theory (Minimax, Alpha-Beta, MCTS) | Colony state, available event types | Selected disaster/event specification | Modules 1-3 | Checkpoint 3 (March 19) |
| 5 | Event Application Logic | Selected event, colony state | Modified colony state after event | Modules 1, 4 | Checkpoint 3-4 (March 19 - April 2) |
| 6 | Reinforcement Learning or Heuristics | Colony state, historical data (optional) | Survival probability score, risk assessment | Modules 1-3 | Checkpoint 4-5 (April 2-16) |

## Repository Layout

```
project-2-ai-system-the-colonizers/
├── src/                                   # main system source code (modules 1–6)
├── unit_tests/                            # unit tests (parallel structure to src/)
├── docs/                                  # checkpoint reports + project docs
├── assets/                                # visual assets for pygame client
├── visual_game.py                         # pygame visual client
├── main.py                                # engine-only demonstration entrypoint
├── run_tests.py                           # unified test runner
├── .claude/skills/code-review/SKILL.md    # rubric-based review skill
├── AGENTS.md                              # agent workflow + module plan
└── README.md                              # system overview and checkpoint log
```

## Setup

### Prerequisites

- Python 3.8 or higher
- No external dependencies required for basic implementation (see `requirements.txt` for optional packages)

### Installation

1. Clone the repository (or download as a zip):
   ```bash
   git clone <your-repo-url>
   cd project-2-ai-system-the-colonizers
   ```

2. (Optional) Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. (Optional) Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running

### Run the engine-only demonstration:
```bash
python main.py
```

This will run a simple demonstration showing the game engine executing several turns with all modules working together.

### Run the Pygame visual client:
```bash
python visual_game.py
```

### Run individual modules:

Each module can be imported and used independently. For example, this snippet
shows the full four-phase flow without the visual UI:

```python
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import Task
from src.module3_logic.rule_engine import RuleEngine
from src.module4_game_theory.ai_director import AIDirector
from src.module5_events.event_resolver import EventResolver
from src.module6_rl.survival_assessor import SurvivalAssessor
from src.game_engine import GameEngine

# Create initial state (normally produced by the previous turn)
state = ColonyState()

# Set up engine (wires modules 1–6 together)
engine = GameEngine(initial_state=state)

# Example: one player task at (0, 0)
tasks = [
    Task(
        task_id=\"task_0_0_0\",
        location=(0, 0),
        requirements={},
        priority=5,
        estimated_duration=1,
    )
]

# Execute a single turn through Logic → Planning → Adversarial → Resolution
turn_report = engine.execute_turn(player_tasks=tasks, algorithm=\"astar\")

print(\"Turn:\", turn_report[\"turn_number\"])
print(\"Logic phase:\", turn_report[\"phases\"][\"logic\"])
print(\"Planning phase:\", turn_report[\"phases\"][\"planning\"])
print(\"Adversarial phase:\", turn_report[\"phases\"][\"adversarial\"])
print(\"Resolution phase:\", turn_report[\"phases\"][\"resolution\"])
print(\"Survival assessment:\", turn_report[\"survival_assessment\"])
```

## Testing

**Unit Tests** (`unit_tests/`): Mirror the structure of `src/`. Each module has corresponding unit tests.

**Integration Tests** (`integration_tests/`): Each module beyond the first has a subfolder demonstrating how modules work together.

### Run all tests:
```bash
python run_tests.py
```

### Run specific test file:
```bash
python -m unittest unit_tests.test_module1_state
python -m unittest integration_tests.module2_search.test_search_with_state
```

### Run with verbose output:
```bash
python -m unittest discover -v
```

## Checkpoint Log

| Checkpoint | Date | Modules Included | Status | Evidence |
| ---------- | ---- | ---------------- | ------ | -------- |
| 1 | Feb 11 | Module 1 (State), Module 2 (Search), Module 3 (Logic) | Ready | `docs/checkpoint_1_elegance_report.md`; `python run_tests.py` (116/116 as of 2026-04-09) |
| 2 | Feb 26 | Module 2 (Search), Module 3 (Logic) | Ready | `docs/checkpoint_2_CODE_ELEGANCE_REPORT_2026-02-26.md`; `python run_tests.py` (116/116 as of 2026-04-09) |
| 3 | March 19 | Module 4 (Game Theory), Module 5 (Events) | Ready | `docs/checkpoint_3_CODE_ELEGANCE_REPORT_2026-03-19.md`; `docs/checkpoint_3_SUBMISSION_NOTES_2026-03-19.md`; `docs/checkpoint_3_DEMO_SCRIPT_2026-03-19.md`; `python run_tests.py` (116/116 as of 2026-04-09) |
| 4 | April 2 | Module 5 (Events), Module 6 (RL/Heuristics) | Ready | `docs/checkpoint_4_CODE_ELEGANCE_REPORT_2026-04-02.md`; `python run_tests.py` (116/116 as of 2026-04-09) |
| 5 | April 16 | Module 6 (RL/Heuristics) | Ready | `docs/checkpoint_5_CODE_ELEGANCE_AND_MODULE_REPORT_2026-04-09.md`; `python run_tests.py` (116/116 as of 2026-04-09) |

### Docs

- Docs index: `docs/README.md`
- Full-project report: `docs/PROJECT_CODE_ELEGANCE_AND_MODULE_REPORT_2026-04-09.md`

## Required Workflow (Agent-Guided)

Before each module:

1. Write a short module spec in this README (inputs, outputs, dependencies, tests).
2. Ask the agent to propose a plan in "Plan" mode.
3. Review and edit the plan. You must understand and approve the approach.
4. Implement the module in `src/`.
5. Unit test the module, placing tests in `unit_tests/` (parallel structure to `src/`).
6. For modules beyond the first, add integration tests in `integration_tests/` (new subfolder per module).
7. Run a rubric review using the code-review skill at `.claude/skills/code-review/SKILL.md`.

Keep `AGENTS.md` updated with your module plan, constraints, and links to APIs/data sources.

## References

### Course Materials
- Project Instructions: https://csc-343.path.app/projects/project-2-ai-system/ai-system.project.md
- Code elegance rubric: https://csc-343.path.app/rubrics/code-elegance.rubric.md
- Course schedule: https://csc-343.path.app/resources/course.schedule.md
- Rubric: https://csc-343.path.app/projects/project-2-ai-system/ai-system.rubric.md

### Libraries (Optional)
- `networkx`: For graph-based search algorithms
- `numpy`: For numerical computations in RL
- `pytest`: Alternative testing framework

### Data Format
- Game state is stored in JSON format
- See `src/module1_state/colony_state.py` for state structure
 
