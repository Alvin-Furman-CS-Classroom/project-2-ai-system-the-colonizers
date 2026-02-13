# Module 1 Explanation: Colony State Management

## Overview

Module 1 is the foundational state representation module for The Colony Manager. It manages all colony data including agents (colonists), resources, infrastructure, and tasks. This module serves as the "memory" of the game system that all other modules read from and modify.

---

## Input

### What does Module 1 accept?

Module 1 accepts a **previous turn's colony state** as a JSON structure (or Python dictionary). The input can be:
- An empty/None value (creates a new empty colony)
- A dictionary containing the previous state

### Input Structure

```python
{
    "agents": [
        {
            "id": 0,
            "name": "Alice",
            "location": (10, 15),
            "oxygen": 75.0,
            "calories": 60.0,
            "integrity": 90.0,
            "status": "active"
        },
        # ... more agents
    ],
    "resources": {
        "oxygen": 100.0,
        "calories": 100.0,
        "integrity": 100.0
    },
    "infrastructure": {
        "section_alpha": {
            "integrity": 85.0,
            "status": "operational",
            "efficiency": 0.9
        }
        # ... more infrastructure locations
    },
    "active_tasks": [
        {
            "task_id": "repair_hull_001",
            "agent_id": 0,
            "location": "section_alpha",
            "progress": 0.6,
            "completion_turn": 3
        }
        # ... more tasks
    ],
    "turn_number": 5,
    "world_seed": 42
}
```

### Constraints

- Agent IDs must be unique integers
- Agent locations must be tuples of (x, y) coordinates
- Resource values should be between 0-100
- Task IDs must be unique strings
- No two agents can occupy the same location

### Example Usage

```python
from src.module1_state.colony_state import ColonyState

# Create from previous state
previous_state_json = '{"agents": [...], "resources": {...}, ...}'
state = ColonyState.from_json(previous_state_json)

# Or create empty state
state = ColonyState()
```

---

## Output

### What does Module 1 produce?

Module 1 produces an **updated colony state** after resource consumption and state modifications. The output has the same JSON structure as the input, but with updated values.

### Output Structure

The output maintains the same structure as input, with modifications such as:
- Updated resource levels (after consumption)
- Modified agent statuses (locations, health, etc.)
- Updated infrastructure states
- Modified task progress
- Incremented turn number

### Example Output

```python
{
    "agents": [
        {
            "id": 0,
            "name": "Alice",
            "location": (10, 15),
            "oxygen": 70.0,  # Consumed 5.0
            "calories": 55.0,  # Consumed 5.0
            "integrity": 90.0,
            "status": "active"
        }
    ],
    "resources": {
        "oxygen": 95.0,  # Consumed 5.0
        "calories": 90.0,  # Consumed 10.0
        "integrity": 100.0
    },
    "infrastructure": {...},
    "active_tasks": [...],
    "turn_number": 6,  # Incremented
    "world_seed": 42
}
```

### Next Module Feed

**Module 2 (Search/Task Planning)** will:
- Read agent locations and capabilities from the state
- Read active tasks and their requirements
- Use `get_tile_at()` for pathfinding
- Output optimized task sequences that Module 1 will use to update agent locations and task progress

**Module 3 (Logic/Rule Enforcement)** will:
- Read the entire state to check survival constraints
- Validate that resources are above zero
- Check agent statuses
- Output violation reports that Module 1 will use to update agent statuses (e.g., mark agents as dead)

**Module 4 (Game Theory)** will:
- Read state to identify colony weaknesses
- Use `copy()` to simulate different event outcomes
- Output event selections that Module 5 will apply

---

## AI Concepts

### State Representation

Module 1 demonstrates **State Representation** in two key ways:

#### 1. Explicit State Management
- The `ColonyState` class explicitly represents the complete game state
- State is stored as structured data (agents, resources, infrastructure, tasks)
- State can be serialized to JSON for persistence
- State can be copied for simulation (used by Module 4 for game tree exploration)

#### 2. Procedural State Generation
- The world is **not stored** as a fixed map
- Instead, the world state is represented **implicitly** by:
  - A seed number (`world_seed`)
  - A deterministic generation function (`get_tile()`)
- Any tile at coordinates (x, y) is computed on-demand: `tile = f(seed, x, y)`
- This demonstrates **compact state representation**: a small seed + function defines an infinite world

### Why This Approach?

**Explicit State (ColonyState)**:
- Needed for game logic (tracking agents, resources, tasks)
- Must be mutable (updated each turn)
- Must be serializable (save/load games)
- Must be validatable (ensure data integrity)

**Procedural State (Tiles)**:
- Efficient: No need to store infinite world
- Deterministic: Same seed = same world (reproducible)
- Flexible: Can query any coordinate without pre-generation
- Demonstrates compact encoding: finite description (seed + rule) → infinite state space

### Connection to Course Topic

This directly relates to **State Representation** because:
- We have a **finite description** (seed + generation rule) that defines a **potentially infinite set** of cell states
- We can compute any part of the state on demand without storing it
- This is the same principle used in AI: compact representations that enable efficient computation

---

## Key Features Demonstrated

1. **State Validation**: Ensures data integrity (unique IDs, valid ranges, no collisions)
2. **Resource Management**: Tracks and consumes resources (global and per-agent)
3. **Agent Management**: CRUD operations for agents with collision detection
4. **Infrastructure Management**: Tracks colony systems and their status
5. **Task Management**: Tracks active tasks and their progress
6. **Serialization**: Save/load state as JSON
7. **Procedural Generation**: Deterministic world generation without storage

---

## Visual Representation Ideas

### Data Flow Diagram
```
[Previous State JSON]
        ↓
[ColonyState.from_json()]
        ↓
[State Object with agents, resources, infrastructure, tasks]
        ↓
[Resource Consumption] → [Agent Updates] → [Task Updates]
        ↓
[Updated State JSON]
        ↓
[Next Module Input]
```

### State Structure Visualization
```
ColonyState
├── agents: List[Agent]
│   ├── id, name, location
│   ├── oxygen, calories, integrity
│   └── status, skills, current_task
├── resources: Dict[str, float]
│   ├── oxygen, calories, integrity
├── infrastructure: Dict[str, Dict]
│   └── location → {integrity, status, efficiency}
├── active_tasks: List[Task]
│   └── task_id, agent_id, location, progress
├── turn_number: int
└── world_seed: int → Procedural Tiles
```

### Procedural Generation Concept
```
Seed: 42
    ↓
Function: f(seed, x, y) → tile
    ↓
Infinite World (computed on-demand)
```

---

## Integration Point in System Pipeline

```
[Game Engine]
    ↓
[Module 1: State] ← Reads/Writes state
    ↓
[Module 3: Logic] ← Reads state, outputs violations
    ↓
[Module 2: Search] ← Reads state, outputs task plans
    ↓
[Module 4: Game Theory] ← Reads state, outputs events
    ↓
[Module 5: Events] ← Reads state, modifies state
    ↓
[Module 1: State] ← Updated state for next turn
```

Module 1 is the **central hub** that all other modules interact with.
