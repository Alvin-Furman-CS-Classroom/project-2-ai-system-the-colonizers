# Agent Location, Bounds, Collisions, and Speed

Walkthrough of what exists today and what you might add before moving on.

---

## 1. What Exists Today

### Agent location at initialization

- **Schema (Module 1):** Agents have a **required** field `"location"`.
- **Allowed forms:**
  - **`(x, y)`** — tuple/list of two numbers (used in `main.py`, tests, and Module 2).
  - **String** — graph node ID (e.g. `"section_alpha"`); Module 2’s `get_agent_location_node()` accepts this and uses it directly if it’s in the graph.
- **Validation:** `validate_agent()` only checks that `location` is present and, if present, is a length-2 tuple/list of numbers. It does **not** check:
  - Map bounds
  - Collisions with other agents
  - That a string location is a valid graph node

So: you can initialize agents with any `(x, y)` or with a node ID string; there is no “map” or bounds stored in Module 1.

### Checking agent status

- **Location:** Read from `agent["location"]` or via `get_agent_by_id()` then `agent["location"]`.
- **Status:** Optional field `"status"` (`"active"`, `"incapacitated"`, `"dead"`). Module 3 sets `"incapacitated"`; death is implemented by **removing** the agent, so there’s no `"dead"` left in the list.
- No central “is this agent in bounds / valid / colliding?” check; each module uses location as needed (e.g. Module 2 maps `(x,y)` to graph nodes, Module 5 checks `agent.get("location") == event.location` when location is a string).

### Map bounds

- **Current:** There are **no** map bounds in the codebase.
  - Colony state has no `bounds` or `map_width` / `map_height`.
  - The colony graph (Module 2) has **node positions** (e.g. section_alpha at (0,0), section_beta at (20,0)), but those are used only to map `(x,y)` to the nearest node and for heuristics; they don’t define “in bounds” for agents.
  - So agents can be initialized or updated to any `(x, y)` (e.g. (-1000, 1000)) and validation will pass.

So: **no**, there are currently no map bounds that an agent “must be in bounds” for.

### Collision rules

- **Current:** There are **no** collision rules.
  - Multiple agents can have the same `(x, y)` or the same node ID.
  - No check that “two agents can’t occupy the same cell” or “same node has a capacity of 1.”
  - Pathfinding (Module 2) doesn’t treat “another agent at (x,y)” as blocking.

So: **no** collision rules between agents.

### Variable speeds

- **Schema:** The agent schema in Module 1 docstring lists optional `"speed": float` (movement speed multiplier) and `"efficiency": float`.
- **Usage:** Module 2’s task planner and pathfinding **do not** use `speed`. Travel cost is the same for all agents (graph edge cost or Euclidean distance). So speed is **documented but unused**; there are no variable speeds in gameplay logic today.

---

## 2. Summary Table

| Topic              | Exists? | Where it lives / notes                                      |
|--------------------|--------|-------------------------------------------------------------|
| Agent location     | Yes    | `agent["location"]`: `(x,y)` or node ID string             |
| Location validation| Yes    | Type/shape + collision (no two agents same location)       |
| Map bounds         | No     | Procedural tiles; no bounds (deterministic from seed)      |
| Collision rules    | Yes    | One agent per location (add_agent, update_agent, validate_state) |
| Variable speeds    | Schema only | Optional `speed` field; not used in Module 2           |

---

## 3. Should You Add These? (Recommendations)

### Map bounds

- **If** you want “agents must be in bounds”:
  - Define a single notion of “map” (e.g. grid `0..width-1`, `0..height-1`, or “location must be one of those graph nodes”).
  - Add it either in **Module 1** (e.g. `ColonyState` has optional `map_bounds` and `is_in_bounds(x,y)` / `is_valid_location(loc)`) or in a small game-config layer that Module 1 reads.
  - In **Module 1** you could then:
    - In `validate_agent()`, if bounds are set, reject agents with `location` outside bounds.
    - In `update_agent()` (or a dedicated `set_agent_location()`), optionally reject out-of-bounds updates.
  - Keeps “what is valid” in one place and prevents other modules from putting agents at (-1000, 1000) if you validate on add/update.

### Collision rules

- **If** you want “no two agents in the same place” (or “at most N per cell”):
  - You need a rule like: “when setting or updating location, check that no other agent (or not more than N) has that location.”
  - That fits in **Module 1** as part of adding/updating agents (e.g. in `add_agent()` and in whatever updates `location`), so the rest of the game can assume “state respects collisions.”
  - Alternatively you can enforce it only when **moving** (e.g. in the game engine or a movement helper), but then the “single source of truth” for “is this state valid” is split; putting it in Module 1 keeps state consistent.

### Variable speeds

- **If** you want different agents to have different movement speed:
  - **Module 2** is the right place: when computing “cost for agent A to go to task T,” multiply (or divide) the path cost by `agent.get("speed", 1.0)` (or similar). So faster agents have lower effective cost.
  - You don’t need to change Module 1 beyond already having `speed` in the schema; you only need to **use** that field in the task planner / pathfinding (Module 2).

---

## 4. Where to implement (before “moving onto module 2”)

You said “before I move onto module 2” — if you mean “before continuing with other modules,” then:

- **Map bounds:** Add in **Module 1** (optional `map_bounds`, validation in `validate_agent()` and when updating location). Optionally a small “game config” that defines width/height or valid node set.
- **Collision rules:** Add in **Module 1** (when adding or updating an agent’s location, check no (or limited) other agent has that location).
- **Variable speeds:** Add in **Module 2** (use `agent.get("speed", 1.0)` when computing travel cost for that agent).

If you tell me which of these you want (e.g. “bounds + collisions in Module 1, speeds in Module 2”), I can outline concrete function signatures and where to hook them (e.g. `ColonyState.__init__(..., map_bounds=None)`, `set_agent_location(agent_id, new_location)` with bounds and collision checks, and in Module 2 a `_travel_cost_for_agent(agent, path_cost)` that uses speed).
