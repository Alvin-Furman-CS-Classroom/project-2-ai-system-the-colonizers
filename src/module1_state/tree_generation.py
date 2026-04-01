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

# Land fraction cap for tree placement — sparse; large maps get more trees only via area×density.
_DIFFICULTY_TREE_FRACTION = {
    "easy": 0.0010,
    "normal": 0.00052,
    "hard": 0.00024,
}

# Tillable / wooded ground (grass per UX; dirt included so forest edges still work).
_GROWABLE_TERRAINS = frozenset({"grass", "dirt"})

# Upper bound on total trees (initial fill + viewport/top-ups); avoids runaway lists on huge maps.
GLOBAL_TREE_CAP = 2000

# Minimum trees in the current camera viewport (see ``ensure_viewport_trees``); keep sparse.
VIEWPORT_TREES_K = {"easy": 1, "normal": 1, "hard": 1}


def _is_compact_world(world_min_x: int, world_max_x: int, world_min_y: int, world_max_y: int) -> bool:
    """Small/Medium presets (e.g. 40×40, 50×50): max side length ≤ 55 tiles."""
    span_w = max(0, int(world_max_x) - int(world_min_x))
    span_h = max(0, int(world_max_y) - int(world_min_y))
    return max(span_w, span_h) <= 55


def min_trees_for_candidate_count(
    n_candidates: int, difficulty: str, *, large_world: bool = False
) -> int:
    """Sparse floors; ``large_world`` uses smaller minimums for density-driven big maps."""
    if n_candidates <= 0:
        return 0
    d = (difficulty or "normal").lower()
    if large_world:
        div = {"easy": 450, "normal": 600, "hard": 800}.get(d, 600)
        floor = {"easy": 5, "normal": 4, "hard": 3}.get(d, 4)
    else:
        div = {"easy": 320, "normal": 420, "hard": 550}.get(d, 420)
        floor = {"easy": 6, "normal": 5, "hard": 4}.get(d, 5)
    chunk = n_candidates // div
    return max(3, min(floor + chunk, GLOBAL_TREE_CAP, n_candidates))


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
    max_trees_cap: int = GLOBAL_TREE_CAP,
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
    span_w = max(0, int(world_max_x) - int(world_min_x))
    span_h = max(0, int(world_max_y) - int(world_min_y))
    area = span_w * span_h
    compact = _is_compact_world(world_min_x, world_max_x, world_min_y, world_max_y)
    wq = float(getattr(state, "wood_quota", 8.0) or 8.0)
    half_quota_trees = max(3, int(round(0.5 * wq)))

    # Large worlds: avoid O(area) nested loops at floor load; sample valid grass/land tiles.
    if area > 12000:
        approx_candidates = max(1, area - len(blocked))
        min_n = min_trees_for_candidate_count(
            approx_candidates, state.difficulty, large_world=True
        )
        target = int(approx_candidates * base)
        target = max(min_n, 3, min(max_trees_cap, target))
        trees: List[List[int]] = []
        occ = set(blocked)
        tries = 0
        max_tries = target * 35 + 1600
        while len(trees) < target and tries < max_tries:
            tries += 1
            x = rng.randrange(world_min_x, world_max_x)
            y = rng.randrange(world_min_y, world_max_y)
            if (x, y) in occ:
                continue
            tile = state.get_tile_at(x, y)
            if not tile.get("passable", True):
                continue
            if tile.get("terrain") == "water":
                continue
            trees.append([int(x), int(y)])
            occ.add((x, y))
        return trees

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

    target_density = int(len(candidates) * base)
    if compact:
        # Small/Medium: aim for ~50% of wood quota in harvestable trees, capped by density.
        target = min(half_quota_trees, target_density, max_trees_cap)
        target = max(3, target)
    else:
        min_n = min_trees_for_candidate_count(
            len(candidates), state.difficulty, large_world=True
        )
        target = max(min_n, 3, min(max_trees_cap, target_density))
    rng.shuffle(candidates)
    trees = []
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

    span_w = max(0, wx1 - wx0)
    span_h = max(0, wy1 - wy0)
    if span_w <= 0 or span_h <= 0:
        return False

    # Large worlds: avoid O(span_w * span_h) Python loops every spawn tick — sample random cells.
    sample_budget = max(max_attempts, min(512, max(96, max_attempts * 8)))
    small_map = span_w * span_h <= 3600

    if small_map:
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

    for _ in range(sample_budget):
        x = rng.randrange(wx0, wx1)
        y = rng.randrange(wy0, wy1)
        if (x, y) in blocked or (x, y) in occupied_trees:
            continue
        tile = state.get_tile_at(x, y)
        if not tile.get("passable", True):
            continue
        if tile.get("terrain") not in _GROWABLE_TERRAINS:
            continue
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


