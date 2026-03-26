"""
Procedurally generated tiles with blob-based lake generation.

Creates organic blob-like lakes with sandy beaches around them, and grass everywhere else.
Lakes are generated as irregular blobs with smooth edges.
"""

from typing import Dict, Any, Optional, Tuple, List
import math

# Terrain types
TERRAIN_GRASS = "grass"
TERRAIN_WATER = "water"
TERRAIN_ROCK = "rock"
TERRAIN_SAND = "sand"
TERRAIN_DIRT = "dirt"

TERRAIN_TYPES = [TERRAIN_GRASS, TERRAIN_WATER, TERRAIN_ROCK, TERRAIN_SAND, TERRAIN_DIRT]

# Cache for generated tiles
_tile_cache: Dict[Tuple[int, int, int], str] = {}

# Cache for lake blob centers (generated once per seed+difficulty)
_lake_blobs_cache: Dict[Tuple[int, str], List[Tuple[int, int, float]]] = {}

def clear_tile_cache():
    """Clear the tile cache (useful when generating a new map with a different seed)."""
    global _tile_cache, _lake_blobs_cache
    _tile_cache.clear()
    _lake_blobs_cache.clear()

# Neighbor directions (8-connected for smoother transitions)
_NEIGHBORS = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]


def _pseudo_random(x: int, y: int, seed: int, step: int = 0) -> float:
    """Deterministic pseudo-random float [0.0, 1.0) based on coordinates and seed."""
    h = hash((seed, x, y, step)) & 0x7FFFFFFF
    return (h % 10000) / 10000.0


