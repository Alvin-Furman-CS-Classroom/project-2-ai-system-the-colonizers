# Slideshow Plan: The Colony Manager

This file implements the presentation plan as a game-first deck that lightly references modules while explaining gameplay.

## Presentation Setup

- Target length: 8-12 minutes
- Slide count: 10 core slides + 3 optional backup slides
- Recommended style: one key message per slide, one strong visual per slide

## To-Do 1 Output: Visual Collection List (4-6 screenshots)

Use this exact shot list while running `python visual_game.py`:

1. **Opening colony state**
- Full map + HUD at turn start
- Purpose: introduce player role and resources

2. **High-pressure decision moment**
- Low Oxygen or Calories with multiple pending actions
- Purpose: show strategic tension

3. **Disaster announcement / event trigger**
- Any Director event popup or warning
- Purpose: show adversarial AI presence

4. **Before/after consequence pair**
- Same zone before a hull breach (or similar event), then after impact
- Purpose: support your example-turn slide

5. **Recovery attempt**
- Colonists repairing/responding after a disaster
- Purpose: show player agency and adaptation

6. **End-state snapshot (win-like or loss-like)**
- Final turns where outcome is visibly clear
- Purpose: support conclusion and replayability point

## Core Deck (10 Slides)

## Slide 1 - Title
**On-slide text**
- The Colony Manager: AI-Adversarial Survival System
- Name, course, date
- Hook: "Can you keep your colony alive against an intelligent adversary?"

**Visual**
- Best full-map screenshot (Opening colony state)

**Speaker notes (15-25s)**
- "This is a turn-based survival game where you manage colonists and resources in a hostile environment."
- "The twist is that an AI Director actively tries to exploit your weaknesses each turn."

## Slide 2 - Core Fantasy: What Playing Feels Like
**On-slide text**
- You are the colony commander.
- Keep 3 critical resources above zero:
  - Oxygen
  - Calories
  - Integrity

**Visual**
- HUD-focused crop showing resources

**Speaker notes (35-45s)**
- "Every turn is a tradeoff problem. If one resource collapses, the colony can rapidly fail."
- "The game is built around balancing short-term survival against long-term stability."

## Slide 3 - One Turn = Four Phases
**On-slide text**
- Logic -> Planning -> Adversarial -> Resolution
- Repeat until survival or collapse

**Visual**
- Simple 4-box flow diagram

**Speaker notes (40-55s)**
- "Logic enforces survival rules."
- "Planning chooses how colonists execute tasks."
- "Adversarial is where the AI Director selects a disruption."
- "Resolution applies costs and consequences to the world state."

## Slide 4 - Player Decision Snapshot
**On-slide text**
- Example situation: low Oxygen, damaged infrastructure, limited actions
- Key question: repair now or gather resources first?

**Visual**
- High-pressure decision screenshot

**Speaker notes (45-60s)**
- "This is the kind of moment the game is built for."
- "You never optimize one metric in isolation; each decision shifts risk elsewhere."

## Slide 5 - The AI Director (Why It Is Challenging)
**On-slide text**
- Director analyzes colony weaknesses
- Chooses events to maximize pressure
- Difficulty scales AI strength:
  - Easy: weaker heuristics / shallower lookahead
  - Hard: deeper Minimax / Alpha-Beta

**Visual**
- Disaster announcement screenshot

**Speaker notes (50-70s)**
- "The AI is not random chaos. It is targeted pressure based on current vulnerabilities."
- "Difficulty changes how strong the AI's reasoning is, not just raw damage numbers."

## Slide 6 - Modules in Plain Language
**On-slide text**
- State Management: tracks world state
- Task Planning: optimizes colonist actions
- Rule Engine: enforces survival logic
- Adversarial Selector: chooses disruptions
- Event Resolver: applies consequences
- Survival Assessor: estimates risk

**Visual**
- One-line pipeline graphic from state -> decisions -> consequences

**Speaker notes (45-60s)**
- "I treat modules as support systems behind the player experience."
- "You do not need to think in module names while playing; you feel them through game behavior."

## Slide 7 - Example Turn: Before -> Event -> After
**On-slide text**
- Before: Oxygen 42, Integrity 51, Calories 60
- Event: Hull breach in vulnerable section
- After: Oxygen 24, Integrity 39, repair priority increases

**Visual**
- Before/after screenshot pair

**Speaker notes (60-90s)**
- Use the full demo script in the "Example Turn Narration" section below.

## Slide 8 - Why This Is an AI System (Not Just a Game Loop)
**On-slide text**
- Search improves task sequencing
- Logic guarantees consistent rule outcomes
- Game theory drives adversarial event choice
- RL/heuristics estimate survival risk over time

**Visual**
- Minimal 4-column icon row (one method per behavior)

**Speaker notes (40-55s)**
- "Each AI method appears as visible behavior: smarter planning, consistent consequences, and adaptive pressure."

## Slide 9 - Results and Playtesting Insights
**On-slide text**
- Difficulty feels meaningfully different by AI reasoning depth
- Strongest player learning: proactive repair beats reactive recovery
- Core loop creates high replay tension

**Visual**
- Final-state screenshot + optional small chart

**Speaker notes (40-60s)**
- "Players improved most when they learned to protect weak points before the Director could exploit them."
- "The system rewards anticipation rather than panic response."

## Slide 10 - Closing + Q&A
**On-slide text**
- Strategic survival under adversarial pressure
- AI modules support fairness, tension, and replayability
- Next improvements:
  - richer event diversity
  - clearer predictive warnings

**Visual**
- End-state screenshot (win-like or loss-like)

**Speaker notes (20-35s)**
- "The main contribution is combining cooperative planning with adversarial AI in one clear turn loop."
- "I am happy to explain any module in detail during questions."

## To-Do 3 Output: Example Turn Narration (60-90 seconds)

Use this script on Slide 7:

"Here is one representative turn. At the start, the colony looks stable at a glance, but Oxygen and Integrity are both trending down. In the planning phase, I can either prioritize resource collection or preventive repairs. The Director then evaluates those vulnerabilities and selects a hull breach in a weak section. When that event resolves, Oxygen drops sharply and Integrity also takes a hit, which forces a new priority order for the next turn. This shows the core game tension: the player is solving a logistics problem while an adversary is actively trying to punish delayed maintenance. What makes the loop engaging is that each turn changes the risk landscape, so good play is about anticipating where the Director will strike next."

## To-Do 4 Output: Backup Technical Slides (Optional Q&A)

## Backup A - Difficulty and Algorithm Mapping
**On-slide text**
- Easy: heuristic targeting or low-iteration MCTS
- Normal: mixed strategy with moderate lookahead
- Hard: Minimax / Alpha-Beta with deeper search
- Outcome: challenge scales by decision quality

**Use when asked**
- "How do you adjust difficulty?"

## Backup B - State Representation Snapshot
**On-slide text**
- State stores:
  - resource levels
  - colonist statuses
  - infrastructure condition
  - active tasks and events
- Turn reports preserve phase-by-phase outputs

**Use when asked**
- "How do modules share data?"

## Backup C - Testing and Reliability
**On-slide text**
- Unit tests for each module
- Integration tests across phases
- Full suite result: `116/116` passing (per project docs)

**Use when asked**
- "How do you know this behavior is correct?"

## Presenter Checklist

- Capture and insert the 6 screenshots listed above.
- Keep text minimal; use speaker notes for details.
- Rehearse slide 7 narration to stay within 60-90 seconds.
- If short on time, skip slide 9 details and move to conclusion.
