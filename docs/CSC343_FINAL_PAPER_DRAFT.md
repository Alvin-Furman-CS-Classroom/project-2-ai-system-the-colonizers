# The Colony Manager: AI-Adversarial Survival System
**Team Members:** Adam Alvarado, Rick King  
**Repository Link:** [INSERT REPO URL]  
**Demo Link:** [INSERT DEMO URL]

---

## Abstract
The Colony Manager is a turn-based survival simulation that combines cooperative planning with adversarial AI pressure. The player manages colonists whose survival depends on oxygen, calories, and integrity, while an AI Director selects disruptive events designed to exploit colony weaknesses. Our final system integrates six course-aligned modules into one executable pipeline: state representation, search, propositional logic, game theory, event application logic, and reinforcement learning/heuristics. A shared `ColonyState` object serves as the canonical world model, and `GameEngine` executes a deterministic turn cycle: Logic, Planning, Adversarial Selection, Resolution, and Assessment. Search planning supports A*, IDA*, and Beam Search. Rule evaluation enforces survival constraints and applies consequences. The Director uses adversarial evaluation with budget and cooldown constraints for fairness. Event resolution applies state transitions through centralized handlers, and a survival assessor outputs risk estimates with tabular Q-learning support and persistent policy caches.  
Evaluation focused on correctness and integration. Unit and integration tests, deterministic seeds, and checkpoint demonstrations were used to validate behavior and claims. Repository evidence reports a full passing suite (`118/118`) at the final checkpoint stage. The system’s strongest outcomes are module coherence, reproducibility, and evidence-backed implementation quality. Main limitations include coarse RL discretization and growing UI orchestration complexity in the visual client. Overall, the project demonstrates a technically consistent, modular AI system that meets project requirements and supports realistic future extension.

## 1. Introduction
Survival simulation is a strong setting for applied AI because it naturally combines optimization, symbolic constraints, adversarial decision-making, and uncertainty. The Colony Manager was designed as a systems project rather than a single-algorithm exercise: each module maps to a course topic, and all modules are integrated into one turn-based pipeline that can be tested and demonstrated.

The core problem is resource survival under pressure. Each turn, the player must allocate limited attention and movement to keep resources stable and complete tasks while the Director AI introduces disruptions. If pressures accumulate without effective response, agents die, station performance degrades, and colony stability collapses. This dynamic creates meaningful interactions among planning, constraints, and adversarial strategy.

The project scope includes:
- A validated world model for agents, tasks, resources, stations, and map metadata.
- Path planning and task planning with configurable search algorithms.
- Rule-based survival checks with deterministic consequence application.
- Adversarial event selection driven by colony vulnerability.
- Centralized event-application logic to mutate state safely.
- Survival assessment and learning hooks through heuristics and tabular RL.
- Test suite and visual demonstration support.

The system intentionally does not claim deep reinforcement learning or complete game-balance optimization. Instead, it prioritizes correctness, integration clarity, and evidence-backed reporting. This design choice aligns with course requirements emphasizing modular architecture, explainability, and evaluation quality.

## 2. System Architecture
The architecture is organized around one canonical state object (`ColonyState`) and one orchestration layer (`GameEngine`). Every module consumes, evaluates, or mutates the same state model through explicit interfaces. This avoids hidden shared logic and supports both unit-level and pipeline-level testing.

### 2.1 High-Level Structure
- **State core (Module 1):** owns authoritative simulation data.
- **Reasoning and planning modules (Modules 2-4):** compute movement, rule outcomes, and adversarial choices.
- **Transition module (Module 5):** applies event effects.
- **Assessment module (Module 6):** summarizes survival outlook and supports adaptation.
- **Orchestration layer (`GameEngine`):** executes the fixed turn cycle and returns structured reports.
- **Presentation layer (`visual_game.py`):** demonstrates runtime behavior with UI controls and render state.

### 2.2 Turn Pipeline and Data Flow
Each turn follows:
1. **Logic:** enforce survival constraints and apply consequences.
2. **Planning:** produce routes/task choices for agents.
3. **Adversarial:** select event subject to difficulty, budget, and cooldown.
4. **Resolution:** apply selected event and update affected state fields.
5. **Assessment:** compute survival probability/risk indicators and optionally update learned values.

