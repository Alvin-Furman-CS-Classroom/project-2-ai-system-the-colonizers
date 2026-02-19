"""
Procedurally generated tiles with circle-based biome generation.

Uses radial distance from biome centers to create circular, organic-looking biomes
instead of rectangular chunks. Neighbors influence tile type for smooth transitions.
"""

from typing import Dict, Any, Optional, Tuple
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

# Neighbor directions (8-connected for smoother transitions)
_NEIGHBORS = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]

# Neighbor influence: how much neighbors affect tile type
_NEIGHBOR_INFLUENCE = 0.80

# Base randomness: chance of ignoring neighbors
_BASE_RANDOMNESS = 0.10


def _pseudo_random(x: int, y: int, seed: int, step: int = 0) -> float:
    """Deterministic pseudo-random float [0.0, 1.0) based on coordinates and seed."""
    h = hash((seed, x, y, step)) & 0x7FFFFFFF
    return (h % 10000) / 10000.0


def _get_biome_center(x: int, y: int, seed: int) -> Tuple[int, int]:
    """Get the biome center for a given coordinate using circular regions."""
    # Use larger regions for circular biomes
    region_size = 8
    region_x = x // region_size
    region_y = y // region_size
    # Biome center is offset within region based on seed
    offset_x = int(_pseudo_random(region_x, region_y, seed, 0) * region_size * 0.6)
    offset_y = int(_pseudo_random(region_x, region_y, seed, 1) * region_size * 0.6)
    center_x = region_x * region_size + region_size // 2 + offset_x - region_size // 2
    center_y = region_y * region_size + region_size // 2 + offset_y - region_size // 2
    return (center_x, center_y)


def _get_base_terrain(x: int, y: int, seed: int) -> str:
    """Get base terrain type based on distance from biome center (circular)."""
    center_x, center_y = _get_biome_center(x, y, seed)
    dist = math.hypot(x - center_x, y - center_y)
    
    # Use distance and angle to determine terrain
    angle = math.atan2(y - center_y, x - center_x) if dist > 0 else 0
    # Combine distance and angle for variety
    h = hash((seed, int(dist // 2), int(angle * 10))) & 0x7FFFFFFF
    terrain_index = h % len(TERRAIN_TYPES)
    return TERRAIN_TYPES[terrain_index]


def get_tile(x: int, y: int, seed: int = 0) -> Dict[str, Any]:
    """
    Return procedural tile data for world coordinates (x, y).
    
    Uses circle-based biome generation: tiles are assigned based on distance from
    biome centers, creating circular, organic biomes. Neighbors influence final
    type for smooth transitions.

    Args:
        x: World x coordinate (any integer).
        y: World y coordinate (any integer).
        seed: World seed for variety (default 0).

    Returns:
        Dictionary with:
        - "terrain": str — one of "grass", "water", "rock", "sand", "dirt"
        - "passable": bool — whether agents can occupy this tile (water is not passable)
    """
    ix, iy = int(x), int(y)
    cache_key = (ix, iy, seed)
    
    # Check cache first
    if cache_key in _tile_cache:
        terrain = _tile_cache[cache_key]
    else:
        # Get base terrain from circular biome
        base_terrain = _get_base_terrain(ix, iy, seed)
        
        # Check neighbors for smoothing
        neighbor_counts: Dict[str, int] = {}
        for dx, dy in _NEIGHBORS:
            nx, ny = ix + dx, iy + dy
            neighbor_key = (nx, ny, seed)
            if neighbor_key in _tile_cache:
                neighbor_terrain = _tile_cache[neighbor_key]
                neighbor_counts[neighbor_terrain] = neighbor_counts.get(neighbor_terrain, 0) + 1
        
        # Determine final terrain: blend base terrain with neighbors
        rand_val = _pseudo_random(ix, iy, seed, 0)
        if neighbor_counts and rand_val > _BASE_RANDOMNESS:
            total_neighbors = sum(neighbor_counts.values())
            if total_neighbors > 0:
                most_common = max(neighbor_counts.items(), key=lambda x: x[1])[0]
                # High chance to match neighbors, but also consider base terrain
                if _pseudo_random(ix, iy, seed, 2) < _NEIGHBOR_INFLUENCE:
                    terrain = most_common
                else:
                    terrain = base_terrain
            else:
                terrain = base_terrain
        else:
            terrain = base_terrain
        
        # Cache the result
        _tile_cache[cache_key] = terrain
    
    passable = terrain != TERRAIN_WATER
    return {
        "terrain": terrain,
        "passable": passable,
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
