# The Colony Manager: AI-Adversarial Survival System
**Team Members:** Adam Alvarado, Rick King  
**Repository Link:** [INSERT REPO URL]  
**Demo Link:** [INSERT DEMO URL]

---

## Abstract
The Colony Manager is a turn-based real-time strategy game that combines cooperative planning with adversarial AI pressure. The player manages colonists whose survival depends on oxygen, calories, and integrity, while an AI Director selects disruptive events designed to exploit colony weaknesses. At runtime, the game moves through a consistent turn cycle where the colony state is passed from phase to phase and updated after each decision. Colony information is represented in a JSON-compatible state structure, allowing player actions, rule checks, planning outcomes, and disaster effects to be tracked in one shared model. Within this loop, search methods (A*, IDA*, and Beam Search) support movement, logical rules enforce survival constraints, adversarial selection pressures weak points with budget/cooldown limits, and event resolution applies concrete state transitions. A survival assessor then estimates risk using heuristic scoring with tabular Q-learning support and persistent policy caches.
To evaluate the final system, we focused on whether behavior remained correct and coherent when all components interacted in sequence. We used deterministic seeded scenarios, automated tests, and checkpoint demonstrations to validate implementation claims and observe failure behavior under pressure. Results showed strong consistency in data flow and module interaction, especially in state transitions and adversarial-response loops. The most important strengths are clear architecture boundaries and reliable pipeline integration, followed by reproducibility across seeded runs. Key limitations are the coarse granularity of tabular RL and growing UI orchestration complexity in the visual client. Overall, the project delivers a technically grounded AI survival system with realistic extension paths.

## 1. Introduction
The Colony Manager is built around a simple gameplay tension: the colony must keep critical resources stable while an adversarial Director continually creates new pressure. Oxygen, calories, and integrity are always at risk, so each turn forces trade-offs between movement, repairs, and immediate survival. If those trade-offs are handled poorly, agents die, station performance drops, and recovery becomes increasingly difficult.

To support this loop, the project treats the colony as one JSON-compatible state that moves through a fixed sequence of phases each turn. Player actions, planner outputs, rule checks, and disaster effects all update the same shared state, which makes behavior easier to track and reason about. This lets planning, logic, adversarial selection, and event resolution interact as one system rather than as isolated algorithm demos.

The implementation focuses on technical coherence and evidence-backed behavior. Search methods drive movement and planning decisions, logical constraints enforce survival rules, adversarial selection targets weak points under practical limits, and a survival assessor estimates risk with heuristic and tabular learning support. The goal is not to claim perfect optimization or deep-RL performance, but to deliver a reliable integrated strategy system that can be tested, demonstrated, and extended.

## 2. System Architecture
At a high level, The Colony Manager is organized as a turn-based AI system where player input, world state, and adversarial pressure are processed through one shared simulation loop. The full system includes a state layer, six AI modules, turn coordination logic, and a visual gameplay interface. Rather than splitting game logic across unrelated data stores, the design keeps one structured colony state as the source of truth for resources, agent status, tasks, and infrastructure condition.

Modules interact in a strict dependency order so each stage receives valid inputs from the previous stage. The state representation stage provides the current snapshot, the rule layer evaluates constraints and applies immediate consequences, and the planning/search layer computes movement and task decisions using that updated state. The AI Director then performs adversarial selection based on weaknesses and constraints, the event-resolution stage applies disruption effects, and the survival-assessment stage evaluates risk from the resulting condition. This ordering is intentional: constraint enforcement happens before planning, disruption selection happens before resolution, and assessment happens after state mutation.

Data flows through the pipeline as a repeated read-update-pass cycle. Each phase reads the current colony state, computes outputs for its own responsibility, writes state changes or phase outputs, and passes the updated result to the next phase in turn. Figure 1 illustrates this turn-cycle progression from initial state, through rule evaluation, planning, adversarial selection, and event resolution, to post-turn risk assessment and next-turn state. This structure creates a traceable chain of evidence for each turn, making it possible to explain exactly why colony values changed and to validate behavior with unit tests, integration tests, and demo observations.

### 2.1 Architecture Artifact Placeholder
**[Figure 1 Placeholder: End-to-end architecture diagram]**  
Include boxes for state representation, rule enforcement, planning/search, AI Director, event resolution, and survival assessment, with arrows showing turn-cycle data flow. The figure should also show persistent policy cache storage used by the learning components.

## 3. Module Implementation Summary
This section summarizes each module by purpose, inputs/outputs, and key design choices.

### 3.1 Module 1: State Representation (`src/module1_state`)
The purpose of Module 1 is to represent the colony as one authoritative state model that all other parts of the system can trust. Its inputs are the prior turn state plus updates to agents, tasks, resources, and station/infrastructure fields, and its outputs are a validated updated state in memory and JSON-compatible serialization for persistence and reload. In practice, this module keeps one shared state representation with strict validation and explicit serialization, so the rest of the pipeline can rely on consistent data. Integration-wise, this module is the core dependency for the entire pipeline because every downstream module reads from or writes to the state it defines.