The output of one phase becomes input for the next phase. Because phase order is deterministic and reports are structured, errors are easier to localize and behavior is reproducible under seeded conditions.

### 2.3 Architecture Artifact Placeholder
**[Figure 1 Placeholder: End-to-end architecture diagram]**  
Include module boxes (`module1_state` ... `module6_rl`), `GameEngine`, and arrows showing data flow through the five turn phases. The figure should explicitly mark persistent RL cache files (`.rl_cache/survival_q.json`, `.rl_cache/director_q.json`).

## 3. Module Implementation Summary
This section summarizes each module by purpose, inputs/outputs, and key design choices.

### 3.1 Module 1: State Representation (`src/module1_state`)
**Purpose:** Provide the canonical simulation model.  
**Inputs:** Prior state, updates to agents/tasks/resources/stations.  
**Outputs:** Validated updated state and serialization forms.  
**Design choices:**
- `ColonyState` centralizes model ownership and mutation methods.
- Validation rejects duplicate IDs, illegal collisions, and invalid references.
- Serialization/deserialization supports deterministic reload and test scenarios.
- Seeded world data supports reproducible procedural behavior.
**Integration dependencies:** foundational dependency for all modules.

### 3.2 Module 2: Search (`src/module2_search`)
**Purpose:** Compute navigation/task plans for agent execution.  
**Inputs:** State topology, tasks, agent locations/capabilities.  
**Outputs:** Planned routes, travel costs, assignment decisions.  
**Design choices:**
- Multiple algorithms (A*, IDA*, Beam Search) behind a shared planner API.
- Search helpers abstract common graph and heuristic logic.
- Runtime algorithm switching supports comparative testing and gameplay options.
**Integration dependencies:** consumes module 1 state; affects movement execution and response timing.

### 3.3 Module 3: Propositional Logic (`src/module3_logic`)
**Purpose:** Enforce rule-based survival constraints.  
**Inputs:** Current `ColonyState`.  
**Outputs:** Violation reports and deterministic consequences.  
**Design choices:**
- Explicit rule definitions keep behavior explainable.
- Consequence application is separated from detection for testability.
- Multi-agent edge cases are validated through tests.
**Integration dependencies:** should run before planning/adversarial phases so downstream modules operate on valid logical state.

### 3.4 Module 4: Game Theory / Director (`src/module4_game_theory`)
**Purpose:** Select disruptive events that maximize pressure under constraints.  
**Inputs:** Colony vulnerability indicators, event options, difficulty settings, budget/cooldowns.  
**Outputs:** Selected event or no-event decision.  
**Design choices:**
- Minimax-style adversarial selection and related search strategies.
- Budget and cooldown constraints prevent repetitive degenerate play.
- Optional RL bias allows adaptive event preference tuning over time.
**Integration dependencies:** reads state/rule outcomes; sends event to module 5.

### 3.5 Module 5: Event Application Logic (`src/module5_events`)
**Purpose:** Apply event effects safely and consistently.  
**Inputs:** Current state + selected event.  
**Outputs:** Mutated state and structured resolution report.  
**Design choices:**
- Centralized resolver avoids scattered side-effect logic.
- Explicit handlers for station degradation, targeted hazards, and cascades.
- Deterministic transitions allow reproducible tests and debugging.
**Integration dependencies:** consumes module 4 output and produces post-event state for module 6.

### 3.6 Module 6: RL / Heuristics (`src/module6_rl`)
**Purpose:** Compute survival/risk assessment and support adaptive learning hooks.  
**Inputs:** Post-resolution state and transition context.  
**Outputs:** Assessment dictionary (risk, threats, time-to-failure), optional Q-table updates.  
**Design choices:**
- Heuristic path provides interpretable baseline behavior.
- Tabular Q-learning over discretized states keeps learning bounded and explainable.
- Policy persistence in `.rl_cache` supports cross-run carryover.
**Integration dependencies:** consumes final turn state and can inform future strategic behavior.