def _generate_lake_blobs(seed: int, difficulty: str) -> List[Tuple[int, int, float]]:
    """
    Generate lake blob centers and sizes based on seed and difficulty.
    Returns list of (center_x, center_y, radius) tuples.
    """
    cache_key = (int(seed), str(difficulty))
    if cache_key in _lake_blobs_cache:
        return _lake_blobs_cache[cache_key]

    # Generate cohesive lakes by clustering many overlapping blobs around lake hubs.
    hub_counts = {"easy": 2, "normal": 3, "hard": 4}
    blobs_per_hub = {"easy": (3, 5), "normal": (4, 6), "hard": (5, 8)}
    radius_ranges = {"easy": (4.0, 10.0), "normal": (6.0, 13.0), "hard": (7.0, 15.0)}

    num_hubs = hub_counts.get(difficulty, 3)
    min_blobs, max_blobs = blobs_per_hub.get(difficulty, (4, 6))
    min_radius, max_radius = radius_ranges.get(difficulty, (6.0, 13.0))
    world_span = 250  # Supports larger maps up to 250x250

    blobs: List[Tuple[int, int, float]] = []

    # Always place one cohesive lake cluster in a seed-randomized central zone
    # so small maps reliably contain visible water features without fixing at origin.
    core_blob_count = max(3, min_blobs)
    core_base_radius = (min_radius + max_radius) * 0.45
    core_center_x = int(_pseudo_random(seed, 70000, 301) * 24 - 12)
    core_center_y = int(_pseudo_random(seed, 70000, 302) * 24 - 12)
    for local_idx in range(core_blob_count):
        step = 50000 + local_idx
        angle = _pseudo_random(seed, step, 201) * math.tau
        offset = _pseudo_random(seed, step, 202) * 6.0
        cx = int(round(core_center_x + math.cos(angle) * offset))
        cy = int(round(core_center_y + math.sin(angle) * offset))
        radius = core_base_radius * (0.9 + _pseudo_random(seed, step, 203) * 0.35)
        blobs.append((cx, cy, radius))

    hub_centers: List[Tuple[int, int]] = []
    min_hub_spacing = {"easy": 42.0, "normal": 50.0, "hard": 58.0}.get(difficulty, 50.0)
    min_from_core = 34.0

    for hub_idx in range(num_hubs):
        hub_x, hub_y = 0, 0
        chosen = False
        # Try multiple deterministic candidates and keep the first that is well-spaced.
        for attempt in range(12):
            step = hub_idx * 200 + attempt
            cand_x = int(_pseudo_random(seed, step, 100) * world_span - world_span // 2)
            cand_y = int(_pseudo_random(seed, step, 101) * world_span - world_span // 2)
            if math.hypot(cand_x - core_center_x, cand_y - core_center_y) < min_from_core:
                continue
            if any(math.hypot(cand_x - hx, cand_y - hy) < min_hub_spacing for hx, hy in hub_centers):
                continue
            hub_x, hub_y = cand_x, cand_y
            chosen = True
            break
        if not chosen:
            # Fallback candidate if spacing constraints cannot be met.
            hub_x = int(_pseudo_random(seed, hub_idx, 100) * world_span - world_span // 2)
            hub_y = int(_pseudo_random(seed, hub_idx, 101) * world_span - world_span // 2)
        hub_centers.append((hub_x, hub_y))
        blob_count = min_blobs + int(_pseudo_random(seed, hub_idx, 102) * (max_blobs - min_blobs + 1))
        for local_idx in range(blob_count):
            step = hub_idx * 1000 + local_idx
            angle = _pseudo_random(seed, step, 103) * math.tau
            offset = 2.0 + _pseudo_random(seed, step, 104) * 14.0
            cx = int(round(hub_x + math.cos(angle) * offset))
            cy = int(round(hub_y + math.sin(angle) * offset))
            radius = min_radius + _pseudo_random(seed, step, 105) * (max_radius - min_radius)
            radius *= 0.85 + _pseudo_random(seed, step, 106) * 0.35
            blobs.append((cx, cy, radius))

    _lake_blobs_cache[cache_key] = blobs
    return blobs


def _distance_to_blob(x: int, y: int, blob: Tuple[int, int, float], seed: int = 0) -> float:
    """Calculate signed distance to an irregular (warped) blob edge."""
    center_x, center_y, radius = blob
    dx = x - center_x
    dy = y - center_y

    # Deterministic anisotropy per blob center to avoid perfect circles.
    angle_seed = _pseudo_random(center_x, center_y, seed, 401) * math.tau
    cos_a = math.cos(angle_seed)
    sin_a = math.sin(angle_seed)
    rx = dx * cos_a + dy * sin_a
    ry = -dx * sin_a + dy * cos_a
    stretch = 0.75 + _pseudo_random(center_x, center_y, seed, 402) * 0.7  # [0.75, 1.45]
    squeeze = 0.75 + _pseudo_random(center_x, center_y, seed, 403) * 0.7  # [0.75, 1.45]
    ell_dist = math.hypot(rx / stretch, ry / squeeze)

    # Angular shoreline warp to create oblong/lobed natural edges.
    theta = math.atan2(dy, dx) if (dx or dy) else 0.0
    warp1 = (_pseudo_random(center_x, center_y, seed, 404) - 0.5) * 0.7
    warp2 = (_pseudo_random(center_x, center_y, seed, 405) - 0.5) * 0.45
    phase1 = _pseudo_random(center_x, center_y, seed, 406) * math.tau
    phase2 = _pseudo_random(center_x, center_y, seed, 407) * math.tau
    warped_radius = radius * (
        1.0
        + warp1 * math.sin(2.0 * theta + phase1)
        + warp2 * math.sin(3.0 * theta + phase2)
    )
    warped_radius = max(radius * 0.55, warped_radius)

    return ell_dist - warped_radius


def _get_base_terrain(x: int, y: int, seed: int, difficulty: str) -> str:
    """
    Get base terrain type using a clean lake-union model:
    - water: inside ANY lake blob
    - sand: outside water but within beach width of lake edge
    - grass: everything else
    """
    blobs = _generate_lake_blobs(seed, difficulty)

    # Hard rule: if point is inside any blob, it is water.
    # This prevents sand strips appearing inside connected lake bodies.
    inside_any = False
    min_outer_dist = float("inf")
    for blob in blobs:
        dist_to_edge = _distance_to_blob(x, y, blob, seed=seed)
        if dist_to_edge < 0:
            inside_any = True
            break
        if dist_to_edge < min_outer_dist:
            min_outer_dist = dist_to_edge

    if inside_any:
        return TERRAIN_WATER

    # Outside lakes: classify beach ring then grass.
    if min_outer_dist < 3.0:
        return TERRAIN_SAND
    return TERRAIN_GRASS


def get_tile(x: int, y: int, seed: int = 0, difficulty: str = "normal") -> Dict[str, Any]:
    """
    Return procedural tile data for world coordinates (x, y).
    
    Uses blob-based lake generation: creates organic blob-like lakes with sandy beaches
    around them, and grass everywhere else. Lakes are irregular shapes with smooth edges.

    Args:
        x: World x coordinate (any integer).
        y: World y coordinate (any integer).
        seed: World seed for variety (default 0).
        difficulty: Game difficulty affecting number and size of lakes - "easy" (fewer/smaller),
                   "normal" (moderate), "hard" (more/larger).

    Returns:
        Dictionary with:
        - "terrain": str — one of "grass", "water", "rock", "sand", "dirt"
        - "passable": bool — whether agents can occupy this tile (all passable)
        - "move_speed": float — movement speed multiplier (water is slower)
    """
    ix, iy = int(x), int(y)
    cache_key = (ix, iy, seed)
    
    # Check cache first
    if cache_key in _tile_cache:
        terrain = _tile_cache[cache_key]
    else:
        # Use order-independent classification to avoid striping artifacts.
        terrain = _get_base_terrain(ix, iy, seed, difficulty)
        _tile_cache[cache_key] = terrain
    
    passable = True  # All tiles passable
    # Water is passable but slow (0.2x speed); other terrain normal speed
    move_speed = 0.2 if terrain == TERRAIN_WATER else 1.0
    return {
        "terrain": terrain,
        "passable": passable,
        "move_speed": move_speed,
    }


def get_tile_decor(x: int, y: int, seed: int = 0) -> Optional[str]:
    """
    Return optional decoration for tile (x, y) based on terrain.
    Trees on grass, rocks in water, cacti on sand, etc.
    ~5% of eligible tiles get a decoration (lower frequency).
    Decorations are impassable obstacles.
    """
    tile = get_tile(x, y, seed)
    terrain = tile["terrain"]
    ix, iy = int(x), int(y)
    state = _state_from_coords(seed + 1, ix, iy)
    state = _lcg_next(state)
    if (state % 20) != 0:  # 5% chance (was 20%)
        return None
    decor_map = {
        TERRAIN_GRASS: "tree",
        TERRAIN_WATER: "rock",
        TERRAIN_SAND: "cactus",
        TERRAIN_ROCK: "boulder",
        TERRAIN_DIRT: "bush",
    }
    return decor_map.get(terrain)
