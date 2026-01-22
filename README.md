# The Colony Manager: AI-Adversarial Survival System

## Overview

The Colony Manager is a turn-based survival simulation where a player manages a group of agents (colonists) in a hostile environment. The system tracks critical resources—Oxygen, Calories, and Integrity—which must remain above zero to keep agents alive. The player assigns tasks to agents, manages resource allocation, and responds to disruptions. The AI acts as an adversarial "Director" that evaluates colony weaknesses and selects disasters (e.g., hull breaches, resource shortages, equipment failures) using game-theoretic decision-making to challenge the player.

Each turn follows four phases: Logic (rule enforcement checking constraints), Planning (task optimization via A* search), Adversarial (AI disaster selection via Minimax), and Resolution (resource consumption and event application). The system uses Propositional Logic to encode survival constraints (e.g., "no oxygen implies agent death") and Search algorithms to optimize task sequencing and logistics planning. The AI Director uses Minimax to evaluate colony states and choose disruptions that maximally challenge current resource vulnerabilities.

This theme naturally integrates multiple AI techniques: state representation for colony management, Search for logistics optimization, Propositional Logic for constraint checking, and Game Theory for adversarial decision-making. The system demonstrates how AI can model both cooperative planning and adversarial dynamics within a unified survival framework.

## Team

- Adam Alvarado
- Rick King

## Proposal

(https://github.com/Alvin-Furman-CS-Classroom/project-1-proposal-alvaad4)

## Module Plan

Your system must include 5-6 modules. Fill in the table below as you plan each module.

| Module | Required Topic(s) | Topic Covered By | Checkpoint Due |
| ------ | ----------------- | ---------------- | -------------- |
| 1      | State Representation | Week 1 | Checkpoint 1 (Feb 11) |
| 2      | Search (A*, IDA*, Beam Search) | Week 1.5-3 | Checkpoint 1-2 (Feb 11-26) |
| 3      | Propositional Logic | Week 1-1.5 | Checkpoint 1-2 (Feb 11-26) |
| 4      | Game Theory (Minimax, Alpha-Beta, MCTS) | Week 5.5-8.5 | Checkpoint 3 (March 19) |
| 5      | Event Application Logic (state transitions) | After Module 4 | Checkpoint 3-4 (March 19 - April 2) |
| 6      | Reinforcement Learning or Heuristics | Week 8.5-10 | Checkpoint 4-5 (April 2-16) |

## Repository Layout

```
your-repo/
├── src/                              # main system source code
├── unit_tests/                       # unit tests (parallel structure to src/)
├── integration_tests/                # integration tests (new folder for each module)
├── .claude/skills/code-review/SKILL.md  # rubric-based agent review
├── AGENTS.md                         # instructions for your LLM agent
└── README.md                         # system overview and checkpoints
```

## Setup

List dependencies, setup steps, and any environment variables required to run the system.

## Running

Provide commands or scripts for running modules and demos.

## Testing

**Unit Tests** (`unit_tests/`): Mirror the structure of `src/`. Each module should have corresponding unit tests.

**Integration Tests** (`integration_tests/`): Create a new subfolder for each module beyond the first, demonstrating how modules work together.

Provide commands to run tests and describe any test data needed.

## Checkpoint Log

| Checkpoint | Date | Modules Included | Status | Evidence |
| ---------- | ---- | ---------------- | ------ | -------- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |

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

List libraries, APIs, datasets, and other references used by the system.