## 4. Evaluation Methodology
Evaluation was designed to answer two questions: (1) does each module satisfy its contract, and (2) does the full pipeline behave coherently when modules interact?

### 4.1 What Was Evaluated
- Module-level correctness for all six modules.
- Integration behavior across the full turn sequence.
- Adversarial fairness mechanics (budget and cooldown effects).
- Failure semantics (agent death handling, station failure progression, recovery behavior).
- Multi-floor and progression stability where implemented.

### 4.2 Metrics
- Test pass/fail counts from unit and integration suites.
- Deterministic assertion checks on specific state transitions.
- Cross-module regression checks in integration scenarios.
- Stability indicators under seeded deterministic setups.

### 4.3 Setup and Data
- Test framework: Python `unittest`.
- Runner: `run_tests.py`, with modular and integration discovery.
- Data: synthetic deterministic states for controlled expected outcomes.
- Runtime checks: engine-only (`main.py`) and visual (`visual_game.py`) demonstrations.

### 4.4 Collection Process
1. Run full test suite and record total pass/fail.
2. Verify module-specific edge-case assertions.
3. Validate integration flow and turn report consistency.
4. Compare checkpoint logs and reports to observed outcomes.

### 4.5 Evaluation Artifact Placeholder
**[Table 1 Placeholder: Evaluation summary matrix]**  
Include rows for each module and integration suite, with columns: "What tested", "Evidence", "Outcome", and "Notes".

## 5. Results
The implemented system demonstrates stable module integration and evidence-backed correctness. Reported final project evidence indicates all automated tests passed (`118/118`) at the documented checkpoint run. More importantly, behavior aligns with architecture intent: state consistency, deterministic phase progression, and explicit inter-module dependencies.

### 5.1 Strengths
- **Coherent architecture:** all six modules function through one shared state contract.
- **Strong test-backed behavior:** edge cases and cross-module interactions are explicitly validated.
- **Reproducibility:** seeded world and deterministic tests support consistent verification.
- **Fair adversarial dynamics:** Director constraints improve challenge quality and reduce trivial spam.
- **Traceable state transitions:** centralized event resolution and structured reports simplify debugging.

### 5.2 Weaknesses
- **RL granularity limitations:** discretized tabular states compress nuanced colony conditions.
- **UI maintenance risk:** `visual_game.py` has broad responsibilities and increased complexity.
- **Evaluation realism limits:** no external benchmark dataset or broad player telemetry study.

### 5.3 Suggested Results Artifacts
**[Figure 2 Placeholder: Test coverage by module]**  
Bar chart showing approximate number of tests/assertion groups per module plus integration group.

**[Figure 3 Placeholder: Failure and recovery timeline]**  
Timeline of one adverse scenario (event -> station degradation -> player response -> recovery/failure state).

### 5.4 Example Results Table Content (for Table 1)
| Area | Evidence | Outcome |
|---|---|---|
| State validity | Unit tests | Pass |
| Search planning | Unit + integration tests | Pass |
| Rule enforcement | Unit tests | Pass |
| Director constraints | Unit tests | Pass |
| Event resolver transitions | Unit tests | Pass |
| Survival assessment | Unit tests | Pass |
| Full suite | Unified runner | 118/118 Pass |

## 6. Proposal Delta
The final system follows the proposed six-module structure but diverges in several major implementation decisions:

1. **Adversarial fairness constraints were expanded.**  
   The proposal emphasized challenge selection; the final system added explicit budget and cooldown controls to keep disruption behavior strategic but bounded.

2. **Module 6 converged on hybrid heuristics + tabular RL.**  
   Instead of pursuing high-complexity RL, the final implementation uses interpretable heuristics and Q-learning persistence hooks aligned with project scope.

3. **Visual and demonstration features were expanded.**  
   Additional options/presentation-facing behavior increased demonstration quality and integration visibility, with some complexity trade-off in the UI layer.

4. **Terminal conditions were clarified during implementation.**  
   Game-over semantics were refined around living-agent viability and state progression consistency.

No required module was removed. Scope changes were primarily about balancing technical ambition with testability and reliability.