def _trees_in_rect(
    trees: List[List[int]], x0: int, y0: int, x1: int, y1: int
) -> int:
    """Count trees with integer coords in [x0,x1) × [y0,y1)."""
    n = 0
    for t in trees or []:
        if len(t) < 2:
            continue
        x, y = int(t[0]), int(t[1])
        if x0 <= x < x1 and y0 <= y < y1:
            n += 1
    return n


def ensure_viewport_trees(
    state: ColonyState,
    *,
    view_x0: int,
    view_y0: int,
    view_x1: int,
    view_y1: int,
    k: int,
    margin_tiles: int = 5,
    rng: Optional[random.Random] = None,
    global_cap: int = GLOBAL_TREE_CAP,
    sample_tries_per_need: int = 64,
) -> int:
    """
    If fewer than ``k`` trees fall inside the viewport rectangle, add trees by sampling
    an expanded band (viewport ± margin), without scanning the full map.

    Rectangle bounds are half-open [x0,x1), [y0,y1) in world tile coordinates.
    Returns the number of trees added.
    """
    if k <= 0:
        return 0
    wx0 = int(getattr(state, "world_min_x", -25))
    wx1 = int(getattr(state, "world_max_x", 25))
    wy0 = int(getattr(state, "world_min_y", -25))
    wy1 = int(getattr(state, "world_max_y", 25))
    if wx1 <= wx0 or wy1 <= wy0:
        return 0

    trees = list(state.world_trees or [])
    have = _trees_in_rect(trees, view_x0, view_y0, view_x1, view_y1)
    need = k - have
    if need <= 0:
        return 0
    if len(trees) >= global_cap:
        return 0

    if rng is None:
        rng = random.Random(
            int(state.world_seed)
            + int(state.turn_number) * 7919
            + int(getattr(state, "floor_index", 1)) * 503
            + 6621
        )

    ex0 = max(wx0, view_x0 - margin_tiles)
    ex1 = min(wx1, view_x1 + margin_tiles)
    ey0 = max(wy0, view_y0 - margin_tiles)
    ey1 = min(wy1, view_y1 + margin_tiles)
    if ex1 <= ex0 or ey1 <= ey0:
        return 0

    blocked = _blocked_positions(state, wx0, wx1, wy0, wy1)
    occupied = {(int(t[0]), int(t[1])) for t in trees if len(t) >= 2}
    added = 0
    tries = 0
    max_tries = max(sample_tries_per_need * need, sample_tries_per_need * 3)

    while added < need and len(trees) < global_cap and tries < max_tries:
        tries += 1
        x = rng.randrange(ex0, ex1)
        y = rng.randrange(ey0, ey1)
        if (x, y) in blocked or (x, y) in occupied:
            continue
        tile = state.get_tile_at(x, y)
        if not tile.get("passable", True):
            continue
        if tile.get("terrain") not in _GROWABLE_TERRAINS:
            continue
        trees.append([int(x), int(y)])
        occupied.add((x, y))
        added += 1

    if added:
        state.world_trees = trees
    return added
