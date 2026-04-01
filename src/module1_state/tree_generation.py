"""
Sparse tree placement for multi-floor wood harvesting.

Design (explicit): harder difficulty → fewer candidate trees (rarer wood on the map);
easier → more trees. This is implemented via land_fraction targets and RNG filtering.

Trees are stored as integer pairs [x, y] in ColonyState.world_trees (JSON-serializable).

When initial scatter is too sparse, ``maybe_spawn_progression_tree`` can add one tree per
turn (stochastic) on grass/dirt until ``wood + len(trees) >= wood_quota``.
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

from src.module1_state.colony_state import ColonyState

# Tunables: easy has ~2.2x the tree density of hard on the same map.
_DIFFICULTY_TREE_FRACTION = {
    "easy": 0.0020,
    "normal": 0.0010,
    "hard": 0.00045,
}

# Tillable / wooded ground (grass per UX; dirt included so forest edges still work).
_GROWABLE_TERRAINS = frozenset({"grass", "dirt"})


def land_tree_density(difficulty: str) -> float:
    """Fraction of passable land tiles that may receive a tree (before carryover multipliers)."""
    d = (difficulty or "normal").lower()
    return _DIFFICULTY_TREE_FRACTION.get(d, _DIFFICULTY_TREE_FRACTION["normal"])


def generate_world_trees(
    state: ColonyState,
    world_min_x: int,
    world_max_x: int,
    world_min_y: int,
    world_max_y: int,
    *,
    tree_density_multiplier: float = 1.0,
    max_trees_cap: int = 400,
) -> List[List[int]]:
    """
    Deterministic sparse tree scatter from world_seed, floor_index, difficulty.

    Avoids water/non-passable tiles, agent positions, and infrastructure center tiles
    (best-effort via state.infrastructure resource_station centers).
    """
    mult = max(0.15, float(tree_density_multiplier))
    base = land_tree_density(state.difficulty) * mult
    d_key = {"easy": 1, "normal": 2, "hard": 3}.get(
        (state.difficulty or "normal").lower(), 2
    )
    rng = random.Random(
        int(state.world_seed) + 1337 * int(getattr(state, "floor_index", 1)) + 17 * d_key
    )

    blocked = _blocked_positions(state, world_min_x, world_max_x, world_min_y, world_max_y)
    candidates: List[Tuple[int, int]] = []
    for x in range(world_min_x, world_max_x):
        for y in range(world_min_y, world_max_y):
            if (x, y) in blocked:
                continue
            tile = state.get_tile_at(x, y)
            if not tile.get("passable", True):
                continue
            if tile.get("terrain") == "water":
                continue
            candidates.append((x, y))

    if not candidates:
        return []

    target = int(len(candidates) * base)
    target = max(3, min(max_trees_cap, target))
    rng.shuffle(candidates)
    trees: List[List[int]] = []
    for x, y in candidates:
        if len(trees) >= target:
            break
        trees.append([int(x), int(y)])
    return trees


def _blocked_positions(
    state: ColonyState,
    wx0: int,
    wx1: int,
    wy0: int,
    wy1: int,
) -> set:
    blocked: set = set()
    for a in state.agents:
        loc = a.get("location")
        if isinstance(loc, (list, tuple)) and len(loc) == 2:
            blocked.add((int(loc[0]), int(loc[1])))
    for _sid, info in (state.infrastructure or {}).items():
        if not isinstance(info, dict):
            continue
        if info.get("kind") != "resource_station":
            continue
        c = info.get("center")
        size = int(info.get("size", 2))
        if isinstance(c, (list, tuple)) and len(c) == 2:
            cx, cy = int(c[0]), int(c[1])
            half = size // 2
            for dx in range(-half, half + 1):
                for dy in range(-half, half + 1):
                    blocked.add((cx + dx, cy + dy))
    return blocked


def base_wood_quota(difficulty: str, floor_index: int) -> float:
    """Default wood target for a floor before carryover adjustments."""
    d = (difficulty or "normal").lower()
    base = {"easy": 6.0, "normal": 8.0, "hard": 10.0}.get(d, 8.0)
    return base + 0.5 * max(0, int(floor_index) - 1)


def maybe_spawn_progression_tree(
    state: ColonyState,
    *,
    rng: Optional[random.Random] = None,
    spawn_probability: float = 0.42,
    max_attempts: int = 48,
) -> bool:
    """
    If the colony cannot reach ``wood_quota`` even by harvesting every remaining tree,
    try to plant one extra tree on a random grass/dirt tile (slow drip, ~spawn_probability / turn).

    Returns True if a tree was added.
    """
    wq = float(getattr(state, "wood_quota", 0.0) or 0.0)
    if wq <= 0.0:
        return False
    wood = float(state.resources.get("wood", 0.0))
    if wood >= wq:
        return False
    trees = state.world_trees or []
    if wood + float(len(trees)) >= wq:
        return False

    if rng is None:
        rng = random.Random(
            int(state.world_seed) + int(state.turn_number) * 1009 + 7331
        )
    if rng.random() > float(spawn_probability):
        return False

    wx0 = int(getattr(state, "world_min_x", -25))
    wx1 = int(getattr(state, "world_max_x", 25))
    wy0 = int(getattr(state, "world_min_y", -25))
    wy1 = int(getattr(state, "world_max_y", 25))

    blocked = _blocked_positions(state, wx0, wx1, wy0, wy1)
    occupied_trees = {
        (int(t[0]), int(t[1])) for t in trees if len(t) >= 2
    }

    candidates: List[Tuple[int, int]] = []
    for x in range(wx0, wx1):
        for y in range(wy0, wy1):
            if (x, y) in blocked or (x, y) in occupied_trees:
                continue
            tile = state.get_tile_at(x, y)
            if not tile.get("passable", True):
                continue
            if tile.get("terrain") not in _GROWABLE_TERRAINS:
                continue
            candidates.append((x, y))

    if not candidates:
        return False

    rng.shuffle(candidates)
    for (x, y) in candidates[:max_attempts]:
        state.world_trees = list(trees) + [[int(x), int(y)]]
        return True
    return False


def try_harvest_trees(state: ColonyState, coords: Sequence[Tuple[int, int]]) -> int:
    """
    For each (x,y) in coords, if that tile is still a tree, grant +1 wood and remove tree.

    Returns number of trees harvested this call.
    """
    if not coords:
        return 0
    tree_set = {tuple(t) for t in state.world_trees if len(t) >= 2}
    if not tree_set:
        return 0
    harvested = 0
    new_trees: List[List[int]] = []
    consumed: set = set()
    for xy in coords:
        t = (int(xy[0]), int(xy[1]))
        if t in tree_set and t not in consumed:
            consumed.add(t)
            harvested += 1
    if harvested == 0:
        return 0
    for t in state.world_trees:
        if len(t) < 2:
            continue
        tp = (int(t[0]), int(t[1]))
        if tp not in consumed:
            new_trees.append([tp[0], tp[1]])
    state.world_trees = new_trees
    w = float(state.resources.get("wood", 0.0))
    state.resources["wood"] = w + float(harvested)
    return harvested