## 7. Limitations and Failure Analysis
### 7.1 Limitation 1: Discretized RL representation
**Observed issue:** Q-learning state buckets can merge distinct high-dimensional colony conditions into the same discrete state, reducing policy precision.  
**Likely cause:** intentional simplification for interpretability and manageable implementation scope.  
**Improvement path:** richer feature encoding or lightweight function approximation while preserving explainability.

### 7.2 Limitation 2: Visual client complexity
**Observed issue:** `visual_game.py` centralizes rendering, input, state synchronization, and UI logic.  
**Likely cause:** iterative feature additions in a single file during rapid development.  
**Improvement path:** split into dedicated renderer/input/HUD/controller modules and add targeted UI regression tests.

### 7.3 Limitation 3: External validity of outcomes
**Observed issue:** evaluation is primarily simulation-based with deterministic synthetic states.  
**Likely cause:** project focus on module correctness and integration under time constraints.  
**Improvement path:** add repeated-seed benchmark experiments, playtesting telemetry, and comparative difficulty analysis.

### 7.4 Concrete Failure Cases
- Resource collapse when repeated adverse events align with low station availability.
- Delayed recovery when pathfinding options are constrained.
- Increased challenge volatility when multiple stressors stack in short windows.

## 8. Individual Contributions
Project work was shared evenly across the full timeline. Early modules were developed collaboratively, and later responsibilities were split across implementation support, integration/testing, presentation development, and final documentation.

- **Adam Alvarado (50%)**: Core module implementation support, integration contributions, presentation development, and final paper preparation.
- **Rick King (50%)**: Core module implementation support, engine orchestration contributions, and testing pipeline contributions.

Total effort allocation: **100%**.

## 9. Conclusions and Future Work
The Colony Manager achieved its primary goal: integrating six AI course topics into one coherent survival system with explicit module boundaries and test-backed behavior. The project demonstrates how planning, symbolic constraints, adversarial reasoning, and adaptive assessment can be composed in a deterministic architecture without sacrificing readability or evidence quality.

Future work should focus on:
1. Refactoring visual/UI orchestration for maintainability.
2. Expanding empirical evaluation with repeated-seed and telemetry-based studies.
3. Improving adaptation quality with richer learning representations.
4. Formalizing stage/campaign progression for long-horizon strategy analysis.
5. Running controlled comparisons among adversarial algorithms under fixed constraints.

## 10. References
[1] P. E. Hart, N. J. Nilsson, and B. Raphael, "A Formal Basis for the Heuristic Determination of Minimum Cost Paths," *IEEE Transactions on Systems Science and Cybernetics*, vol. 4, no. 2, pp. 100-107, 1968.  
[2] S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed. Pearson, 2021.  
[3] C. E. Shannon, "Programming a Computer for Playing Chess," *Philosophical Magazine*, vol. 41, no. 314, pp. 256-275, 1950.  
[4] C. J. C. H. Watkins and P. Dayan, "Q-learning," *Machine Learning*, vol. 8, pp. 279-292, 1992.  
[5] Python Software Foundation, "unittest - Unit testing framework." [Online]. Available: https://docs.python.org/3/library/unittest.html  
[6] Pygame Community, "Pygame Documentation." [Online]. Available: https://www.pygame.org/docs/  
[7] CSC343 Course Staff, "AI System Project Instructions." [Online]. Available: https://csc-343.path.app/projects/project-2-ai-system/ai-system.project.md  
[8] CSC343 Course Staff, "AI System Rubric." [Online]. Available: https://csc-343.path.app/projects/project-2-ai-system/ai-system.rubric.md

---

## Appendix A (Optional): Final Submission Assembly Checklist
- [ ] Replace repo/demo placeholders at top of paper.
- [ ] Insert at least 3 visuals total.
- [ ] Ensure Figure 1 is architecture diagram.
- [ ] Ensure at least one evaluation table/plot is present.
- [ ] Reference every figure/table in body text.
- [ ] Keep final main text near 2200-2500 words.
- [ ] Convert to PDF with page numbers.
- [ ] Final filename: `CSC343_Project_Name1_Name2.pdf`.

