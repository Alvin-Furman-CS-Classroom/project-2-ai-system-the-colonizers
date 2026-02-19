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

# Cache for lake blob centers (generated once per seed)
_lake_blobs_cache: Dict[int, List[Tuple[int, int, float]]] = {}  # seed -> [(x, y, radius), ...]

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
    if seed in _lake_blobs_cache:
        return _lake_blobs_cache[seed]
    
    # Number of lakes based on difficulty (more lakes = more water)
    lake_counts = {
        "easy": 3,    # Fewer, smaller lakes
        "normal": 5,  # Moderate lakes
        "hard": 8     # More, larger lakes
    }
    num_lakes = lake_counts.get(difficulty, 5)
    
    # Lake size ranges (radius in tiles)
    size_ranges = {
        "easy": (3.0, 6.0),      # Smaller lakes
        "normal": (4.0, 8.0),   # Medium lakes
        "hard": (5.0, 10.0)     # Larger lakes
    }
    min_radius, max_radius = size_ranges.get(difficulty, (4.0, 8.0))
    
    blobs: List[Tuple[int, int, float]] = []
    world_size = 50  # WORLD_WIDTH/HEIGHT
    
    for i in range(num_lakes):
        # Generate random blob center
        center_x = int(_pseudo_random(seed, i, 0) * world_size - world_size // 2)
        center_y = int(_pseudo_random(seed, i, 1) * world_size - world_size // 2)
        
        # Generate random radius with some variation
        base_radius = min_radius + _pseudo_random(seed, i, 2) * (max_radius - min_radius)
        # Add some irregularity to radius for organic shape
        radius_variation = 0.7 + _pseudo_random(seed, i, 3) * 0.6  # 0.7 to 1.3 multiplier
        radius = base_radius * radius_variation
        
        blobs.append((center_x, center_y, radius))
    
    _lake_blobs_cache[seed] = blobs
    return blobs


def _distance_to_blob(x: int, y: int, blob: Tuple[int, int, float]) -> float:
    """Calculate distance from point to blob edge (negative if inside blob)."""
    center_x, center_y, radius = blob
    dist = math.hypot(x - center_x, y - center_y)
    return dist - radius  # Negative if inside blob, positive if outside


def _get_base_terrain(x: int, y: int, seed: int, difficulty: str) -> str:
    """
    Get base terrain type: water (inside blobs), sand (beach around blobs), grass (everywhere else).
    """
    blobs = _generate_lake_blobs(seed, difficulty)
    
    # Find minimum distance to any blob edge
    min_dist_to_edge = float('inf')
    nearest_blob = None
    
    for blob in blobs:
        dist_to_edge = _distance_to_blob(x, y, blob)
        if abs(dist_to_edge) < abs(min_dist_to_edge):
            min_dist_to_edge = dist_to_edge
            nearest_blob = blob
    
    # Determine terrain based on distance to blob edge
    if min_dist_to_edge < 0:
        # Inside blob = water
        return TERRAIN_WATER
    elif min_dist_to_edge < 2.0:
        # Within 2 tiles of blob edge = sand (beach)
        # Add some variation so beaches aren't perfectly uniform
        beach_variation = _pseudo_random(x, y, seed, 20)
        if beach_variation < 0.85:  # 85% chance of sand, 15% chance of grass (for natural look)
            return TERRAIN_SAND
        else:
            return TERRAIN_GRASS
    else:
        # Far from blobs = grass
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
        # Get base terrain from blob-based generation
        base_terrain = _get_base_terrain(ix, iy, seed, difficulty)
        
        # Smooth transitions using neighbors (especially for beach edges)
        neighbor_counts: Dict[str, int] = {}
        for dx, dy in _NEIGHBORS:
            nx, ny = ix + dx, iy + dy
            neighbor_key = (nx, ny, seed)
            if neighbor_key in _tile_cache:
                neighbor_terrain = _tile_cache[neighbor_key]
                neighbor_counts[neighbor_terrain] = neighbor_counts.get(neighbor_terrain, 0) + 1
        
        # Smooth beach edges: if surrounded by water, become water; if surrounded by grass, become grass
        if base_terrain == TERRAIN_SAND and neighbor_counts:
            water_count = neighbor_counts.get(TERRAIN_WATER, 0)
            grass_count = neighbor_counts.get(TERRAIN_GRASS, 0)
            total_neighbors = sum(neighbor_counts.values())
            
            if total_neighbors >= 5:  # Most neighbors are known
                if water_count >= 4:
                    # Mostly water neighbors = inside lake edge, become water
                    terrain = TERRAIN_WATER
                elif grass_count >= 4:
                    # Mostly grass neighbors = outside beach, become grass
                    terrain = TERRAIN_GRASS
                else:
                    # Mixed = stay sand (beach)
                    terrain = TERRAIN_SAND
            else:
                terrain = base_terrain
        else:
            terrain = base_terrain
        
        # Cache the result
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