### 3.2 Module 2: Search (`src/module2_search`)
The purpose of Module 2 is to compute movement and task-planning decisions for agents. It takes as input the current map/state topology, active tasks, and agent locations or capabilities, and it outputs route plans, travel costs, and assignment decisions used in turn execution. The main implementation choice here is a single planning interface that supports A*, IDA*, and Beam Search, with shared helper logic to keep behavior consistent across algorithms. Integration dependencies are direct: Module 2 consumes state from Module 1 and its outputs influence later stages by shaping which tasks complete first and how exposed the colony is when the AI Director selects disruptions.

### 3.3 Module 3: Propositional Logic (`src/module3_logic`)
The purpose of Module 3 is to enforce survival constraints through rule-based logic before the rest of the turn proceeds. Its input is the current colony state, and its outputs are violation reports plus applied consequences (for example, status updates when critical constraints fail). The module keeps rules explicit and separates detection from consequence application, which makes failures easier to debug and test. Integration dependencies are temporal and structural: Module 3 depends on Module 1 state and runs before planning and adversarial selection, ensuring later modules operate on logically valid conditions.

### 3.4 Module 4: Game Theory / Director (`src/module4_game_theory`)
The purpose of Module 4 is to choose adversarial disruptions that pressure the colony at the right moment. It takes as input vulnerability indicators derived from the current state, available event candidates, and control constraints such as difficulty, budget, and cooldown, and it outputs a selected event (or a no-event decision when constraints block selection). The core approach combines adversarial reasoning with fairness limits so challenge remains strategic without becoming repetitive, with optional learning bias for adaptation over time. Integration dependencies are straightforward: it consumes outputs from state and rule evaluation stages, then passes the selected disruption to Module 5 for application.

### 3.5 Module 5: Event Application Logic (`src/module5_events`)
The purpose of Module 5 is to apply disruption effects consistently and predictably to the live colony state. Its inputs are the selected event from Module 4 and the current state snapshot, and its outputs are the mutated state plus a structured resolution report describing what changed. The main design choice is to keep event mutation logic centralized, with explicit handlers for station degradation, targeted hazards, and cascading effects so transitions stay auditable. Integration dependencies are critical here: Module 5 depends on Module 4 event output and produces the post-event state that Module 6 uses for survival assessment.

### 3.6 Module 6: RL / Heuristics (`src/module6_rl`)
The purpose of Module 6 is to estimate survival risk after each turn and provide a bounded adaptation mechanism. It takes as input the post-resolution colony state and transition context, and it outputs an assessment dictionary (risk level, critical threats, and time-to-failure indicators) with optional Q-table updates. It uses a simple heuristic baseline with tabular Q-learning on top, and carries learned values across runs to retain adaptation over time. Integration dependencies place this module at the end of the pipeline: it consumes Module 5 output and produces risk information that can guide future strategic behavior and tuning.

## 4. Evaluation Methodology
The evaluation was designed to verify both local correctness and full-system behavior. At the module level, we evaluated whether each component met its stated contract (state updates, planning outputs, rule enforcement, event selection, event application, and risk assessment). At the integration level, we evaluated whether those components remained coherent when executed in sequence across a full turn, including fairness constraints in adversarial selection, failure semantics such as death handling and station degradation, and multi-step state carryover behavior.

We used four main metric types: test pass/fail outcomes, assertion-level checks on expected state transitions, cross-module consistency checks in integration scenarios, and consistency checks under seeded conditions. The test setup used a standard Python unit-testing framework with both unit and integration suites executed through a unified test runner and discovery process. Test data was intentionally synthetic and controlled so expected outputs could be validated precisely, and runtime behavior was also observed in both engine-only and visual demonstration modes to confirm that automated checks matched gameplay execution.

Results were collected in a staged process: run the full suite, inspect module-specific edge cases, confirm turn-pipeline consistency in structured outputs, and cross-check findings against checkpoint reports and demo observations. This method ensured that reported claims were tied to repeatable evidence rather than one-off runs. **[Table 1 Placeholder: Evaluation summary matrix]** should summarize this section with rows for each module and integration area, using columns for what was evaluated, evidence type, outcome, and key notes.

## 5. Results
As a complete game system, The Colony Manager delivers a consistent survival loop where player planning and adversarial pressure meaningfully interact each turn. In successful runs, players can recover from disruptions by rerouting agents, prioritizing critical resources, and stabilizing damaged stations before pressure compounds. The game therefore creates the intended tension: decisions that look reasonable in isolation can still fail when resource decay, travel cost, and event timing overlap.

