# Module 4: Minimax, Alpha-Beta, and MCTS

## The Setting

The **AI Director** chooses which disruptive event to apply each turn. The goal is to **maximize challenge** to the player (make the colony state worse for them). We can model this as a two-player game:

- **Director (maximizer):** Picks an event. Wants to maximize a "challenge" score.
- **Player (minimizer):** Responds (e.g. next turn they assign tasks, repair, etc.). We model their best response as minimizing the challenge score.

So we have a **game tree**: Director move → Player response → Director move → … and we search this tree to pick the best event **now**.

---

## Minimax

**Idea:** Assume both sides play optimally. The Director maximizes the score, the Player minimizes it.

- **Max node (Director):** Value = max over all events of (value of resulting state after Player responds optimally).
- **Min node (Player):** Value = min over all possible responses of (value of resulting state after Director responds optimally).
- **Terminal / depth limit:** Value = evaluate(state) — a "challenge" score (higher = worse for player = better for Director).

**Recursion:**

- `max_value(state, depth)` = if depth 0 then evaluate(state), else max over events of `min_value(simulate_event(state, event), depth-1)`.
- `min_value(state, depth)` = if depth 0 then evaluate(state), else min over player responses of `max_value(simulate_response(state, response), depth-1)`.

**To choose an event:** At the root (Director’s turn), compute the value for each event, then **pick the event that has the highest value** (i.e. the one that leads to the best outcome for the Director after the player’s best response).

**Guarantee:** With exact evaluation and full search, Minimax gives the **optimal** event assuming optimal play from both sides.

---

## Alpha-Beta Pruning

**Idea:** Same as Minimax, but we **prune** branches that cannot change the final decision.

- **Alpha (α):** Best value the maximizer (Director) can guarantee so far along the current path.
- **Beta (β):** Best value the minimizer (Player) can guarantee so far (lowest value they can force).

When we’re at a **min node** and we know the minimizer can already get a value ≤ β, we don’t need to look at any branch that would give the maximizer more than β (the min player would never allow that branch). So we **prune** (stop expanding) when **α ≥ β**.

**Effect:** We get the **same result** as Minimax (same chosen event and value), but we often explore **fewer nodes**, so it’s faster.

**Ordering:** If we consider good moves first (e.g. events that hurt the player most), we prune more and Alpha-Beta is even more efficient.

---

## MCTS (Monte Carlo Tree Search)

**Idea:** Instead of evaluating states with a heuristic, we **simulate** random playouts to the end (or for a fixed number of steps) and use the **average outcome** of those playouts to decide which move is best.

**Four phases (repeated many times):**

1. **Selection:** From the root, walk down the tree by choosing children with a **UCB1** (or similar) formula that balances exploitation (good average reward) and exploration (less-visited nodes), until we hit a node that is not fully expanded.
2. **Expansion:** Add one (or more) child for an unexpanded action (e.g. a new event we haven’t tried from that state).
3. **Simulation (rollout):** From the new node, play **randomly** (or with a simple policy) until a terminal condition or depth limit; record the outcome (e.g. challenge score or win/loss).
4. **Backpropagation:** Update the statistics (visit count, total reward) along the path from the new node back to the root.

After many iterations, we choose the **root action** (event) with the **highest visit count** (or highest average reward). So MCTS uses **random play** to estimate which event is best, instead of a fixed evaluation function.

**Pros:** Can handle large/branching trees, doesn’t require a perfect evaluation function, good for games with randomness or complex outcomes.  
**Cons:** No optimality guarantee; needs many iterations to be good.

---

## Summary Table

| Algorithm    | Role in Module 4                         | Optimal? | Memory/speed notes        |
|-------------|-------------------------------------------|----------|----------------------------|
| **Minimax** | Choose event that maximizes challenge after player’s best response | Yes (with exact eval) | Explores full tree to depth |
| **Alpha-Beta** | Same as Minimax, with pruning so we skip branches that can’t change the decision | Yes (same as Minimax) | Same result, often fewer nodes |
| **MCTS**    | Use random playouts to estimate value of each event; pick most visited or best average | No (heuristic) | Good for large/complex trees |

In our implementation, **Minimax** (and Alpha-Beta) use a **challenge score** over colony state and a **simple model of player responses** (e.g. which resource they recover). **MCTS** would use the same state representation but score nodes by averaging outcomes of random simulations instead of a closed-form evaluation.
