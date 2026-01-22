# The Colony Manager: AI-Adversarial Survival System

## System Overview

The Colony Manager is a turn-based survival simulation where a player manages a group of agents (colonists) in a hostile environment. The system tracks critical resources—Oxygen, Calories, and Integrity—which must remain above zero to keep agents alive. The player assigns tasks to agents, manages resource allocation, and responds to disruptions. The AI acts as an adversarial "Director" that evaluates colony weaknesses and selects disasters (e.g., hull breaches, resource shortages, equipment failures) using game-theoretic decision-making to challenge the player.

Each turn follows four phases: Logic (rule enforcement checking constraints), Planning (task optimization via A* search), Adversarial (AI disaster selection via Minimax), and Resolution (resource consumption and event application). The system uses Propositional Logic to encode survival constraints (e.g., "no oxygen implies agent death") and Search algorithms to optimize task sequencing and logistics planning. The AI Director uses Minimax to evaluate colony states and choose disruptions that maximally challenge current resource vulnerabilities.

This theme naturally integrates multiple AI techniques: state representation for colony management, Search for logistics optimization, Propositional Logic for constraint checking, and Game Theory for adversarial decision-making. The system demonstrates how AI can model both cooperative planning and adversarial dynamics within a unified survival framework.

## Modules

### Module 1: Colony State Management

**Topics:** State representation

**Input:** Previous turn's colony state (JSON structure containing: agents array with health/resource status, resource levels {oxygen, calories, integrity}, infrastructure state, active tasks)

**Output:** Updated colony state after resource consumption for current turn (same JSON structure with modified values)

**Integration:** Base state representation that all other modules read from and modify. Module 2 uses this for task planning, Module 3 uses it for rule checking, Module 4 uses it for event selection.

**Prerequisites:** None (foundational module, can start immediately)

---

### Module 2: Task Planning & Logistics Optimization

**Topics:** Search (A*, IDA*, Beam Search)

**Input:** Player-assigned tasks (list of tasks with locations/requirements), current colony state from Module 1, agent capabilities (speed, skill levels)

**Output:** Optimal task execution sequence (ordered list of tasks with assigned agents, estimated completion times, resource costs)

**Integration:** Uses colony state from Module 1. Outputs task sequences that affect resource consumption in Module 1's resolution phase.

**Prerequisites:** Module 1, Search algorithms (A*, IDA*, Beam Search) - available by Week 1.5-3

---

### Module 3: Rule Enforcement Engine

**Topics:** Propositional Logic (constraint checking, survival rule inference)

**Input:** Current colony state from Module 1 (resource levels, agent status, infrastructure state)

**Output:** Constraint violation report (list of violated rules with consequences, e.g., {"agent_id": 3, "violation": "oxygen_zero", "consequence": "death", "applied": true})

**Integration:** Evaluates state from Module 1 before other phases. Violations (like agent death) update Module 1's state. Feeds into Module 4's decision-making.

**Prerequisites:** Module 1, Propositional Logic (available by Week 1-1.5)

---

### Module 4: Adversarial Event Selection

**Topics:** Games and Game Theory (Minimax, Alpha-Beta Pruning, MCTS)

**Input:** Current colony state from Module 1 (resource levels, infrastructure vulnerabilities, agent locations), available event types (disaster catalog)

**Output:** Selected disaster/event specification (e.g., {"event_type": "hull_breach", "location": "section_alpha", "severity": 0.7, "resource_impact": {"oxygen": -20}})

**Integration:** Analyzes Module 1 state to identify weaknesses. Uses Minimax/Alpha-Beta to select events that maximally challenge player. Outputs to Module 5 for application.

**Prerequisites:** Modules 1-3, Games and Game Theory (Minimax, Alpha-Beta) - available by Week 5.5-8.5

---

### Module 5: Event Resolution & State Update

**Topics:** Event application logic, state transitions

**Input:** Selected event from Module 4 (event specification with type, location, severity, resource_impact), current colony state from Module 1

**Output:** Modified colony state after event application (JSON structure with: updated resource levels, damaged/affected infrastructure locations, agent status changes from event exposure, cascading effects if applicable)

**Integration:** Receives event specification from Module 4, applies damage calculations and resource deductions to Module 1's state. Handles cascading effects (e.g., hull breach in one section affects adjacent areas). Updated state becomes input for next turn's Module 1 resolution phase.

**Prerequisites:** Modules 1, 4

---

### Module 6: Survival Assessment & Adaptation

**Topics:** Reinforcement Learning (Q-Learning, Value Functions) or Heuristic Evaluation

**Input:** Current colony state from Module 1 (all resources, agent count, infrastructure integrity), historical gameplay data (optional)

**Output:** Survival probability score (float 0.0-1.0), risk assessment report ({"survival_probability": 0.65, "critical_threats": ["oxygen_depletion"], "time_to_failure": 5_turns})

**Integration:** Evaluates Module 1 state to assess overall colony health. Can inform Module 4's event selection (higher survival = more aggressive disruptions). Provides feedback to player.

**Prerequisites:** Modules 1-3, Reinforcement Learning (available by Week 8.5-10) OR can use heuristics if RL seems too complex

---

## Feasibility Study

_A timeline showing that each module's prerequisites align with the course schedule. Verify that you are not planning to implement content before it is taught._

| Module | Required Topic(s) | Topic Covered By | Checkpoint Due |
| ------ | ----------------- | ---------------- | -------------- |
| 1      | State Representation | Week 1 | Checkpoint 1 (Feb 11) |
| 2      | Search (A*, IDA*, Beam Search) | Week 1.5-3 | Checkpoint 1-2 (Feb 11-26) |
| 3      | Propositional Logic | Week 1-1.5 | Checkpoint 1-2 (Feb 11-26) |
| 4      | Game Theory (Minimax, Alpha-Beta, MCTS) | Week 5.5-8.5 | Checkpoint 3 (March 19) |
| 5      | Event Application Logic (state transitions) | After Module 4 | Checkpoint 3-4 (March 19 - April 2) |
| 6      | Reinforcement Learning or Heuristics | Week 8.5-10 | Checkpoint 4-5 (April 2-16) |

## Coverage Rationale

This topic selection fits the Colony Manager theme because survival simulation requires both logical constraint checking (survival rules) and strategic optimization (resource allocation, disaster planning). Search algorithms naturally fit task sequencing and logistics optimization—colonists must efficiently allocate time and resources using A* pathfinding and beam search for multi-agent task assignment. Propositional Logic is essential for encoding survival constraints (e.g., "if oxygen = 0 then agent dies"), ensuring game rules are consistently applied through entailment and chaining. Game Theory (Minimax, Alpha-Beta Pruning, MCTS) fits the adversarial AI Director role, allowing the system to strategically challenge players by evaluating colony vulnerabilities and selecting optimal disruptive events.

Trade-offs considered: Using Reinforcement Learning for Module 6 allows adaptive survival assessment, but could be replaced with heuristic evaluation if RL proves too complex. Focusing on turn-based mechanics simplifies real-time complexity while maintaining strategic depth. The modular design allows progressive implementation where early modules (Logic, Search) can be developed independently before integrating adversarial elements. Prioritizing Search and Logic ensures both required topics are covered early in the project timeline.