The strongest outcome is that the full pipeline behaves coherently during live play. Rule enforcement, planning outcomes, director decisions, and event resolution produce state changes that are understandable from one turn to the next, which makes both gameplay and debugging more reliable. Budget and cooldown constraints also improved adversarial pacing by preventing repetitive disruption patterns and encouraging more varied pressure over time.

The main weaknesses are visible at the game level as well. Adaptive behavior remains limited by coarse state discretization in the learning layer, so strategic adjustment can feel broad rather than nuanced. In addition, the visual/client side carries substantial orchestration responsibility, which slows iteration and can make balancing harder as features grow. These results suggest the core loop is solid, but future work should focus on deeper adaptation quality, cleaner UI architecture, and broader playtesting data for difficulty tuning.

## 6. Proposal Delta
The final project stayed aligned with the original proposal at the architecture level: the same six required modules were implemented, and the core survival loop (state, planning, logic, adversarial choice, event application, and assessment) remained intact. What changed was not the module count or topic coverage, but how aggressively each module was scoped in the final game. Early proposal language emphasized near-optimal adversarial pressure and broader adaptation ambitions, while the final build prioritized consistency, playability, and integration reliability.

The largest change was in the adversarial layer. The proposal framed disruption selection mainly as a challenge-maximization problem driven by minimax-style search and difficulty scaling. In the final system, that logic was constrained with explicit budget and cooldown behavior so pressure remained strategic without becoming repetitive or unfair. This change was made after integration and gameplay testing showed that unconstrained disruption patterns could reduce recoverability and weaken game pacing.

The second major change was in the adaptation module. The proposal allowed either reinforcement learning or heuristics, with RL as the more ambitious direction. The final implementation settled on a hybrid approach: heuristic survival assessment with bounded tabular Q-learning support and persistence. This rescale was intentional and was made to keep learning behavior interpretable and stable within project constraints. In parallel, presentation-facing systems (menus/options, powerups, multi-floor progression support, and UI feedback) expanded more than originally described to improve demonstration quality and gameplay clarity. No required modules were dropped or merged, but Module 4 and Module 6 were rescaled for robustness, and non-core presentation features were expanded around the same six-module pipeline.

## 7. Limitations and Failure Analysis
One concrete limitation is the discretized representation used in the tabular learning layer. Distinct high-dimensional colony conditions can collapse into the same state bucket, which reduces policy precision and can produce similar responses to meaningfully different situations. The likely cause is intentional simplification for interpretability and manageable implementation effort. A practical improvement path is to expand state features or adopt lightweight function approximation while preserving explainability and testability.

A second limitation is the concentration of visual and interaction responsibilities in one large client layer. Rendering, input handling, state synchronization, and display logic are tightly coupled, which increases maintenance risk and makes regressions harder to isolate. This is largely a consequence of iterative feature growth during rapid development. The direct improvement is architectural refactoring into clearer interface, rendering, and state-update components, supported by targeted regression checks.

Failure behavior also appears in gameplay scenarios where multiple stressors align. For example, repeated disruptions during low station availability can trigger rapid resource collapse before recovery actions complete, and constrained movement paths can delay response enough to amplify losses. These failures are useful diagnostic signals rather than isolated bugs: they indicate where balancing, route robustness, and adaptive policy quality should be improved in future iterations. A stronger benchmark suite with repeated seeds and staged stress tests would make these failure patterns easier to quantify and compare over time.

## 8. Individual Contributions
Work was divided evenly across the project timeline. Early module development was collaborative, and later tasks were split by focus area while maintaining equal overall effort.

- **Adam Alvarado — 50%**: co-developed core systems, contributed to integration and gameplay polish, led presentation materials, and prepared the final paper.
- **Rick King — 50%**: co-developed core systems, contributed to integration and engine-side coordination, and led testing and verification support.

Combined contribution: **100%**.

## 9. Conclusions and Future Work
The Colony Manager achieved its primary goal: integrating six AI course topics into one coherent survival system with explicit module boundaries and test-backed behavior. The project demonstrates how planning, symbolic constraints, adversarial reasoning, and adaptive assessment can be composed in a deterministic architecture without sacrificing readability or evidence quality.

Future work is centered on making the game feel more complete and strategically richer. A major priority is updating visuals and graphics so the game better reflects the quality of the underlying systems and provides clearer player feedback during high-pressure turns. Another key goal is introducing moving objects and dynamic hazards so planning algorithms such as A* must adapt to changing map conditions rather than primarily static terrain constraints. We also want to build a conclusive campaign mode that gives runs a stronger beginning-to-end structure with clearer progression and final objectives. Beyond that, the project can continue expanding core game features to improve depth, replayability, and challenge variety while preserving the current architecture’s modular design.

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

