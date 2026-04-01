"""
Visual Game Interface for The Colony Manager

Top-down tile-based game with automatic turn progression.
Player manages agents and tasks while resources degrade over time.
"""

import pygame
import sys
import math
import random
import os
from typing import Dict, List, Tuple, Optional, Any, Set
from src.game_engine import GameEngine
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import Task, TaskPlanner
from src.module1_state.procedural_tiles import clear_tile_cache
from src.module1_state.movement_bonus import (
    effective_move_multiplier,
    prune_expired_speed_boosts,
)
from src.module1_state.tree_generation import (
    VIEWPORT_TREES_K,
    base_wood_quota,
    ensure_viewport_trees,
    generate_world_trees,
    try_harvest_trees,
)
from src.module1_state.floor_carryover import (
    compute_stress_bin,
    next_floor_knobs,
    summarize_finished_floor,
)

# Asset loading
# visual_game.py lives at the project root, alongside the top-level assets/ folder.
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")


def load_image(*path_parts: str) -> pygame.Surface:
    """Load an image from the assets directory with alpha preserved."""
    path = os.path.join(ASSET_DIR, *path_parts)
    return pygame.image.load(path).convert_alpha()

# Constants
TILE_SIZE = 32  # Size of each tile in pixels
CAMERA_WIDTH = 800  # Width of game view
CAMERA_HEIGHT = 600  # Height of game view
SIDEBAR_WIDTH = 300  # Width of sidebar
SIDEBAR_TAB_BAR_HEIGHT = 32  # Height of tab row (Colony | Agents | Tasks)
# Vertical slice per agent in Agents tab (scroll + hover hit-test must stay in sync)
SIDEBAR_AGENT_ROW_PX = 76
# Pixels from window top to agent list = tab bar + content pad + "Agents (n):" heading block
SIDEBAR_AGENTS_LIST_TOP = SIDEBAR_TAB_BAR_HEIGHT + 6 + 22
WINDOW_WIDTH = CAMERA_WIDTH + SIDEBAR_WIDTH
WINDOW_HEIGHT = CAMERA_HEIGHT
TURN_INTERVAL_SECONDS = 8.0  # Seconds between automatic turns (slower for easier interaction)

# World bounds (finite world size)
WORLD_WIDTH = 50  # Number of tiles wide
WORLD_HEIGHT = 50  # Number of tiles tall
WORLD_MIN_X = -WORLD_WIDTH // 2
WORLD_MAX_X = WORLD_WIDTH // 2
WORLD_MIN_Y = -WORLD_HEIGHT // 2
WORLD_MAX_Y = WORLD_HEIGHT // 2
MAP_SIZE_PRESETS = [
    ("Small", 40),
    ("Medium", 50),
    ("Large", 60),
    ("XL", 100),
    ("XXL", 150),
    ("Max Test", 250),
]

# Colors
COLOR_GRASS = (34, 139, 34)
COLOR_WATER = (0, 119, 190)
COLOR_ROCK = (105, 105, 105)
COLOR_SAND = (238, 203, 173)
COLOR_DIRT = (101, 67, 33)
COLOR_AGENT = (255, 215, 0)  # Gold
COLOR_AGENT_LOW_HEALTH = (255, 0, 0)  # Red
COLOR_TREE_TRUNK = (101, 67, 33)
COLOR_TREE_FOLIAGE = (25, 120, 45)
COLOR_INFRASTRUCTURE = (70, 130, 180)  # Steel blue
COLOR_BACKGROUND = (20, 20, 30)
COLOR_SIDEBAR_BG = (40, 40, 50)
COLOR_TEXT = (255, 255, 255)
COLOR_RESOURCE_BAR_BG = (50, 50, 50)
COLOR_RESOURCE_OXYGEN = (0, 191, 255)
COLOR_RESOURCE_CALORIES = (255, 165, 0)
COLOR_RESOURCE_INTEGRITY = (255, 69, 0)
COLOR_EVENT_TEXT = (255, 0, 0)
COLOR_STATION_OXYGEN = (0, 191, 255)  # Cyan
COLOR_STATION_CALORIES = (255, 165, 0)  # Orange
COLOR_STATION_INTEGRITY = (255, 69, 0)  # Red-orange
COLOR_MENU_BG = (30, 30, 40)
COLOR_BUTTON = (60, 60, 80)
COLOR_BUTTON_HOVER = (80, 80, 100)
COLOR_BUTTON_SELECTED = (100, 150, 200)


# Resource Station Types
STATION_OXYGEN = "oxygen_station"
STATION_CALORIES = "calories_station"
STATION_INTEGRITY = "integrity_station"

# Powerup types (auto-walk to resource station when that resource drops below 20%)
POWERUP_AUTO_OXYGEN = "auto_oxygen"
POWERUP_AUTO_CALORIES = "auto_calories"
POWERUP_AUTO_INTEGRITY = "auto_integrity"
POWERUP_SPEED_BOOST = "speed_boost"
AUTO_WALK_THRESHOLD = 20.0  # Percent below which agent auto-walks to station


def _powerup_params_for_difficulty(difficulty: str) -> Dict[str, Any]:
    """Per-turn spawn chance, max on map, type weights (O2, Cal, Int, Speed). Start is always 1 powerup."""
    d = (difficulty or "normal").lower()
    table = {
        "easy": {
            "max_on_map": 11,
            "turn_spawn_p": 0.36,
            "weights": (0.20, 0.20, 0.20, 0.40),
        },
        "normal": {
            "max_on_map": 8,
            "turn_spawn_p": 0.24,
            "weights": (0.24, 0.24, 0.24, 0.28),
        },
        "hard": {
            "max_on_map": 5,
            "turn_spawn_p": 0.13,
            "weights": (0.28, 0.28, 0.28, 0.16),
        },
    }
    return table.get(d, table["normal"])


def _random_powerup_type(rng: random.Random, weights: Tuple[float, ...]) -> str:
    r = rng.random()
    total = sum(weights)
    acc = 0.0
    types = (
        POWERUP_AUTO_OXYGEN,
        POWERUP_AUTO_CALORIES,
        POWERUP_AUTO_INTEGRITY,
        POWERUP_SPEED_BOOST,
    )
    for t, w in zip(types, weights):
        acc += w / total
        if r <= acc:
            return t
    return types[-1]
VISUAL_REPAIR_AGENT_CAP = 3
# Colonist map sprite height/width ≈ this fraction of on-screen tile size
COLONIST_SPRITE_TILE_FRAC = 0.9
# Station building art: longest edge = this × colonist sprite size (~3× “people” scale)
STATION_SPRITE_VS_COLONIST = 3.0

# Game States
STATE_MENU = "menu"
STATE_SETUP = "setup"  # New game: select starting agents
STATE_OPTIONS = "options"
STATE_ADVANCED = "advanced"
STATE_CONTROLS = "controls"  # Controls help screen
STATE_PLAYING = "playing"
STATE_CONFIRM_QUIT = "confirm_quit"
STATE_GAME_OVER = "game_over"

# Typing this digit sequence during play tops up colony wood (developer / QA testing).
DEV_WOOD_CHEAT_CODE = "941481"
# Spawns several speed-boost map pickups (developer / QA testing).
DEV_SPEED_CHEAT_CODE = "2326"


class ResourceStation:
    """Represents a resource station building."""
    def __init__(self, station_id: str, station_type: str, center_x: int, center_y: int, size: int = 2):
        self.station_id = station_id
        self.station_type = station_type  # oxygen_station, calories_station, integrity_station
        self.center_x = center_x
        self.center_y = center_y
        self.size = size  # 2x2 or 3x3
        self.restore_amount = 30.0  # Amount of resource restored per visit
        
    def get_tiles(self) -> List[Tuple[int, int]]:
        """Get all tiles occupied by this station."""
        offset = self.size // 2
        tiles = []
        for x in range(self.center_x - offset, self.center_x + offset + 1):
            for y in range(self.center_y - offset, self.center_y + offset + 1):
                tiles.append((x, y))
        return tiles
    
    def get_resource_type(self) -> str:
        """Get the resource type this station restores."""
        if self.station_type == STATION_OXYGEN:
            return "oxygen"
        elif self.station_type == STATION_CALORIES:
            return "calories"
        elif self.station_type == STATION_INTEGRITY:
            return "integrity"
        return "oxygen"

    def to_infrastructure_dict(self) -> Dict[str, Any]:
        """Convert station metadata to a serializable infrastructure record."""
        return {
            "kind": "resource_station",
            "station_id": self.station_id,
            "station_type": self.station_type,
            "resource_type": self.get_resource_type(),
            "center": (self.center_x, self.center_y),
            "size": self.size,
            "tiles": self.get_tiles(),
            "status": "operational",
            "warning_turns_remaining": 0,
            "repair_remaining_turns": 0,
            "repair_total_turns": 0,
            "repair_agent_id": None,
        }


def _station_tiles(center_x: int, center_y: int, size: int) -> List[Tuple[int, int]]:
    """Return list of (x, y) tiles occupied by a station with given center and size."""
    offset = size // 2
    tiles = []
    for x in range(center_x - offset, center_x + offset + 1):
        for y in range(center_y - offset, center_y + offset + 1):
            tiles.append((x, y))
    return tiles


_THREAT_LABELS = {
    "oxygen_depletion": "Oxygen critical",
    "oxygen_low": "Oxygen low",
    "calories_depletion": "Food critical",
    "calories_low": "Food low",
    "integrity_depletion": "Structure critical",
    "integrity_low": "Structure low",
    "insufficient_agents": "Short on crew",
    "structural_failure_risk": "Structure at risk",
    "agent_oxygen_depletion": "Colonists: O2 critical",
    "agent_oxygen_low": "Colonists: O2 low",
    "agent_calories_depletion": "Colonists: food critical",
    "agent_calories_low": "Colonists: food low",
}


def _humanize_survival_threat(threat: str) -> str:
    """Turn assessor threat keys into short sidebar labels."""
    key = str(threat).strip()
    if key in _THREAT_LABELS:
        return _THREAT_LABELS[key]
    return key.replace("_", " ").title()


def _task_destination_from_id(task_id: Any) -> Optional[Tuple[int, int]]:
    """Parse world (x, y) from planner task ids like task_-3_5_12."""
    tid = str(task_id or "")
    if not tid.startswith("task_"):
        return None
    parts = tid.split("_")
    if len(parts) < 3:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _format_sidebar_task_line(task: Dict[str, Any]) -> str:
    """One-line task summary for the Tasks tab."""
    dest = _task_destination_from_id(task.get("task_id"))
    agent_id = task.get("agent_id")
    progress = float(task.get("progress", 0.0))
    pct = int(max(0, min(100, round(progress * 100))))
    who = f"agent {agent_id}" if agent_id is not None else "unassigned"
    if dest:
        return f"Go to {dest[0]}, {dest[1]} — {who} — {pct}%"
    return f"En route — {who} — {pct}%"


def _format_event_task_location(loc: Any) -> str:
    """Short location text for an event-driven task row."""
    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
        try:
            return f"{int(loc[0])}, {int(loc[1])}"
        except (TypeError, ValueError):
            pass
    s = str(loc)
    if "_" in s:
        return s.replace("_", " ").title()
    return s


class Powerup:
    """Map pickup: auto-walk (O2/Cal/Int) or temporary speed boost (POWERUP_SPEED_BOOST)."""
    def __init__(self, x: int, y: int, powerup_type: str):
        self.x = x
        self.y = y
        self.powerup_type = powerup_type  # POWERUP_* constants


class VisualGame:
    """
    Main visual game interface using Pygame.
    
    Agent Movement System:
    - Agents have fixed locations that update when they complete tasks
    - When you assign a task (right-click), the task planner (Module 2) calculates:
      * Optimal path using A* pathfinding on the colony graph
      * Travel cost and completion time
    - Agents automatically move to task locations over multiple turns
    - Agent location updates when they reach the destination (task completion)
    - Visual indicators:
      * Yellow circles = Pending tasks (assigned but not started)
      * Green circles = Active tasks (agents traveling/completing)
      * Green lines = Connection from agent to their assigned task
    - World is finite: 50x50 tiles (from -25 to +25 in both directions)
    """
    
    def __init__(self):
        """Initialize the visual game."""
        pygame.init()
        self.original_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.fullscreen = False
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("The Colony Manager")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.font_large = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 18)
        # Smaller type for sidebar stats only (menus / map keep font_small)
        self.font_sidebar_title = pygame.font.Font(None, 18)
        self.font_sidebar_body = pygame.font.Font(None, 13)
        self.font_tab = pygame.font.Font(None, 15)
        
        # Game state
        self.game_state = STATE_MENU
        
        # Game settings
        self.difficulty = "normal"  # easy, normal, hard
        self.algorithm = "astar"  # astar, idastar, beam_search
        self.turn_interval = TURN_INTERVAL_SECONDS
        
        # Camera position (tracks center of view)
        self.camera_x = 0
        self.camera_y = 0
        
        # Zoom level (1.0 = default, higher = zoomed in, lower = zoomed out)
        self.zoom_level = 1.0
        self.zoom_min = 0.2  # Allow more zoom out to see more of the map
        self.zoom_max = 2.0
        
        # Initialize game engine (will be created when starting new game)
        self.game: Optional[GameEngine] = None
        self.last_turn_time = pygame.time.get_ticks()
        self.turn_timer = self.turn_interval * 1000
        self.last_decay_time = 0  # Track time for continuous decay (0 = not initialized yet)
        
        # Event notification system
        self.current_event_text = None
        self.event_start_time = None
        self.event_duration = 2000  # 2 seconds
        # Event tasks shown in Tasks tab (created from adversarial events)
        self.event_tasks: List[Dict[str, Any]] = []
        self.event_task_rects: List[Tuple[pygame.Rect, int]] = []  # (rect, event_task_index)
        
        # Player task queue (for assigning tasks)
        self.pending_tasks: List[Task] = []
        self.selected_agent_id = None
        
        # Agent walking: path coords per agent (agent_id -> remaining steps to walk)
        self.agent_paths: Dict[int, List[Tuple[int, int]]] = {}
        # Smooth movement: interpolated (x, y) for agents in transit
        self.agent_visual_pos: Dict[int, Tuple[float, float]] = {}
        self.agent_move_speed = 2.5  # Tiles per second
        # Last-drawn sprite rects per agent (for hit-testing in screen space)
        self.agent_sprite_rects: Dict[int, pygame.Rect] = {}
        
        # Click-and-drag: assign destination by dragging from agent
        self.drag_agent_id: Optional[int] = None
        self.drag_start_screen: Optional[Tuple[int, int]] = None
        
        # Resource stations
        self.resource_stations: List[ResourceStation] = []
        
        # Menu navigation
        self.menu_selection = 0  # 0 = New Game, 1 = Options, 2 = Quit
        self.options_selection = 0  # 0 = Difficulty, 1 = Advanced, 2 = Controls, 3 = Back
        self.advanced_selection = 0  # 0=Algorithm, 1=Turn Speed, 2=Decay, 3=AI Aggro, 4=AI Random, 5=AI Cooldown, 6=Map Size, 7=Back
        self.difficulty_selection = 1  # 0 = Easy, 1 = Normal, 2 = Hard
        self.algorithm_selection = 0  # 0 = A*, 1 = IDA*, 2 = Beam Search
        self.starting_agents = 2  # 1-5, selected at new game setup
        
        # Decay rate multipliers (1.0 = default, higher = faster decay)
        self.decay_multiplier = 1.0  # Multiplier for decay rates
        # AI Director tuning knobs (editable in Advanced settings)
        self.ai_aggression = 1.0
        self.ai_randomness = 0.4
        self.ai_repeat_cooldown = 3
        self.map_size_index = 1  # 0=Small, 1=Medium, 2=Large
        self._set_world_size(MAP_SIZE_PRESETS[self.map_size_index][1])
        self._apply_difficulty_defaults()
        
        # Fullscreen mode
        self.fullscreen = False
        self.original_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        # Dynamic dimensions (update on fullscreen toggle)
        self.camera_width = CAMERA_WIDTH
        self.camera_height = CAMERA_HEIGHT
        self.sidebar_width = SIDEBAR_WIDTH
        self.window_width = WINDOW_WIDTH
        self.window_height = WINDOW_HEIGHT
        
        # Agent list scrolling
        self.agent_list_scroll = 0  # Scroll offset for agent list in sidebar
        # Sidebar tab: "colony" | "agents" | "tasks"
        self.sidebar_tab = "colony"
        self.sidebar_tab_rects: List[pygame.Rect] = []  # Filled each frame for hit-test
        # Agent under mouse (for hover highlight in sidebar and on map)
        self.hovered_agent_id: Optional[int] = None
        
        # Stage index (0 = first stage). For stage-by-stage play: increment current_stage,
        # then set self.resource_stations = self._choose_station_placements(state, self.current_stage).
        self.current_stage = 0
        
        # Powerups on the map: one at start, more spawn randomly each turn (capped by difficulty)
        self.powerups: List[Powerup] = []
        # Which agents have which powerups: agent_id -> set of powerup_type
        self.agent_powerups: Dict[int, set] = {}
        # When agent is auto-walking to a station we set agent_auto_target[agent_id] = resource_type; clear when they reach station
        self.agent_auto_target: Dict[int, str] = {}
        # Scaled terrain textures for current zoom: (terrain_name, ts_int) -> Surface
        self._tile_scale_cache: Dict[Tuple[str, int], Any] = {}

        # ESC confirmation overlay (in-game)
        self.confirm_quit_selection = 0  # 0=Resume, 1=Quit to Menu
        self.confirm_resume_rect: Optional[pygame.Rect] = None
        self.confirm_quit_rect: Optional[pygame.Rect] = None

        # Game over screen
        self.last_game_over_reason: Optional[str] = None

        # Pause flag (e.g., when window loses focus)
        self.paused: bool = False

        # Latest Module 6 survival assessment (updated each turn for testing / debug UI)
        self.last_survival_assessment: Optional[Dict[str, Any]] = None

        # Rolling buffers for dev digit cheats (digits only)
        self._dev_wood_cheat_buffer: str = ""
        self._dev_speed_cheat_buffer: str = ""

        # --- Sprites / textures (loaded from assets/) ---
        # Terrain tiles (filenames can be adjusted if yours differ)
        try:
            self.img_tile_grass = load_image("tiles", "tile_grass_01.png")
        except Exception as e:
            print("Failed to load tile_grass_01.png:", e)
            self.img_tile_grass = None
        try:
            self.img_tile_sand = load_image("tiles", "tile_sand_01.png")
        except Exception as e:
            print("Failed to load tile_sand_01.png:", e)
            self.img_tile_sand = None
        try:
            self.img_tile_water = load_image("tiles", "tile_water_01.png")
        except Exception as e:
            print("Failed to load tile_water_01.png:", e)
            self.img_tile_water = None
        try:
            self.img_tile_rock = load_image("tiles", "tile_rock_01.png")
        except Exception as e:
            print("Failed to load tile_rock_01.png:", e)
            self.img_tile_rock = None
        try:
            self.img_tile_dirt = load_image("tiles", "tile_dirt_01.png")
        except Exception as e:
            print("Failed to load tile_dirt_01.png:", e)
            self.img_tile_dirt = None

        # Agents
        try:
            self.img_agent_idle = load_image("agents", "agent_idle.png")
        except Exception as e:
            print("Failed to load agent_idle.png:", e)
            self.img_agent_idle = None
        try:
            self.img_agent_walk_1 = load_image("agents", "agent_walk_1.png")
        except Exception as e:
            print("Failed to load agent_walk_1.png:", e)
            self.img_agent_walk_1 = None
        try:
            self.img_agent_walk_2 = load_image("agents", "agent_walk_2.png")
        except Exception as e:
            print("Failed to load agent_walk_2.png:", e)
            self.img_agent_walk_2 = None
        try:
            self.img_agent_dead = load_image("agents", "agent_dead.png")
        except Exception as e:
            print("Failed to load agent_dead.png:", e)
            self.img_agent_dead = None

        # Stations
        try:
            self.img_station_oxygen = load_image("stations", "station_oxygen_3x3.png")
        except Exception as e:
            print("Failed to load station_oxygen_3x3.png:", e)
            self.img_station_oxygen = None
        try:
            self.img_station_calories = load_image("stations", "station_calories_2x2.png")
        except Exception as e:
            print("Failed to load station_calories_2x2.png:", e)
            self.img_station_calories = None
        try:
            self.img_station_integrity = load_image("stations", "station_integrity_3x3.png")
        except Exception as e:
            print("Failed to load station_integrity_3x3.png:", e)
            self.img_station_integrity = None

        # Powerups
        try:
            self.img_powerup_o2 = load_image("powerups", "powerup_auto_oxygen.png")
        except Exception as e:
            print("Failed to load powerup_auto_oxygen.png:", e)
            self.img_powerup_o2 = None
        try:
            self.img_powerup_cal = load_image("powerups", "powerup_auto_calories.png")
        except Exception as e:
            print("Failed to load powerup_auto_calories.png:", e)
            self.img_powerup_cal = None
        try:
            self.img_powerup_int = load_image("powerups", "powerup_auto_integrity.png")
        except Exception as e:
            print("Failed to load powerup_auto_integrity.png:", e)
            self.img_powerup_int = None
        try:
            self.img_powerup_speed = load_image("powerups", "powerup_speed.png")
        except Exception as e:
            print("Failed to load powerup_speed.png:", e)
            self.img_powerup_speed = None
    
    def _set_world_size(self, size_tiles: int) -> None:
        """Apply a world-size preset by updating module-level world bounds."""
        global WORLD_WIDTH, WORLD_HEIGHT, WORLD_MIN_X, WORLD_MAX_X, WORLD_MIN_Y, WORLD_MAX_Y
        size = max(30, min(250, int(size_tiles)))
        if size % 2 != 0:
            size += 1
        WORLD_WIDTH = size
        WORLD_HEIGHT = size
        WORLD_MIN_X = -WORLD_WIDTH // 2
        WORLD_MAX_X = WORLD_WIDTH // 2
        WORLD_MIN_Y = -WORLD_HEIGHT // 2
        WORLD_MAX_Y = WORLD_HEIGHT // 2

    def _choose_station_placements(self, state: ColonyState, stage_index: int) -> List[ResourceStation]:
        """
        Choose valid, non-overlapping positions for resource stations using deterministic RNG.
        Uses (world_seed, stage_index) so each game and each stage gets different but reproducible layouts.
        Ready for stage-by-stage play: call with state and current_stage when starting or advancing a stage.
        """
        seed = state.world_seed + stage_index * 10000
        rng = random.Random(seed)
        
        occupied = set()
        for a in state.agents:
            if a.get("status") == "dead":
                continue
            loc = a.get("location")
            if loc and len(loc) == 2:
                occupied.add((int(loc[0]), int(loc[1])))
        
        def is_valid_placement(cx: int, cy: int, size: int, exclude: set) -> bool:
            tiles = _station_tiles(cx, cy, size)
            for (tx, ty) in tiles:
                if tx < WORLD_MIN_X or tx >= WORLD_MAX_X or ty < WORLD_MIN_Y or ty >= WORLD_MAX_Y:
                    return False
                if (tx, ty) in exclude:
                    return False
                tile = state.get_tile_at(tx, ty)
                if not tile.get("passable", True):
                    return False
                if tile.get("terrain") == "water":
                    return False
            return True
        
        # Candidate centers for 2×2 stations (smaller map footprint than 3×3)
        valid_2x2 = []
        for cx in range(WORLD_MIN_X + 1, WORLD_MAX_X - 1):
            for cy in range(WORLD_MIN_Y + 1, WORLD_MAX_Y - 1):
                if is_valid_placement(cx, cy, 2, occupied):
                    valid_2x2.append((cx, cy))

        if len(valid_2x2) < 3:
            return [
                ResourceStation("oxy_station_1", STATION_OXYGEN, -10, -10, size=2),
                ResourceStation("cal_station_1", STATION_CALORIES, 10, -10, size=2),
                ResourceStation("int_station_1", STATION_INTEGRITY, 0, 10, size=2),
            ]

        rng.shuffle(valid_2x2)
        stations: List[ResourceStation] = []
        for (cx, cy) in valid_2x2:
            if not is_valid_placement(cx, cy, 2, occupied):
                continue
            occupied.update(_station_tiles(cx, cy, 2))
            if len(stations) == 0:
                stations.append(ResourceStation("int_station_1", STATION_INTEGRITY, cx, cy, size=2))
            elif len(stations) == 1:
                stations.append(ResourceStation("oxy_station_1", STATION_OXYGEN, cx, cy, size=2))
            else:
                stations.append(ResourceStation("cal_station_1", STATION_CALORIES, cx, cy, size=2))
                break
        if len(stations) < 3:
            return [
                ResourceStation("oxy_station_1", STATION_OXYGEN, -10, -10, size=2),
                ResourceStation("cal_station_1", STATION_CALORIES, 10, -10, size=2),
                ResourceStation("int_station_1", STATION_INTEGRITY, 0, 10, size=2),
            ]
        return stations
    
    def _powerup_occupied_cells(self, state: ColonyState) -> set:
        """Tiles blocked for powerup placement."""
        occupied = set()
        for a in state.agents:
            if a.get("status") == "dead":
                continue
            loc = a.get("location")
            if loc and len(loc) == 2:
                occupied.add((int(loc[0]), int(loc[1])))
        for station in self.resource_stations:
            occupied.update(station.get_tiles())
        for t in state.world_trees or []:
            if len(t) >= 2:
                occupied.add((int(t[0]), int(t[1])))
        for p in self.powerups:
            occupied.add((p.x, p.y))
        return occupied

    def _snapshot_agent_powerup_carryover(
        self, state: ColonyState, new_agent_count: int
    ) -> Dict[int, Tuple[float, Set[str]]]:
        """Per-agent speed and auto-walk powerup types for IDs that are rebuilt on the next floor."""
        out: Dict[int, Tuple[float, Set[str]]] = {}
        for a in state.agents:
            if a.get("status") == "dead":
                continue
            aid = a.get("id")
            if not isinstance(aid, int) or aid < 0 or aid >= new_agent_count:
                continue
            spd = float(a.get("speed") or 1.0)
            perks = set(self.agent_powerups.get(aid, set()))
            out[aid] = (spd, perks)
        return out

    def _apply_agent_powerup_carryover(
        self, state: ColonyState, carry: Dict[int, Tuple[float, Set[str]]]
    ) -> None:
        """Reapply persisted speed and collector powerups after floor-regenerated agents exist."""
        for aid, (spd, perks) in carry.items():
            agent = state.get_agent_by_id(aid)
            if not agent or agent.get("status") == "dead":
                continue
            if spd > 1.0:
                agent["speed"] = min(2.25, spd)
            if perks:
                self.agent_powerups[aid] = set(perks)

    def _powerups_valid_on_floor(self, state: ColonyState, previous: List[Powerup]) -> List[Powerup]:
        """
        Keep map powerups whose tile is still valid after regen; drop collisions with trees/stations/agents.
        At most one pickup per tile.
        """
        station_tiles: Set[Tuple[int, int]] = set()
        for st in self.resource_stations:
            station_tiles.update(st.get_tiles())
        tree_cells: Set[Tuple[int, int]] = set()
        for t in state.world_trees or []:
            if len(t) >= 2:
                tree_cells.add((int(t[0]), int(t[1])))
        agent_cells: Set[Tuple[int, int]] = set()
        for a in state.agents:
            if a.get("status") == "dead":
                continue
            loc = a.get("location")
            if loc and len(loc) == 2:
                agent_cells.add((int(loc[0]), int(loc[1])))
        used_tile: Set[Tuple[int, int]] = set()
        out: List[Powerup] = []
        for p in previous:
            x, y = int(p.x), int(p.y)
            if not (WORLD_MIN_X <= x < WORLD_MAX_X and WORLD_MIN_Y <= y < WORLD_MAX_Y):
                continue
            tile = state.get_tile_at(x, y)
            if not tile.get("passable", True) or tile.get("terrain") == "water":
                continue
            if (x, y) in station_tiles or (x, y) in tree_cells or (x, y) in agent_cells:
                continue
            if (x, y) in used_tile:
                continue
            used_tile.add((x, y))
            out.append(Powerup(x, y, p.powerup_type))
        return out

    def _sample_powerup_tile(
        self, state: ColonyState, rng: random.Random, occupied: set
    ) -> Optional[Tuple[int, int]]:
        """Random passable non-water tile; bounded tries (no full-map scan)."""
        for _ in range(256):
            x = rng.randrange(WORLD_MIN_X, WORLD_MAX_X)
            y = rng.randrange(WORLD_MIN_Y, WORLD_MAX_Y)
            if (x, y) in occupied:
                continue
            tile = state.get_tile_at(x, y)
            if not tile.get("passable", True):
                continue
            if tile.get("terrain") == "water":
                continue
            return (x, y)
        return None

    def _spawn_initial_powerups(self, state: ColonyState) -> None:
        """
        Exactly one starter powerup (difficulty-weighted type). More spawn randomly each turn.
        RNG: world_seed + 9999.
        """
        params = _powerup_params_for_difficulty(state.difficulty)
        rng = random.Random(int(state.world_seed) + 9999)
        occupied = self._powerup_occupied_cells(state)
        typ = _random_powerup_type(rng, params["weights"])
        xy = self._sample_powerup_tile(state, rng, occupied)
        if xy:
            self.powerups.append(Powerup(xy[0], xy[1], typ))

    def _camera_visible_world_rect(self) -> Tuple[int, int, int, int]:
        """Visible tile AABB as half-open ranges [x0,x1), [y0,y1), aligned with _draw_map."""
        scaled_tile_size = self._get_scaled_tile_size()
        tiles_x = int(self.camera_width / scaled_tile_size) + 4
        tiles_y = int(self.camera_height / scaled_tile_size) + 4
        cx, cy = int(self.camera_x), int(self.camera_y)
        start_x = max(WORLD_MIN_X, min(WORLD_MAX_X - tiles_x, cx - tiles_x // 2))
        start_y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - tiles_y, cy - tiles_y // 2))
        end_x = min(start_x + tiles_x, WORLD_MAX_X)
        end_y = min(start_y + tiles_y, WORLD_MAX_Y)
        return start_x, start_y, end_x, end_y

    def _wood_quota_met_for_advance(self, state: ColonyState) -> bool:
        """Matches colony sidebar: Advance unlocks when wood ≥ floor wood quota."""
        wq = float(getattr(state, "wood_quota", 0.0) or 0.0)
        if wq <= 0.0:
            return False
        return float(state.resources.get("wood", 0.0)) >= wq

    def _apply_dev_wood_cheat(self) -> None:
        """Set colony wood to at least the current floor quota (unlocks Advance when quota > 0)."""
        if not self.game:
            return
        state = self.game.state
        wq = float(getattr(state, "wood_quota", 0.0) or 0.0)
        cur = float(state.resources.get("wood", 0.0))
        if wq > 0.0:
            state.resources["wood"] = max(cur, wq)
        else:
            state.resources["wood"] = cur + 100.0
        self._show_event("Dev: colony wood topped up")

    def _apply_dev_speed_powerups_cheat(self) -> None:
        """Place N speed-boost powerups on passable tiles (same pickup type as map spawns)."""
        if not self.game:
            return
        state = self.game.state
        rng = random.Random(
            int(state.world_seed) + int(state.turn_number) * 997 + 23260
        )
        n_spawn = 5
        added = 0
        for _ in range(n_spawn * 32):
            if added >= n_spawn:
                break
            occupied = self._powerup_occupied_cells(state)
            xy = self._sample_powerup_tile(state, rng, occupied)
            if not xy:
                break
            self.powerups.append(Powerup(xy[0], xy[1], POWERUP_SPEED_BOOST))
            added += 1
        self._show_event(f"Dev: placed {added} speed powerup(s) on the map")

    def _ensure_viewport_trees_turn(self) -> None:
        """Once per turn: guarantee K trees in the current camera view (see VIEWPORT_TREES_K)."""
        if not self.game:
            return
        state = self.game.get_state()
        if self._wood_quota_met_for_advance(state):
            return
        x0, y0, x1, y1 = self._camera_visible_world_rect()
        d = (state.difficulty or "normal").lower()
        k = int(VIEWPORT_TREES_K.get(d, VIEWPORT_TREES_K["normal"]))
        rng = random.Random(
            int(state.world_seed)
            + int(state.turn_number) * 7919
            + int(getattr(state, "floor_index", 1)) * 503
            + 6621
        )
        ensure_viewport_trees(
            state,
            view_x0=x0,
            view_y0=y0,
            view_x1=x1,
            view_y1=y1,
            k=k,
            rng=rng,
        )

    def _maybe_spawn_turn_powerup(self, state: ColonyState) -> None:
        """
        Random extra powerup each turn with probability p(difficulty).
        RNG: world_seed + turn_number * 10007 + floor_index * 877 + 4243.
        """
        if self._wood_quota_met_for_advance(state):
            return
        params = _powerup_params_for_difficulty(state.difficulty)
        if len(self.powerups) >= params["max_on_map"]:
            return
        rng = random.Random(
            int(state.world_seed)
            + int(state.turn_number) * 10007
            + int(getattr(state, "floor_index", 1)) * 877
            + 4243
        )
        if rng.random() >= params["turn_spawn_p"]:
            return
        occupied = self._powerup_occupied_cells(state)
        typ = _random_powerup_type(rng, params["weights"])
        xy = self._sample_powerup_tile(state, rng, occupied)
        if xy:
            self.powerups.append(Powerup(xy[0], xy[1], typ))
    
    def _create_initial_game(self) -> GameEngine:
        """Create initial game state with agents and resource stations."""
        self._dev_wood_cheat_buffer = ""
        self._dev_speed_cheat_buffer = ""
        # Clear tile cache to ensure fresh map generation
        clear_tile_cache()
        self.event_tasks.clear()
        self.event_task_rects.clear()
        # Generate random seed for procedural map generation
        random_seed = random.randint(0, 2**31 - 1)
        initial_state = ColonyState({"world_seed": random_seed, "difficulty": self.difficulty})
        
        # Agent names for variety
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        # Spread initial agents around center
        start_positions = [(0, 0), (5, 5), (-5, 5), (-5, -5), (5, -5)]
        
        count = min(max(1, self.starting_agents), 5)
        agents_data = []
        for i in range(count):
            x, y = start_positions[i % len(start_positions)]
            x = max(WORLD_MIN_X, min(WORLD_MAX_X - 1, x + (i * 2 % 5 - 2)))
            y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - 1, y + (i * 3 % 5 - 2)))
            agents_data.append({
                "id": i,
                "name": names[i % len(names)],
                "oxygen": 80.0,
                "calories": 70.0,
                "integrity": 90.0,
                "location": (x, y),
                "status": "active"
            })
        
        for agent_data in agents_data:
            x, y = agent_data["location"]
            x = max(WORLD_MIN_X, min(WORLD_MAX_X - 1, x))
            y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - 1, y))
            agent_data["location"] = (x, y)
        
        for agent_data in agents_data:
            success, errors = initial_state.add_agent(agent_data)
            if not success:
                print(f"Warning: Failed to add agent: {errors}")
        
        # Place resource stations (randomized per game and per stage; deterministic from seed + stage)
        self.current_stage = 0
        self.resource_stations = self._choose_station_placements(initial_state, self.current_stage)
        self._sync_stations_to_state(initial_state)
        
        # One starter powerup; rest spawn per-turn (seed + 9999)
        self.powerups = []
        self.agent_powerups = {}
        self.agent_auto_target = {}
        self._spawn_initial_powerups(initial_state)
        
        # Apply difficulty defaults (turn pacing, decay, AI tuning)
        self._apply_difficulty_defaults()
        
        self.turn_timer = self.turn_interval * 1000
        self.last_decay_time = pygame.time.get_ticks()  # Initialize decay timer
        
        self.agent_paths.clear()
        self.agent_visual_pos.clear()
        engine = GameEngine(initial_state)
        self.game = engine

        # Multi-floor: world AABB, wood quota, sparse trees (design: harder difficulty → fewer trees).
        st = engine.state
        st.world_min_x, st.world_max_x = WORLD_MIN_X, WORLD_MAX_X
        st.world_min_y, st.world_max_y = WORLD_MIN_Y, WORLD_MAX_Y
        st.floor_index = max(1, int(getattr(st, "floor_index", 1)))
        st.wood_quota = float(base_wood_quota(self.difficulty, st.floor_index))
        st.floor_start_turn = int(st.turn_number)
        st.floor_disasters_count = 0
        st.floor_deaths_count = 0
        st.turn_wood_quota_met = None
        st.floor_repair_turns_extra = 0
        st.director_aggression_bonus = 0.0
        st.rl_carryover_stress_bin = 0
        if "wood" not in st.resources:
            st.resources["wood"] = 0.0
        st.world_trees = generate_world_trees(
            st,
            WORLD_MIN_X,
            WORLD_MAX_X,
            WORLD_MIN_Y,
            WORLD_MAX_Y,
            tree_density_multiplier=1.0,
        )

        self._apply_ai_settings_to_engine()
        self.last_survival_assessment = engine.survival_assessor.assess_survival(engine.state)
        engine.warm_terrain_cache()
        return engine

    def _advance_to_next_floor(self) -> None:
        """End current floor, record summary for RL/carryover, regenerate map content."""
        if not self.game:
            return
        state = self.game.state
        summary = summarize_finished_floor(
            state,
            int(getattr(state, "floor_start_turn", 0)),
            int(getattr(state, "floor_disasters_count", 0)),
            int(getattr(state, "floor_deaths_count", 0)),
            getattr(state, "turn_wood_quota_met", None),
        )
        state.prior_floor_summaries.append(summary)
        stress = compute_stress_bin(summary)
        knobs = next_floor_knobs(
            state.prior_floor_summaries,
            int(state.floor_index) + 1,
            state.difficulty,
        )
        state.rl_carryover_stress_bin = stress
        state.floor_index = int(state.floor_index) + 1
        state.world_seed = (int(state.world_seed) + 104729 * state.floor_index) % (2**31)
        state.resources["wood"] = 0.0
        state.wood_quota = float(
            base_wood_quota(state.difficulty, state.floor_index) + knobs["wood_quota_adjust"]
        )
        state.turn_wood_quota_met = None
        state.floor_start_turn = int(state.turn_number)
        state.floor_disasters_count = 0
        state.floor_deaths_count = 0
        state.floor_repair_turns_extra = int(knobs["extra_repair_turns"])
        state.director_aggression_bonus = float(
            getattr(state, "director_aggression_bonus", 0.0) + knobs["director_aggression_delta"]
        )

        # Parity with _create_initial_game: engine pathfinding / terrain grid use state.world_*.
        state.world_min_x = WORLD_MIN_X
        state.world_max_x = WORLD_MAX_X
        state.world_min_y = WORLD_MIN_Y
        state.world_max_y = WORLD_MAX_Y

        # Drop planner/UI baggage from the previous floor (stale agent IDs, old events).
        state.active_tasks.clear()
        self.pending_tasks.clear()
        self.event_tasks.clear()
        self.event_task_rects.clear()
        self.selected_agent_id = None
        self.hovered_agent_id = None
        self.drag_agent_id = None
        self.drag_start_screen = None

        clear_tile_cache()
        if self.game:
            self.game.invalidate_terrain_cache()
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        count = min(max(1, self.starting_agents), 5)
        persist_map_powerups = list(self.powerups)
        carry_agent_powerups = self._snapshot_agent_powerup_carryover(state, count)
        state.agents.clear()
        start_positions = [(0, 0), (5, 5), (-5, 5), (-5, -5), (5, -5)]
        for i in range(count):
            x, y = start_positions[i % len(start_positions)]
            x = max(WORLD_MIN_X, min(WORLD_MAX_X - 1, x + (i * 2 % 5 - 2)))
            y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - 1, y + (i * 3 % 5 - 2)))
            ok, errs = state.add_agent(
                {
                    "id": i,
                    "name": names[i % len(names)],
                    "oxygen": 80.0,
                    "calories": 70.0,
                    "integrity": 90.0,
                    "location": (x, y),
                    "status": "active",
                },
                validate=True,
            )
            if not ok:
                print(f"Warning: Advance floor failed to add agent: {errs}")

        self.resource_stations = self._choose_station_placements(state, int(state.floor_index))
        for sid in list(state.infrastructure.keys()):
            del state.infrastructure[sid]
        self._sync_stations_to_state(state)
        self.agent_powerups = {}
        self.agent_auto_target = {}
        self.agent_paths.clear()
        self.agent_visual_pos.clear()
        state.world_trees = generate_world_trees(
            state,
            WORLD_MIN_X,
            WORLD_MAX_X,
            WORLD_MIN_Y,
            WORLD_MAX_Y,
            tree_density_multiplier=float(knobs["tree_density_multiplier"]),
        )
        self.powerups = self._powerups_valid_on_floor(state, persist_map_powerups)
        self._spawn_initial_powerups(state)
        self._apply_agent_powerup_carryover(state, carry_agent_powerups)
        self._apply_ai_settings_to_engine()
        self.game.task_planner = TaskPlanner(state)
        self.last_survival_assessment = self.game.survival_assessor.assess_survival(state)
        self.game.warm_terrain_cache()
        self._show_event(
            f"Floor {int(state.floor_index)} — wood quota {state.wood_quota:.0f}. Disasters active again."
        )

    def _difficulty_defaults(self, difficulty: str) -> Dict[str, float]:
        """Return default gameplay + AI settings for a difficulty preset."""
        presets = {
            "easy": {
                "turn_interval": 15.0,
                "decay_multiplier": 0.8,
                "ai_aggression": 0.75,
                "ai_randomness": 0.65,
                "ai_repeat_cooldown": 4,
            },
            "normal": {  # medium
                "turn_interval": 12.0,
                "decay_multiplier": 1.0,
                "ai_aggression": 1.0,
                "ai_randomness": 0.4,
                "ai_repeat_cooldown": 3,
            },
            "hard": {
                "turn_interval": 8.0,
                "decay_multiplier": 1.25,
                "ai_aggression": 1.3,
                "ai_randomness": 0.2,
                "ai_repeat_cooldown": 2,
            },
        }
        return presets.get(difficulty, presets["normal"])

    def _apply_ai_settings_to_engine(self) -> None:
        """Push current AI tuning values into the running GameEngine (if any)."""
        if not self.game:
            return
        bonus = float(getattr(self.game.state, "director_aggression_bonus", 0.0))
        self.game.set_ai_director_settings(
            aggression=self.ai_aggression + bonus,
            randomness=self.ai_randomness,
            repetition_window=self.ai_repeat_cooldown,
        )

    def _apply_difficulty_defaults(self) -> None:
        """Apply default settings bundle for the current difficulty."""
        defaults = self._difficulty_defaults(self.difficulty)
        self.turn_interval = float(defaults["turn_interval"])
        self.turn_timer = self.turn_interval * 1000
        self.decay_multiplier = float(defaults["decay_multiplier"])
        self.ai_aggression = float(defaults["ai_aggression"])
        self.ai_randomness = float(defaults["ai_randomness"])
        self.ai_repeat_cooldown = int(defaults["ai_repeat_cooldown"])
        self._apply_ai_settings_to_engine()

    def _sync_stations_to_state(self, state: ColonyState) -> None:
        """
        Persist station layout/runtime metadata into ColonyState infrastructure.

        This keeps station data in the authoritative game state so it can be
        saved/loaded and used by the AI/event systems.
        """
        for station in self.resource_stations:
            existing = state.infrastructure.get(station.station_id, {})
            merged = station.to_infrastructure_dict()
            # Preserve runtime fields when re-syncing (e.g., after load/stage updates)
            merged["status"] = existing.get("status", merged["status"])
            merged["warning_turns_remaining"] = existing.get(
                "warning_turns_remaining", merged["warning_turns_remaining"]
            )
            merged["repair_remaining_turns"] = existing.get(
                "repair_remaining_turns", merged["repair_remaining_turns"]
            )
            merged["repair_total_turns"] = existing.get(
                "repair_total_turns", merged["repair_total_turns"]
            )
            merged["repair_agent_id"] = existing.get("repair_agent_id", merged["repair_agent_id"])
            state.infrastructure[station.station_id] = merged

    def _get_station_state(self, station: ResourceStation) -> Dict[str, Any]:
        """Get runtime station state from ColonyState infrastructure."""
        if not self.game:
            return station.to_infrastructure_dict()
        state = self.game.get_state()
        return state.infrastructure.get(station.station_id, station.to_infrastructure_dict())

    def _count_living_agents_on_station(self, station: ResourceStation) -> int:
        """Return number of living agents currently standing on a station footprint."""
        if not self.game:
            return 0
        state = self.game.get_state()
        station_tiles = set(station.get_tiles())
        count = 0
        for agent in state.agents:
            if agent.get("status") == "dead":
                continue
            loc = agent.get("location")
            if not isinstance(loc, (tuple, list)) or len(loc) != 2:
                continue
            if (int(loc[0]), int(loc[1])) in station_tiles:
                count += 1
        return count
    
    def _get_tile_color(self, terrain: str) -> Tuple[int, int, int]:
        """Get color for a terrain type."""
        color_map = {
            "grass": COLOR_GRASS,
            "water": COLOR_WATER,
            "rock": COLOR_ROCK,
            "sand": COLOR_SAND,
            "dirt": COLOR_DIRT,
        }
        return color_map.get(terrain, COLOR_DIRT)
    
    def _get_scaled_tile_size(self) -> float:
        """Get TILE_SIZE scaled by zoom level."""
        return TILE_SIZE * self.zoom_level

    def _colonist_map_sprite_px(self) -> int:
        """On-screen pixel size for colonist sprites (matches _draw_agents)."""
        ts = int(self._get_scaled_tile_size())
        return max(16, int(ts * COLONIST_SPRITE_TILE_FRAC))

    def _world_to_screen(self, world_x: int, world_y: int) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates (tile center)."""
        ts = self._get_scaled_tile_size()
        screen_x = (world_x - self.camera_x) * ts + self.camera_width // 2
        screen_y = (world_y - self.camera_y) * ts + self.camera_height // 2
        return int(screen_x), int(screen_y)
    
    def _screen_to_world_tile(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """Convert screen coordinates to the tile under the cursor (rounded). Use for drag target and click-to-select so the intended tile is chosen."""
        ts = self._get_scaled_tile_size()
        world_x = (screen_x - self.camera_width // 2) / ts + self.camera_x
        world_y = (screen_y - self.camera_height // 2) / ts + self.camera_y
        return round(world_x), round(world_y)
    
    def _get_tile_screen_rect(self, world_x: int, world_y: int) -> Tuple[int, int, int, int]:
        """Return (left, top, width, height) for the tile at world (world_x, world_y) using a
        grid-aligned layout so adjacent tiles share edges with no gaps or overlaps (avoids
        visible grid lines when zooming). Uses integer tile size and a single origin per frame."""
        ts_f = self._get_scaled_tile_size()
        ts_int = int(round(ts_f))
        origin_left = (0 - self.camera_x) * ts_f + self.camera_width // 2 - ts_int / 2
        origin_top = (0 - self.camera_y) * ts_f + self.camera_height // 2 - ts_int / 2
        left = int(origin_left) + world_x * ts_int
        top = int(origin_top) + world_y * ts_int
        return left, top, ts_int, ts_int
    
    def _draw_tile(self, x: int, y: int, terrain: str):
        """Draw a single tile at world coordinates. Uses grid-aligned rect to avoid seam lines when zooming."""
        left, top, ts, _ = self._get_tile_screen_rect(x, y)
        
        # Only draw if tile is visible
        if -ts <= left <= self.camera_width + ts and -ts <= top <= self.camera_height + ts:
            # Prefer textured tiles if available, fall back to solid colors otherwise
            img = None
            if terrain == "grass" and self.img_tile_grass:
                img = self.img_tile_grass
            elif terrain == "sand" and self.img_tile_sand:
                img = self.img_tile_sand
            elif terrain == "water" and self.img_tile_water:
                img = self.img_tile_water
            elif terrain == "rock" and self.img_tile_rock:
                img = self.img_tile_rock
            elif terrain == "dirt" and self.img_tile_dirt:
                img = self.img_tile_dirt

            if img is not None:
                key = (terrain, ts)
                scaled = self._tile_scale_cache.get(key)
                if scaled is None:
                    if len(self._tile_scale_cache) > 64:
                        self._tile_scale_cache.clear()
                    scaled = pygame.transform.smoothscale(img, (ts, ts))
                    self._tile_scale_cache[key] = scaled
                rect = pygame.Rect(left, top, ts, ts)
                self.screen.blit(scaled, rect)
            else:
                color = self._get_tile_color(terrain)
                rect = pygame.Rect(left, top, ts, ts)
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)  # Border
    
    def _draw_task_destinations(self):
        """Draw visual indicators for task destinations (where agents are going)."""
        state = self.game.get_state()
        
        # Draw pending tasks (yellow markers)
        ts = int(self._get_scaled_tile_size())
        for task in self.pending_tasks:
            x, y = task.location
            if WORLD_MIN_X <= x < WORLD_MAX_X and WORLD_MIN_Y <= y < WORLD_MAX_Y:
                screen_x, screen_y = self._world_to_screen(x, y)
                # Draw yellow circle marker
                pygame.draw.circle(self.screen, (255, 255, 0), (screen_x, screen_y), ts // 2, 2)
                # Draw "T" for task
                text = self.font_small.render("T", True, (255, 255, 0))
                text_rect = text.get_rect(center=(screen_x, screen_y))
                self.screen.blit(text, text_rect)
        
        # Draw active tasks (green markers with progress)
        for task in state.active_tasks:
            task_id = task.get("task_id", "")
            agent_id = task.get("agent_id")
            progress = task.get("progress", 0.0)
            
            # Try to find task location from task_id or use a default
            # Task IDs are formatted as "task_{x}_{y}_{turn}"
            if task_id.startswith("task_") and "_" in task_id:
                parts = task_id.split("_")
                if len(parts) >= 3:
                    try:
                        x, y = int(parts[1]), int(parts[2])
                        if WORLD_MIN_X <= x < WORLD_MAX_X and WORLD_MIN_Y <= y < WORLD_MAX_Y:
                            screen_x, screen_y = self._world_to_screen(x, y)
                            # Draw green circle marker
                            pygame.draw.circle(self.screen, (0, 255, 0), (screen_x, screen_y), TILE_SIZE // 2, 2)
                            # Draw progress percentage
                            progress_text = f"{int(progress * 100)}%"
                            text = self.font_small.render(progress_text, True, (0, 255, 0))
                            text_rect = text.get_rect(center=(screen_x, screen_y))
                            self.screen.blit(text, text_rect)
                            
                            # Draw line from agent to task if agent exists
                            if agent_id is not None:
                                agent = state.get_agent_by_id(agent_id)
                                if agent:
                                    agent_loc = agent.get("location")
                                    if agent_loc and isinstance(agent_loc, (tuple, list)) and len(agent_loc) == 2:
                                        ax, ay = int(agent_loc[0]), int(agent_loc[1])
                                        agent_screen_x, agent_screen_y = self._world_to_screen(ax, ay)
                                        # Draw dashed line
                                        pygame.draw.line(self.screen, (0, 255, 0), 
                                                       (agent_screen_x, agent_screen_y),
                                                       (screen_x, screen_y), 1)
                    except (ValueError, IndexError):
                        pass
    
    def _draw_agents(self):
        """Draw all agents on the map. Uses smooth visual position when agent is walking."""
        state = self.game.get_state()
        # Reset sprite rects each frame before drawing
        self.agent_sprite_rects.clear()
        for agent in state.agents:
            agent_id = agent.get("id")
            status = agent.get("status", "active")
            
            # Use interpolated position when agent is in transit
            if agent_id in self.agent_visual_pos:
                vx, vy = self.agent_visual_pos[agent_id]
                x, y = vx, vy
            else:
                loc = agent.get("location")
                if not loc or not isinstance(loc, (tuple, list)) or len(loc) != 2:
                    continue
                x, y = float(loc[0]), float(loc[1])
            screen_x, screen_y = self._world_to_screen(x, y)
            ts = int(self._get_scaled_tile_size())
            pad = max(ts * 2, self._colonist_map_sprite_px())
            if (
                screen_x < -pad
                or screen_x > self.camera_width + pad
                or screen_y < -pad
                or screen_y > self.camera_height + pad
            ):
                continue

            # Choose sprite if available; fall back to circles if not
            img = None
            if status == "dead" and self.img_agent_dead:
                img = self.img_agent_dead
            elif status != "dead" and self.img_agent_idle:
                # Simple: always use idle sprite for now
                img = self.img_agent_idle

            if img is not None:
                # Scale agent sprite with zoom so it stays proportional to tiles
                size = self._colonist_map_sprite_px()
                scaled = pygame.transform.smoothscale(img, (size, size))
                rect = scaled.get_rect(center=(screen_x, screen_y))
                self.screen.blit(scaled, rect)
                # Store rect for hit-testing (hitbox = sprite bounds)
                if agent_id is not None:
                    self.agent_sprite_rects[agent_id] = rect
                # Hover and selected highlights
                if status != "dead":
                    if self.hovered_agent_id == agent_id:
                        pygame.draw.circle(self.screen, (255, 255, 0), (screen_x, screen_y), rect.width // 2 + 5, 2)
                    if self.selected_agent_id == agent.get("id"):
                        pygame.draw.circle(self.screen, (255, 255, 0), (screen_x, screen_y), rect.width // 2 + 4, 2)
            else:
                # Fallback: original circle-based rendering
                if status == "dead":
                    color = (100, 100, 100)  # Grey for dead agents
                    border_color = (60, 60, 60)  # Darker grey border
                    text_color = (150, 150, 150)  # Grey text
                else:
                    oxygen = agent.get("oxygen", 100.0)
                    integrity = agent.get("integrity", 100.0)
                    avg_health = (oxygen + integrity) / 2.0
                    color = COLOR_AGENT_LOW_HEALTH if avg_health < 30 else COLOR_AGENT
                    border_color = (0, 0, 0)
                    text_color = COLOR_TEXT
                radius = max(4, int(self._get_scaled_tile_size() // 3))
                pygame.draw.circle(self.screen, color, (screen_x, screen_y), radius)
                pygame.draw.circle(self.screen, border_color, (screen_x, screen_y), radius, 2)
                agent_id_display = agent.get("id", "?")
                text = self.font_small.render(str(agent_id_display), True, text_color)
                text_rect = text.get_rect(center=(screen_x, screen_y))
                self.screen.blit(text, text_rect)
                if status != "dead":
                    if self.hovered_agent_id == agent.get("id"):
                        pygame.draw.circle(self.screen, (255, 255, 0), (screen_x, screen_y), radius + 5, 2)
                    if self.selected_agent_id == agent.get("id"):
                        pygame.draw.circle(self.screen, (255, 255, 0), (screen_x, screen_y), radius + 4, 3)
    
    def _draw_drag_preview(self):
        """Draw line from agent to cursor when dragging to assign destination."""
        if self.drag_agent_id is None or not self.game:
            return
        state = self.game.get_state()
        agent = state.get_agent_by_id(self.drag_agent_id)
        # Don't draw preview for dead agents
        if not agent or agent.get("status") == "dead":
            self.drag_agent_id = None
            self.drag_start_screen = None
            return
        # Use visual pos if agent is walking, else state location
        if self.drag_agent_id in self.agent_visual_pos:
            vx, vy = self.agent_visual_pos[self.drag_agent_id]
            ax, ay = vx, vy
        else:
            loc = agent.get("location")
            if not loc or not isinstance(loc, (tuple, list)) or len(loc) != 2:
                return
            ax, ay = float(loc[0]), float(loc[1])
        agent_screen = self._world_to_screen(ax, ay)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if mouse_x < self.camera_width:
            pygame.draw.line(self.screen, (255, 255, 0), agent_screen, (mouse_x, mouse_y), 3)
            # Draw target marker at cursor
            pygame.draw.circle(self.screen, (255, 255, 0), (mouse_x, mouse_y), 8, 2)
    
    def _draw_world_bounds(self):
        """Draw visual indicators for world boundaries."""
        # Draw boundary lines at edges of visible area
        camera_x_int = int(self.camera_x)
        camera_y_int = int(self.camera_y)
        
        # Check if we're near boundaries
        if camera_x_int <= WORLD_MIN_X + 5:
            # Left boundary visible
            screen_x, _ = self._world_to_screen(WORLD_MIN_X, camera_y_int)
            if 0 <= screen_x <= self.camera_width:
                pygame.draw.line(self.screen, (255, 255, 0), 
                               (screen_x, 0), (screen_x, self.camera_height), 3)
        
        if camera_x_int >= WORLD_MAX_X - 5:
            # Right boundary visible
            screen_x, _ = self._world_to_screen(WORLD_MAX_X - 1, camera_y_int)
            if 0 <= screen_x <= self.camera_width:
                pygame.draw.line(self.screen, (255, 255, 0), 
                               (screen_x, 0), (screen_x, self.camera_height), 3)
        
        if camera_y_int <= WORLD_MIN_Y + 5:
            # Top boundary visible
            _, screen_y = self._world_to_screen(camera_x_int, WORLD_MIN_Y)
            if 0 <= screen_y <= self.camera_height:
                pygame.draw.line(self.screen, (255, 255, 0), 
                               (0, screen_y), (self.camera_width, screen_y), 3)
        
        if camera_y_int >= WORLD_MAX_Y - 5:
            # Bottom boundary visible
            _, screen_y = self._world_to_screen(camera_x_int, WORLD_MAX_Y - 1)
            if 0 <= screen_y <= self.camera_height:
                pygame.draw.line(self.screen, (255, 255, 0), 
                               (0, screen_y), (self.camera_width, screen_y), 3)

    def _draw_graph_location_labels(self):
        """
        Draw labels/markers for internal graph locations (e.g., section_alpha).
        This makes adversarial event locations visible on the map.
        """
        # Disaster node circles/labels disabled per UX request.
        return
    
    def _draw_sidebar(self):
        """Draw the sidebar with tabs: Colony | Agents | Tasks."""
        sidebar_x = self.camera_width
        state = self.game.get_state()
        agents = [a for a in state.agents if a.get("status") != "dead"]
        if agents:
            avg_oxygen = sum(a.get("oxygen", 0) for a in agents) / len(agents)
            avg_calories = sum(a.get("calories", 0) for a in agents) / len(agents)
            avg_integrity = sum(a.get("integrity", 0) for a in agents) / len(agents)
        else:
            avg_oxygen = avg_calories = avg_integrity = 0.0

        # Background
        sidebar_rect = pygame.Rect(sidebar_x, 0, self.sidebar_width, self.window_height)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR_BG, sidebar_rect)

        # Tab bar
        tab_bar_rect = pygame.Rect(sidebar_x, 0, self.sidebar_width, SIDEBAR_TAB_BAR_HEIGHT)
        pygame.draw.rect(self.screen, (50, 50, 65), tab_bar_rect)
        pygame.draw.line(self.screen, (80, 80, 90), (sidebar_x, SIDEBAR_TAB_BAR_HEIGHT), (sidebar_x + self.sidebar_width, SIDEBAR_TAB_BAR_HEIGHT), 2)

        tab_labels = ["Colony", "Agents", "Tasks"]
        tab_keys = ["colony", "agents", "tasks"]
        self.sidebar_tab_rects = []
        tw = self.sidebar_width // 3
        for i, label in enumerate(tab_labels):
            tab_rect = pygame.Rect(sidebar_x + i * tw, 0, tw, SIDEBAR_TAB_BAR_HEIGHT)
            self.sidebar_tab_rects.append(tab_rect)
            is_active = self.sidebar_tab == tab_keys[i]
            color = COLOR_BUTTON_SELECTED if is_active else COLOR_BUTTON
            pygame.draw.rect(self.screen, color, tab_rect)
            if i > 0:
                pygame.draw.line(self.screen, (60, 60, 70), (tab_rect.left, 4), (tab_rect.left, SIDEBAR_TAB_BAR_HEIGHT - 4), 1)
            text_surf = self.font_tab.render(label, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=tab_rect.center)
            self.screen.blit(text_surf, text_rect)

        content_top = SIDEBAR_TAB_BAR_HEIGHT + 6
        y_offset = content_top

        # Content area depends on active tab
        if self.sidebar_tab == "colony":
            # Colony: resources, turn, recruit
            title = self.font_sidebar_title.render("Colony Status", True, COLOR_TEXT)
            self.screen.blit(title, (sidebar_x + 10, y_offset))
            y_offset += 22
            y_offset = self._draw_resource_bar(sidebar_x + 10, y_offset, "Oxygen", avg_oxygen, COLOR_RESOURCE_OXYGEN)
            y_offset = self._draw_resource_bar(sidebar_x + 10, y_offset, "Calories", avg_calories, COLOR_RESOURCE_CALORIES)
            y_offset = self._draw_resource_bar(sidebar_x + 10, y_offset, "Integrity", avg_integrity, COLOR_RESOURCE_INTEGRITY)
            y_offset += 6
            turn_text = self.font_sidebar_title.render(f"Turn: {state.turn_number}", True, COLOR_TEXT)
            self.screen.blit(turn_text, (sidebar_x + 10, y_offset))
            y_offset += 20
            # Colony outlook (heuristic or Q estimate; no raw state ids / method names)
            dbg = self.last_survival_assessment
            if dbg:
                sp = float(dbg.get("survival_probability", 0.0))
                threats = dbg.get("critical_threats") or []
                ttf = dbg.get("time_to_failure")
                outlook_color = (160, 210, 160) if sp >= 0.65 else (220, 190, 130) if sp >= 0.4 else (220, 150, 130)
                main_line = self.font_sidebar_body.render(f"Outlook: {sp:.0%}", True, outlook_color)
                self.screen.blit(main_line, (sidebar_x + 10, y_offset))
                y_offset += 14
                if threats:
                    labels = [_humanize_survival_threat(t) for t in threats[:3]]
                    extra = "…" if len(threats) > 3 else ""
                    watch = self.font_sidebar_body.render(f"Watch: {', '.join(labels)}{extra}", True, (200, 170, 150))
                    self.screen.blit(watch, (sidebar_x + 10, y_offset))
                    y_offset += 13
                elif sp < 0.65 and ttf is not None:
                    hint = self.font_sidebar_body.render(f"If trends hold: crisis in ~{ttf} turns", True, (180, 165, 140))
                    self.screen.blit(hint, (sidebar_x + 10, y_offset))
                    y_offset += 13
                else:
                    pending = self.font_sidebar_body.render("Outlook: —", True, (120, 120, 130))
                    self.screen.blit(pending, (sidebar_x + 10, y_offset))
                    y_offset += 14
            y_offset += 6
            floor_line = self.font_sidebar_body.render(
                f"Floor {int(getattr(state, 'floor_index', 1))}", True, (180, 200, 220)
            )
            self.screen.blit(floor_line, (sidebar_x + 10, y_offset))
            y_offset += 14
            wq = float(getattr(state, "wood_quota", 0.0) or 0.0)
            wood_amt = float(state.resources.get("wood", 0.0))
            wood_line = self.font_sidebar_body.render(
                f"Wood: {wood_amt:.0f} / {wq:.0f}", True, (210, 175, 120)
            )
            self.screen.blit(wood_line, (sidebar_x + 10, y_offset))
            y_offset += 14
            self.advance_floor_button_rect = None
            if wq > 0 and wood_amt >= wq:
                calm = self.font_sidebar_body.render(
                    "Disasters halted — safe to advance.", True, (120, 220, 140)
                )
                self.screen.blit(calm, (sidebar_x + 10, y_offset))
                y_offset += 14
                adv_rect = pygame.Rect(sidebar_x + 10, y_offset, self.sidebar_width - 20, 28)
                self.advance_floor_button_rect = adv_rect
                pygame.draw.rect(self.screen, (70, 110, 90), adv_rect)
                pygame.draw.rect(self.screen, COLOR_TEXT, adv_rect, 2)
                adv_lbl = self.font_sidebar_body.render("Advance to next floor", True, COLOR_TEXT)
                self.screen.blit(adv_lbl, adv_lbl.get_rect(center=adv_rect.center))
                y_offset += 32
            else:
                y_offset += 4
            y_offset += 8
            RECRUIT_COST = (30, 30, 30)
            can_recruit = (
                agents and avg_oxygen >= RECRUIT_COST[0]
                and avg_calories >= RECRUIT_COST[1]
                and avg_integrity >= RECRUIT_COST[2]
            )
            recruit_rect = pygame.Rect(sidebar_x + 10, y_offset, self.sidebar_width - 20, 28)
            self.recruit_button_rect = recruit_rect
            recruit_color = COLOR_BUTTON_SELECTED if can_recruit else (80, 60, 60)
            pygame.draw.rect(self.screen, recruit_color, recruit_rect)
            pygame.draw.rect(self.screen, COLOR_TEXT, recruit_rect, 2)
            recruit_text = self.font_sidebar_body.render("Recruit Agent (30 each)", True, COLOR_TEXT)
            self.screen.blit(recruit_text, recruit_text.get_rect(center=recruit_rect.center))
            self.agent_scroll_up_rect = None
            self.agent_scroll_down_rect = None

        elif self.sidebar_tab == "agents":
            self.recruit_button_rect = None
            self.advance_floor_button_rect = None
            # Reserve a gutter on the right for scrollbar so content never overlaps
            agents_gutter = 44
            agents_content_right = sidebar_x + self.sidebar_width - agents_gutter
            agents_content_width = self.sidebar_width - agents_gutter
            agents_bar_max_width = agents_content_width - 50  # bars start at sidebar_x + 50

            agents_title = self.font_sidebar_title.render(f"Agents ({len(state.agents)}):", True, COLOR_TEXT)
            self.screen.blit(agents_title, (sidebar_x + 10, y_offset))
            y_offset += 22
            agents_per_page = 5
            agent_entry_height = SIDEBAR_AGENT_ROW_PX
            total_agents = len(state.agents)
            max_scroll = max(0, total_agents - agents_per_page)
            self.agent_list_scroll = max(0, min(self.agent_list_scroll, max_scroll))
            agents_list_top = y_offset
            agents_list_height = agents_per_page * agent_entry_height

            # Scroll column: track and buttons sit entirely in the gutter (no overlap with content)
            scroll_btn_size = 20
            scroll_track_x = sidebar_x + self.sidebar_width - agents_gutter
            scroll_track_width = 18
            scroll_track_inner_width = 10
            scroll_track_inner_x = scroll_track_x + (scroll_track_width - scroll_track_inner_width) // 2

            if total_agents > agents_per_page:
                scroll_up_rect = pygame.Rect(scroll_track_x, agents_list_top, scroll_btn_size, scroll_btn_size)
                scroll_down_rect = pygame.Rect(scroll_track_x, agents_list_top + agents_list_height - scroll_btn_size, scroll_btn_size, scroll_btn_size)
                self.agent_scroll_up_rect = scroll_up_rect
                self.agent_scroll_down_rect = scroll_down_rect
                up_color = COLOR_BUTTON if self.agent_list_scroll > 0 else (50, 50, 50)
                down_color = COLOR_BUTTON if self.agent_list_scroll < max_scroll else (50, 50, 50)
                pygame.draw.rect(self.screen, up_color, scroll_up_rect)
                pygame.draw.rect(self.screen, (60, 60, 70), scroll_up_rect, 1)
                pygame.draw.rect(self.screen, down_color, scroll_down_rect)
                pygame.draw.rect(self.screen, (60, 60, 70), scroll_down_rect, 1)
                pygame.draw.polygon(self.screen, COLOR_TEXT, [
                    (scroll_up_rect.centerx, scroll_up_rect.top + 6),
                    (scroll_up_rect.left + 6, scroll_up_rect.bottom - 6),
                    (scroll_up_rect.right - 6, scroll_up_rect.bottom - 6)
                ])
                pygame.draw.polygon(self.screen, COLOR_TEXT, [
                    (scroll_down_rect.centerx, scroll_down_rect.bottom - 6),
                    (scroll_down_rect.left + 6, scroll_down_rect.top + 6),
                    (scroll_down_rect.right - 6, scroll_down_rect.top + 6)
                ])
                # Track between the two buttons
                scroll_track_rect = pygame.Rect(scroll_track_inner_x, agents_list_top + scroll_btn_size, scroll_track_inner_width, agents_list_height - 2 * scroll_btn_size)
                pygame.draw.rect(self.screen, (45, 45, 52), scroll_track_rect)
                pygame.draw.rect(self.screen, (65, 65, 75), scroll_track_rect, 1)
                thumb_height = max(28, int((agents_list_height - 2 * scroll_btn_size) * agents_per_page / total_agents))
                thumb_y = agents_list_top + scroll_btn_size + int((agents_list_height - 2 * scroll_btn_size - thumb_height) * self.agent_list_scroll / max_scroll) if max_scroll > 0 else agents_list_top + scroll_btn_size
                thumb_rect = pygame.Rect(scroll_track_inner_x + 1, thumb_y, scroll_track_inner_width - 2, thumb_height)
                pygame.draw.rect(self.screen, (85, 88, 105), thumb_rect)
                pygame.draw.rect(self.screen, (110, 115, 135), thumb_rect, 1)
            else:
                self.agent_scroll_up_rect = None
                self.agent_scroll_down_rect = None

            # Vertical divider between content and scroll gutter
            div_x = agents_content_right
            pygame.draw.line(self.screen, (55, 55, 65), (div_x, agents_list_top), (div_x, agents_list_top + agents_list_height), 1)

            visible_agents = state.agents[self.agent_list_scroll:self.agent_list_scroll + agents_per_page]
            for idx, agent in enumerate(visible_agents):
                agent_entry_start_y = y_offset
                agent_id = agent.get("id", "?")
                name = agent.get("name", "Unknown")
                oxygen = agent.get("oxygen", 0)
                calories = agent.get("calories", 0)
                integrity = agent.get("integrity", 0)
                status = agent.get("status", "active")
                loc = agent.get("location", (0, 0))
                is_selected = (self.selected_agent_id == agent_id and status != "dead")
                is_hovered = (self.hovered_agent_id == agent_id and status != "dead")
                row_hi = SIDEBAR_AGENT_ROW_PX - 6
                if is_hovered and not is_selected:
                    hover_rect = pygame.Rect(sidebar_x + 5, agent_entry_start_y - 3, agents_content_width - 10, row_hi)
                    pygame.draw.rect(self.screen, (70, 70, 30), hover_rect)
                    pygame.draw.rect(self.screen, (255, 255, 0), hover_rect, 1)
                if is_selected:
                    highlight_rect = pygame.Rect(sidebar_x + 5, agent_entry_start_y - 3, agents_content_width - 10, row_hi)
                    pygame.draw.rect(self.screen, (60, 80, 100), highlight_rect)
                    pygame.draw.rect(self.screen, (255, 255, 0), highlight_rect, 2)
                agent_text = f"{agent_id}: {name} ({status})"
                text_color = (150, 150, 150) if status == "dead" else (COLOR_TEXT if not is_selected else (255, 255, 200))
                text_surface = self.font_sidebar_body.render(agent_text, True, text_color)
                self.screen.blit(text_surface, (sidebar_x + 10, y_offset))
                y_offset += 14
                if status == "dead":
                    y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "O2", 0, (80, 80, 80), max_bar_width=agents_bar_max_width)
                    y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Cal", 0, (80, 80, 80), max_bar_width=agents_bar_max_width)
                    y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Int", 0, (80, 80, 80), max_bar_width=agents_bar_max_width)
                else:
                    y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "O2", oxygen, COLOR_RESOURCE_OXYGEN, max_bar_width=agents_bar_max_width)
                    y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Cal", calories, COLOR_RESOURCE_CALORIES, max_bar_width=agents_bar_max_width)
                    y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Int", integrity, COLOR_RESOURCE_INTEGRITY, max_bar_width=agents_bar_max_width)
                loc_text = f"  Loc: {loc[0]}, {loc[1]}"
                text_surface = self.font_sidebar_body.render(loc_text, True, (255, 255, 200) if is_selected else COLOR_TEXT)
                self.screen.blit(text_surface, (sidebar_x + 10, y_offset))
                y_offset += 12
                powers = self.agent_powerups.get(agent_id, set())
                if powers and status != "dead":
                    badges = []
                    if POWERUP_AUTO_OXYGEN in powers:
                        badges.append("O2")
                    if POWERUP_AUTO_CALORIES in powers:
                        badges.append("Cal")
                    if POWERUP_AUTO_INTEGRITY in powers:
                        badges.append("Int")
                    if badges:
                        auto_text = "Auto: " + " ".join(badges)
                        badge_surface = self.font_sidebar_body.render(auto_text, True, (150, 220, 150))
                        self.screen.blit(badge_surface, (sidebar_x + 10, y_offset))
                        y_offset += 12
                move_spd = float(agent.get("speed") or 1.0)
                if status != "dead" and move_spd > 1.02:
                    spd = self.font_sidebar_body.render(
                        f"  Move speed: ×{move_spd:.2f}",
                        True,
                        (180, 200, 255),
                    )
                    self.screen.blit(spd, (sidebar_x + 10, y_offset))
                    y_offset += 12
                y_offset += 12
                # Separator line between agents (stops at content edge, not under scrollbar)
                if idx < len(visible_agents) - 1:
                    line_y = y_offset
                    pygame.draw.line(self.screen, (70, 70, 80), (sidebar_x + 10, line_y), (agents_content_right - 6, line_y), 1)
                    y_offset += 5

        else:
            # Tasks tab
            self.recruit_button_rect = None
            self.advance_floor_button_rect = None
            self.agent_scroll_up_rect = None
            self.agent_scroll_down_rect = None
            self.event_task_rects = []
            tasks_title = self.font_sidebar_title.render("In progress", True, COLOR_TEXT)
            self.screen.blit(tasks_title, (sidebar_x + 10, y_offset))
            y_offset += 22
            for task in state.active_tasks:
                task_text = _format_sidebar_task_line(task)
                text_surface = self.font_sidebar_body.render(task_text, True, COLOR_TEXT)
                self.screen.blit(text_surface, (sidebar_x + 10, y_offset))
                y_offset += 16

            # Event tasks: tap a row to assign the nearest free agent
            y_offset += 6
            event_title = self.font_sidebar_title.render("Needs you", True, COLOR_TEXT)
            self.screen.blit(event_title, (sidebar_x + 10, y_offset))
            y_offset += 18
            hint = self.font_sidebar_body.render("Tap a row to dispatch someone nearby.", True, (130, 130, 145))
            self.screen.blit(hint, (sidebar_x + 10, y_offset))
            y_offset += 15

            unresolved_indices = [i for i, et in enumerate(self.event_tasks) if not et.get("resolved", False)]
            if unresolved_indices:
                for i in unresolved_indices:
                    et = self.event_tasks[i]
                    ev_type = str(et.get("event_type", "event")).replace("_", " ").title()
                    ev_loc = _format_event_task_location(et.get("location", ""))
                    row_rect = pygame.Rect(sidebar_x + 8, y_offset - 1, self.sidebar_width - 16, 17)
                    self.event_task_rects.append((row_rect, i))
                    pygame.draw.rect(self.screen, (75, 40, 40), row_rect)
                    pygame.draw.rect(self.screen, (200, 120, 120), row_rect, 1)
                    row_text = f"{ev_type} · {ev_loc}"
                    text_surface = self.font_sidebar_body.render(row_text, True, (255, 220, 220))
                    self.screen.blit(text_surface, (sidebar_x + 12, y_offset))
                    y_offset += 18
            else:
                none_text = self.font_sidebar_body.render("All quiet.", True, (140, 140, 140))
                self.screen.blit(none_text, (sidebar_x + 10, y_offset))
                y_offset += 16

            if not state.active_tasks and not unresolved_indices:
                no_tasks = self.font_sidebar_body.render("Nothing running right now.", True, (140, 140, 140))
                self.screen.blit(no_tasks, (sidebar_x + 10, y_offset))
        
    
    def _draw_resource_bar(self, x: int, y: int, label: str, value: float, color: Tuple[int, int, int]) -> int:
        """Draw a resource bar and return next y position."""
        label_text = self.font_sidebar_body.render(label, True, COLOR_TEXT)
        self.screen.blit(label_text, (x, y))

        bar_width = self.sidebar_width - 40
        bar_height = 13
        bar_x = x
        bar_y = y + 14

        # Background
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLOR_RESOURCE_BAR_BG, bg_rect)

        # Fill
        fill_width = int(bar_width * max(0, min(100, value)) / 100)
        fill_rect = pygame.Rect(bar_x, bar_y, fill_width, bar_height)
        pygame.draw.rect(self.screen, color, fill_rect)

        # Border
        pygame.draw.rect(self.screen, (0, 0, 0), bg_rect, 1)

        # Value text
        value_text = self.font_sidebar_body.render(f"{value:.1f}%", True, COLOR_TEXT)
        text_rect = value_text.get_rect(center=(bar_x + bar_width // 2, bar_y + bar_height // 2))
        self.screen.blit(value_text, text_rect)

        return bar_y + bar_height + 4

    def _draw_small_bar(self, x: int, y: int, label: str, value: float, color: Tuple[int, int, int], max_bar_width: Optional[int] = None) -> int:
        """Draw a small resource bar and return next y position. max_bar_width limits bar width (e.g. when scrollbar is present)."""
        bar_width = SIDEBAR_WIDTH - 50
        if max_bar_width is not None:
            bar_width = min(bar_width, max_bar_width)
        bar_height = 7

        # Label
        label_text = self.font_sidebar_body.render(f"{label}:", True, COLOR_TEXT)
        self.screen.blit(label_text, (x, y))

        # Bar
        bar_x = x + 22
        bar_y = y

        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLOR_RESOURCE_BAR_BG, bg_rect)

        fill_width = int(bar_width * max(0, min(100, value)) / 100)
        fill_rect = pygame.Rect(bar_x, bar_y, fill_width, bar_height)
        pygame.draw.rect(self.screen, color, fill_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), bg_rect, 1)

        return bar_y + bar_height + 2
    
    def _draw_event_notification(self):
        """Draw event notification centered over the gameplay area with a readable backdrop."""
        if self.current_event_text and self.event_start_time:
            current_time = pygame.time.get_ticks()
            elapsed = current_time - self.event_start_time

            if elapsed < self.event_duration:
                # Center on the gameplay (camera) area, independent of zoom
                center_x = self.camera_width // 2
                center_y = self.camera_height // 2

                # Render alert panel with better contrast and wrapped text for readability.
                body_max_w = int(self.camera_width * 0.78)
                words = str(self.current_event_text).split()
                lines: List[str] = []
                current_line = ""
                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    if self.font.size(test_line)[0] <= body_max_w:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
                if not lines:
                    lines = [str(self.current_event_text)]

                title_surface = self.font_large.render("ALERT", True, (255, 245, 245))
                body_surfaces = [self.font.render(line, True, (255, 235, 235)) for line in lines[:3]]
                title_h = title_surface.get_height()
                body_h = sum(s.get_height() for s in body_surfaces) + max(0, len(body_surfaces) - 1) * 4
                panel_w = max(
                    title_surface.get_width(),
                    max((s.get_width() for s in body_surfaces), default=0),
                ) + 36
                panel_h = title_h + body_h + 30
                panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
                panel_rect.center = (center_x, center_y)

                # Dark translucent panel + red border improves readability on any background.
                panel_surface = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
                panel_surface.fill((20, 8, 8, 220))
                self.screen.blit(panel_surface, panel_rect.topleft)
                pygame.draw.rect(self.screen, (235, 80, 80), panel_rect, 3, border_radius=6)
                pygame.draw.rect(self.screen, (120, 35, 35), panel_rect.inflate(-10, -10), 1, border_radius=6)

                title_rect = title_surface.get_rect(midtop=(panel_rect.centerx, panel_rect.top + 10))
                self.screen.blit(title_surface, title_rect)
                y = title_rect.bottom + 6
                for s in body_surfaces:
                    r = s.get_rect(midtop=(panel_rect.centerx, y))
                    self.screen.blit(s, r)
                    y += s.get_height() + 4
            else:
                # Clear event after duration
                self.current_event_text = None
                self.event_start_time = None
    
    def _show_event(self, event_description: str):
        """Show an event notification."""
        self.current_event_text = event_description
        self.event_start_time = pygame.time.get_ticks()

    def _event_location_to_world(self, location: Any) -> Optional[Tuple[int, int]]:
        """
        Convert an event location (node id, station id, or coordinates) to world (x, y).
        Returns None if it cannot be mapped.
        """
        if location is None:
            return None
        if isinstance(location, (tuple, list)) and len(location) == 2:
            try:
                x = int(location[0])
                y = int(location[1])
                return (
                    max(WORLD_MIN_X, min(WORLD_MAX_X - 1, x)),
                    max(WORLD_MIN_Y, min(WORLD_MAX_Y - 1, y)),
                )
            except (TypeError, ValueError):
                return None
        if isinstance(location, str):
            # Station IDs in visual layer
            for station in self.resource_stations:
                if station.station_id == location:
                    return (station.center_x, station.center_y)
            # Graph node IDs in planner
            if self.game and self.game.task_planner and self.game.task_planner.graph:
                node_pos = self.game.task_planner.graph.node_positions.get(location)
                if node_pos:
                    return (
                        max(WORLD_MIN_X, min(WORLD_MAX_X - 1, int(node_pos[0]))),
                        max(WORLD_MIN_Y, min(WORLD_MAX_Y - 1, int(node_pos[1]))),
                    )
        return None

    def _add_event_task(self, event_type: str, event_location: Any):
        """Add (or refresh) an event task entry in the Tasks tab."""
        if not event_type:
            return
        # If same unresolved event+location already exists, keep a single row.
        for task in self.event_tasks:
            if (
                not task.get("resolved", False)
                and task.get("event_type") == event_type
                and task.get("location") == event_location
            ):
                task["turn_seen"] = self.game.get_state().turn_number if self.game else 0
                return
        self.event_tasks.append(
            {
                "event_type": event_type,
                "location": event_location,
                "resolved": False,
                "assigned_agent_id": None,
                "turn_seen": self.game.get_state().turn_number if self.game else 0,
            }
        )

    def _dispatch_closest_agent_to_event_task(self, event_task_index: int):
        """Send the closest alive/reachable agent to the clicked event task location."""
        if not self.game:
            return
        if event_task_index < 0 or event_task_index >= len(self.event_tasks):
            return
        event_task = self.event_tasks[event_task_index]
        if event_task.get("resolved", False):
            return

        target = self._event_location_to_world(event_task.get("location"))
        if target is None:
            self._show_event("Event location is not reachable on map")
            return
        tx, ty = target

        state = self.game.get_state()
        living_agents = [a for a in state.agents if a.get("status") != "dead"]
        if not living_agents:
            self._show_event("No living agents to dispatch")
            return

        # Busy agents cannot be recruited for new event-response tasks.
        # "Busy" means either currently moving on a path or assigned in active_tasks.
        active_task_agent_ids = {
            t.get("agent_id")
            for t in state.active_tasks
            if t.get("agent_id") is not None and t.get("progress", 0.0) < 1.0
        }
        # Repairs are tracked in infrastructure, not in active_tasks.
        repair_agent_ids = set()
        failed_station_tiles = set()
        infra = state.infrastructure or {}
        for station in self.resource_stations:
            info = infra.get(station.station_id, {})
            if not isinstance(info, dict):
                continue
            if info.get("status") != "failed":
                continue
            repair_agent_id = info.get("repair_agent_id")
            if repair_agent_id is not None:
                repair_agent_ids.add(repair_agent_id)
            for tile_xy in station.get_tiles():
                failed_station_tiles.add(tile_xy)

        # Agents physically on failed station footprints are considered busy repairing,
        # even if repair_agent_id has not yet been assigned this turn.
        on_failed_station_ids = set()
        for agent in living_agents:
            aid = agent.get("id")
            loc = agent.get("location")
            if aid is None or not isinstance(loc, (tuple, list)) or len(loc) != 2:
                continue
            if (int(loc[0]), int(loc[1])) in failed_station_tiles:
                on_failed_station_ids.add(aid)

        available_agents = []
        for agent in living_agents:
            aid = agent.get("id")
            if aid is None:
                continue
            path_busy = aid in self.agent_paths and len(self.agent_paths.get(aid, [])) > 0
            task_busy = aid in active_task_agent_ids
            repair_busy = aid in repair_agent_ids or aid in on_failed_station_ids
            if not path_busy and not task_busy and not repair_busy:
                available_agents.append(agent)

        if not available_agents:
            self._show_event("All agents busy")
            return

        best_agent_id: Optional[int] = None
        best_path_len: Optional[int] = None
        for agent in available_agents:
            agent_id = agent.get("id")
            if agent_id is None:
                continue
            path = self.game.get_path_for_agent_to_location(agent_id, tx, ty)
            if not path:
                continue
            plen = len(path)
            if best_path_len is None or plen < best_path_len:
                best_path_len = plen
                best_agent_id = agent_id

        if best_agent_id is None:
            self._show_event("No reachable agent for this event")
            return

        # Assign the closest agent immediately.
        self.selected_agent_id = best_agent_id
        self._assign_task_at(tx, ty, agent_id=best_agent_id)
        event_task["resolved"] = True
        event_task["assigned_agent_id"] = best_agent_id
        self._show_event(f"Agent {best_agent_id} dispatched to event")
    
    def _draw_map(self):
        """Draw the procedural tile map (finite world with bounds)."""
        state = self.game.get_state()
        
        # Calculate visible tile range based on zoom level
        # When zoomed out, tiles are smaller, so we need to draw more tiles to fill the screen
        scaled_tile_size = self._get_scaled_tile_size()
        
        # Calculate how many tiles fit on screen (with padding for edge tiles)
        tiles_x = int(self.camera_width / scaled_tile_size) + 4
        tiles_y = int(self.camera_height / scaled_tile_size) + 4
        
        # Convert camera position to integers for range()
        camera_x_int = int(self.camera_x)
        camera_y_int = int(self.camera_y)
        
        start_x = camera_x_int - tiles_x // 2
        start_y = camera_y_int - tiles_y // 2
        
        # Clamp to world bounds
        start_x = max(WORLD_MIN_X, min(WORLD_MAX_X - tiles_x, start_x))
        start_y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - tiles_y, start_y))
        
        # Draw visible tiles (only within world bounds)
        for y in range(start_y, min(start_y + tiles_y, WORLD_MAX_Y)):
            for x in range(start_x, min(start_x + tiles_x, WORLD_MAX_X)):
                if WORLD_MIN_X <= x < WORLD_MAX_X and WORLD_MIN_Y <= y < WORLD_MAX_Y:
                    tile = state.get_tile_at(x, y)
                    self._draw_tile(x, y, tile["terrain"])
        
        # Draw world boundary indicators
        self._draw_world_bounds()

    def _draw_trees(self):
        """Draw harvestable trees from ColonyState.world_trees (on top of terrain)."""
        if not self.game:
            return
        state = self.game.get_state()
        ts = self._get_scaled_tile_size()
        scaled_tile_size = ts
        tiles_x = int(self.camera_width / scaled_tile_size) + 4
        tiles_y = int(self.camera_height / scaled_tile_size) + 4
        camera_x_int = int(self.camera_x)
        camera_y_int = int(self.camera_y)
        start_x = max(WORLD_MIN_X, min(WORLD_MAX_X - tiles_x, camera_x_int - tiles_x // 2))
        start_y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - tiles_y, camera_y_int - tiles_y // 2))
        end_x = min(start_x + tiles_x, WORLD_MAX_X)
        end_y = min(start_y + tiles_y, WORLD_MAX_Y)
        margin = 2
        vmin_x, vmax_x = start_x - margin, end_x + margin
        vmin_y, vmax_y = start_y - margin, end_y + margin
        for t in state.world_trees or []:
            if len(t) < 2:
                continue
            wx, wy = int(t[0]), int(t[1])
            if not (WORLD_MIN_X <= wx < WORLD_MAX_X and WORLD_MIN_Y <= wy < WORLD_MAX_Y):
                continue
            if wx < vmin_x or wx >= vmax_x or wy < vmin_y or wy >= vmax_y:
                continue
            sx, sy = self._world_to_screen(wx, wy)
            trunk_r = max(2, int(ts * 0.12))
            fol_r = max(4, int(ts * 0.28))
            pygame.draw.circle(
                self.screen, COLOR_TREE_FOLIAGE, (int(sx), int(sy - fol_r // 2)), fol_r
            )
            pygame.draw.rect(
                self.screen,
                COLOR_TREE_TRUNK,
                (int(sx) - trunk_r // 2, int(sy), trunk_r, int(ts * 0.22)),
            )

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode and refresh dynamic layout dimensions."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.window_width, self.window_height = self.screen.get_size()
            self.camera_width = int(self.window_width * 0.7)
            self.sidebar_width = self.window_width - self.camera_width
            self.camera_height = self.window_height
        else:
            self.screen = pygame.display.set_mode(self.original_size)
            self.window_width, self.window_height = self.original_size
            self.camera_width = CAMERA_WIDTH
            self.camera_height = CAMERA_HEIGHT
            self.sidebar_width = SIDEBAR_WIDTH
    
    def _handle_input(self):
        """Handle keyboard and mouse input."""
        keys = pygame.key.get_pressed()
        
        # Zoom controls
        if keys[pygame.K_EQUALS] or keys[pygame.K_PLUS]:  # Zoom in
            self.zoom_level = min(self.zoom_max, self.zoom_level + 0.05)
        if keys[pygame.K_MINUS]:  # Zoom out
            self.zoom_level = max(self.zoom_min, self.zoom_level - 0.05)
        
        # Camera movement (clamped to world bounds)
        camera_speed = 0.5
        if keys[pygame.K_w]:
            self.camera_y = max(WORLD_MIN_Y + CAMERA_HEIGHT // (2 * TILE_SIZE), 
                              self.camera_y - camera_speed)
        if keys[pygame.K_s]:
            self.camera_y = min(WORLD_MAX_Y - CAMERA_HEIGHT // (2 * TILE_SIZE), 
                              self.camera_y + camera_speed)
        if keys[pygame.K_a]:
            self.camera_x = max(WORLD_MIN_X + CAMERA_WIDTH // (2 * TILE_SIZE), 
                              self.camera_x - camera_speed)
        if keys[pygame.K_d]:
            self.camera_x = min(WORLD_MAX_X - CAMERA_WIDTH // (2 * TILE_SIZE), 
                              self.camera_x + camera_speed)
        
        # Mouse clicks, wheel, and window events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # Pause when window loses focus; resume when it gains focus again
            # Use both modern WINDOWFOCUS events and legacy ACTIVEEVENT as fallback.
            if event.type == getattr(pygame, "WINDOWFOCUSLOST", None):
                self.paused = True
            elif event.type == getattr(pygame, "WINDOWFOCUSGAINED", None):
                self.paused = False
                # Reset timers so turns/decay don't jump while paused
                now = pygame.time.get_ticks()
                self.last_turn_time = now
                self.last_decay_time = now
            elif event.type == getattr(pygame, "ACTIVEEVENT", None):
                # state bit 2 = focus, gain 0 = lost, 1 = gained
                if getattr(event, "state", 0) & 2:
                    if getattr(event, "gain", 0) == 0:
                        self.paused = True
                    else:
                        self.paused = False
                        now = pygame.time.get_ticks()
                        self.last_turn_time = now
                        self.last_decay_time = now
            
            if event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                # Agent list scrolling only when Agents tab is active and mouse over sidebar
                if mouse_x >= self.camera_width and self.game and self.sidebar_tab == "agents":
                    state = self.game.get_state()
                    total_agents = len(state.agents)
                    agents_per_page = 5
                    if total_agents > agents_per_page:
                        if event.y > 0:
                            self.agent_list_scroll = max(0, self.agent_list_scroll - 1)
                        elif event.y < 0:
                            self.agent_list_scroll = min(max(0, total_agents - agents_per_page), self.agent_list_scroll + 1)
                elif mouse_x < self.camera_width:
                    # Zoom controls (when mouse is over game area)
                    if event.y > 0:
                        self.zoom_level = min(self.zoom_max, self.zoom_level + 0.1)
                    elif event.y < 0:
                        self.zoom_level = max(self.zoom_min, self.zoom_level - 0.1)
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self._toggle_fullscreen()
                elif event.key == pygame.K_ESCAPE:
                    # Open confirmation overlay instead of instantly quitting
                    self.confirm_quit_selection = 0
                    self.game_state = STATE_CONFIRM_QUIT
                    return True
                elif self.game:
                    ch = ""
                    if event.unicode and len(event.unicode) == 1 and event.unicode.isdigit():
                        ch = event.unicode
                    elif pygame.K_0 <= event.key <= pygame.K_9:
                        ch = str(event.key - pygame.K_0)
                    elif pygame.K_KP0 <= event.key <= pygame.K_KP9:
                        ch = str(event.key - pygame.K_KP0)
                    if len(ch) == 1 and ch.isdigit():
                        nw = len(DEV_WOOD_CHEAT_CODE)
                        self._dev_wood_cheat_buffer = (self._dev_wood_cheat_buffer + ch)[-nw:]
                        if self._dev_wood_cheat_buffer == DEV_WOOD_CHEAT_CODE:
                            self._apply_dev_wood_cheat()
                            self._dev_wood_cheat_buffer = ""
                        ns = len(DEV_SPEED_CHEAT_CODE)
                        self._dev_speed_cheat_buffer = (self._dev_speed_cheat_buffer + ch)[-ns:]
                        if self._dev_speed_cheat_buffer == DEV_SPEED_CHEAT_CODE:
                            self._apply_dev_speed_powerups_cheat()
                            self._dev_speed_cheat_buffer = ""
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                mouse_pos = (mouse_x, mouse_y)
                
                # Sidebar interactions
                if mouse_x >= self.camera_width:
                    tab_clicked = False
                    if hasattr(self, 'sidebar_tab_rects') and self.sidebar_tab_rects:
                        for i, tr in enumerate(self.sidebar_tab_rects):
                            if tr.collidepoint(mouse_pos):
                                tabs = ["colony", "agents", "tasks"]
                                if i < len(tabs):
                                    self.sidebar_tab = tabs[i]
                                tab_clicked = True
                                break
                    if not tab_clicked:
                        if self.sidebar_tab == "agents":
                            if hasattr(self, 'agent_scroll_up_rect') and self.agent_scroll_up_rect and self.agent_scroll_up_rect.collidepoint(mouse_pos):
                                self.agent_list_scroll = max(0, self.agent_list_scroll - 1)
                            elif hasattr(self, 'agent_scroll_down_rect') and self.agent_scroll_down_rect and self.agent_scroll_down_rect.collidepoint(mouse_pos):
                                self.agent_list_scroll = min(max(0, len(self.game.get_state().agents) - 5), self.agent_list_scroll + 1)
                        if self.sidebar_tab == "tasks" and event.button == 1:
                            for rect, event_idx in self.event_task_rects:
                                if rect.collidepoint(mouse_pos):
                                    self._dispatch_closest_agent_to_event_task(event_idx)
                                    break
                        if self.sidebar_tab == "colony" and hasattr(self, 'recruit_button_rect') and self.recruit_button_rect and self.recruit_button_rect.collidepoint(mouse_pos):
                            self._recruit_agent()
                        if self.sidebar_tab == "colony" and getattr(self, "advance_floor_button_rect", None) and self.advance_floor_button_rect.collidepoint(mouse_pos):
                            self._advance_to_next_floor()
                
                # Check if click is in game area
                if mouse_x < self.camera_width:
                    if event.button == 1:  # Left click - select or start drag
                        # First, hit-test against sprite rects in screen space so hitbox matches PNG
                        agent_here = self._get_agent_id_at_screen(mouse_x, mouse_y)
                        if agent_here is not None:
                            self.drag_agent_id = agent_here
                            self.drag_start_screen = (mouse_x, mouse_y)
                            self.selected_agent_id = agent_here
                        else:
                            # Fallback to tile-based selection for keyboard/edge cases
                            world_x, world_y = self._screen_to_world_tile(mouse_x, mouse_y)
                            self._select_agent_at(world_x, world_y)
                    elif event.button == 3:  # Right click - assign task
                        world_x, world_y = self._screen_to_world_tile(mouse_x, mouse_y)
                        if self.selected_agent_id is not None:
                            self._assign_task_at(world_x, world_y)
            
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.drag_agent_id is not None:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    if mouse_x < self.camera_width:
                        world_x, world_y = self._screen_to_world_tile(mouse_x, mouse_y)
                        self._assign_task_at(world_x, world_y, agent_id=self.drag_agent_id)
                    self.drag_agent_id = None
                    self.drag_start_screen = None
        
        return True

    def _handle_confirm_quit_input(self):
        """Handle input for the ESC quit confirmation overlay (pauses gameplay updates)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_n):
                    self.game_state = STATE_PLAYING
                    return True
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_y):
                    # Quit to menu
                    self.game_state = STATE_MENU
                    self.game = None
                    return True
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                    self.confirm_quit_selection = 1 - self.confirm_quit_selection

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if self.confirm_resume_rect and self.confirm_resume_rect.collidepoint(mouse_pos):
                    self.game_state = STATE_PLAYING
                    return True
                if self.confirm_quit_rect and self.confirm_quit_rect.collidepoint(mouse_pos):
                    self.game_state = STATE_MENU
                    self.game = None
                    return True

        return True

    def _handle_game_over_input(self):
        """Handle input on the Game Over screen."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                # Any key: return to main menu
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_y, pygame.K_n):
                    self.game_state = STATE_MENU
                    self.game = None
                    return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Any click: return to main menu
                self.game_state = STATE_MENU
                self.game = None
                return True
        return True

    def _draw_confirm_quit_overlay(self):
        """Draw a simple confirmation overlay on top of the game view."""
        # Dim the screen
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Panel
        panel_w, panel_h = 420, 200
        panel_x = WINDOW_WIDTH // 2 - panel_w // 2
        panel_y = WINDOW_HEIGHT // 2 - panel_h // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, (40, 40, 55), panel_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT, panel_rect, 2)

        title = self.font_large.render("Quit to Menu?", True, COLOR_TEXT)
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 50)))

        subtitle = self.font_small.render("Your current game will be lost.", True, (180, 180, 200))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 85)))

        # Buttons
        btn_w, btn_h = 150, 44
        gap = 30
        resume_rect = pygame.Rect(WINDOW_WIDTH // 2 - gap // 2 - btn_w, panel_y + 120, btn_w, btn_h)
        quit_rect = pygame.Rect(WINDOW_WIDTH // 2 + gap // 2, panel_y + 120, btn_w, btn_h)
        self.confirm_resume_rect = resume_rect
        self.confirm_quit_rect = quit_rect

        resume_color = COLOR_BUTTON_SELECTED if self.confirm_quit_selection == 0 else COLOR_BUTTON
        quit_color = COLOR_BUTTON_SELECTED if self.confirm_quit_selection == 1 else COLOR_BUTTON

        pygame.draw.rect(self.screen, resume_color, resume_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT, resume_rect, 2)
        pygame.draw.rect(self.screen, quit_color, quit_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT, quit_rect, 2)

        resume_text = self.font.render("Resume", True, COLOR_TEXT)
        quit_text = self.font.render("Quit", True, COLOR_TEXT)
        self.screen.blit(resume_text, resume_text.get_rect(center=resume_rect.center))
        self.screen.blit(quit_text, quit_text.get_rect(center=quit_rect.center))

    def _draw_game_over_screen(self):
        """Draw a dedicated Game Over screen with explanation and prompt."""
        self.screen.fill(COLOR_MENU_BG)

        title = self.font_large.render("Game Over", True, COLOR_TEXT)
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 140)))

        reason = self.last_game_over_reason or "The colony has failed."
        # Wrap reason into a few lines if long
        y = 200
        max_width = WINDOW_WIDTH - 120
        words = reason.split()
        line = ""
        lines: List[str] = []
        for w in words:
            test = (line + " " + w).strip()
            surf = self.font_small.render(test, True, COLOR_TEXT)
            if surf.get_width() > max_width and line:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)

        for l in lines:
            surf = self.font_small.render(l, True, COLOR_TEXT)
            self.screen.blit(surf, surf.get_rect(center=(WINDOW_WIDTH // 2, y)))
            y += 28

        prompt = self.font.render("Press any key or click to return to the main menu.", True, (200, 200, 220))
        self.screen.blit(prompt, prompt.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 120)))
    
    def _get_agent_id_at_screen(self, screen_x: int, screen_y: int) -> Optional[int]:
        """Return agent id at screen coordinates if the click intersects the drawn sprite rect."""
        if not self.game:
            return None
        state = self.game.get_state()
        for agent_id, rect in self.agent_sprite_rects.items():
            # Only consider living agents
            agent = state.get_agent_by_id(agent_id)
            if not agent or agent.get("status") == "dead":
                continue
            if rect.collidepoint(screen_x, screen_y):
                return agent_id
        return None
    
    def _select_agent_at(self, world_x: int, world_y: int):
        """Select agent at world coordinates, using the same tighter circular hitbox. Skips dead agents."""
        state = self.game.get_state()
        self.selected_agent_id = None
        
        for agent in state.agents:
            # Skip dead agents
            if agent.get("status") == "dead":
                continue
            loc = agent.get("location")
            if loc and isinstance(loc, (tuple, list)) and len(loc) == 2:
                ax, ay = float(loc[0]), float(loc[1])
                dx = ax - float(world_x)
                dy = ay - float(world_y)
                if dx * dx + dy * dy <= 0.75 * 0.75:
                    self.selected_agent_id = agent.get("id")
                    break
    
    def _recruit_agent(self):
        """Purchase a new agent if average resources allow."""
        if not self.game:
            return
        state = self.game.get_state()
        agents = [a for a in state.agents if a.get("status") != "dead"]
        if not agents:
            return
        cost = {"oxygen": 30, "calories": 30, "integrity": 30}
        # Check average resources
        avg_resources = {
            "oxygen": sum(a.get("oxygen", 0) for a in agents) / len(agents),
            "calories": sum(a.get("calories", 0) for a in agents) / len(agents),
            "integrity": sum(a.get("integrity", 0) for a in agents) / len(agents),
        }
        if any(avg_resources[r] < cost[r] for r in cost):
            return
        # Deduct cost from all agents equally
        cost_per_agent = {r: cost[r] / len(agents) for r in cost}
        for agent in agents:
            for r, amt in cost_per_agent.items():
                current = agent.get(r, 100.0)
                agent[r] = max(0.0, current - amt)
        next_id = max((a.get("id", -1) for a in state.agents), default=-1) + 1
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"]
        spawn = self._find_empty_spawn_tile()
        if spawn is None:
            return
        x, y = spawn
        agent_data = {
            "id": next_id,
            "name": names[next_id % len(names)],
            "oxygen": 80.0, "calories": 70.0, "integrity": 90.0,
            "location": (x, y), "status": "active"
        }
        state.add_agent(agent_data)
        self.game.task_planner.colony_state = state
        self._show_event("Agent recruited!")
    
    def _find_empty_spawn_tile(self) -> Optional[Tuple[int, int]]:
        """Find a passable tile not occupied by agent or station (for initial spawn only - agents can move through each other)."""
        state = self.game.get_state()
        occupied = set()
        # Only check living agents for spawn placement (dead agents don't block)
        for a in state.agents:
            if a.get("status") == "dead":
                continue
            loc = a.get("location")
            if loc and len(loc) == 2:
                occupied.add((int(loc[0]), int(loc[1])))
        for station in self.resource_stations:
            occupied.update(station.get_tiles())
        for r in range(0, 25):
            for x in range(max(WORLD_MIN_X, -r), min(WORLD_MAX_X, r + 1)):
                for y in range(max(WORLD_MIN_Y, -r), min(WORLD_MAX_Y, r + 1)):
                    if abs(x) != r and abs(y) != r:
                        continue
                    if (x, y) in occupied:
                        continue
                    tile = state.get_tile_at(x, y)
                    if tile.get("passable", True):
                        return (x, y)
        return None
    
    def _assign_task_at(self, world_x: int, world_y: int, agent_id: Optional[int] = None):
        """
        Assign movement destination to the given agent. Movement starts immediately.
        If clicking on a station, sends agent to that station.
        """
        target_agent = agent_id if agent_id is not None else self.selected_agent_id
        if target_agent is None or not self.game:
            return
        
        # Check if agent is dead
        state = self.game.get_state()
        agent = state.get_agent_by_id(target_agent)
        if not agent or agent.get("status") == "dead":
            self._show_event("Cannot command dead agent!")
            return
        
        # Check if clicking on a station
        station = self._get_station_at(world_x, world_y)
        if station:
            world_x, world_y = station.center_x, station.center_y
        
        # Clamp to world bounds
        world_x = max(WORLD_MIN_X, min(WORLD_MAX_X - 1, world_x))
        world_y = max(WORLD_MIN_Y, min(WORLD_MAX_Y - 1, world_y))
        
        # Get path immediately and start movement right away
        path_coords = self.game.get_path_for_agent_to_location(target_agent, world_x, world_y)
        if not path_coords:
            self._show_event("No path found to destination!")
            return
        
        path_coords = list(path_coords)
        loc = agent.get("location")
        if loc and len(path_coords) > 0 and path_coords[0] == (int(loc[0]), int(loc[1])):
            path_coords = path_coords[1:]
        
        # Check if pathfinding actually found a valid path
        # If path only has start or start+goal but goal is unreachable, it's a failure
        if len(path_coords) == 0:
            self._show_event("No path found to destination!")
            return
        
        # Check if goal is reachable (path should end at or near goal)
        goal = (world_x, world_y)
        path_end = path_coords[-1]
        # If path ends far from goal, pathfinding failed
        if abs(path_end[0] - goal[0]) > 1 or abs(path_end[1] - goal[1]) > 1:
            self._show_event("No path found to destination!")
            return
        
        # Valid path found, assign it
        self.agent_paths[target_agent] = path_coords
    
    def _update_smooth_agent_movement(self, dt_sec: float):
        """
        Move agents smoothly along their paths using delta time.
        Runs every frame; resource draining is separate (turn timer).
        """
        if not self.game or dt_sec <= 0:
            return
        state = self.game.get_state()
        to_remove: List[int] = []
        
        for agent_id, path in list(self.agent_paths.items()):
            if not path:
                to_remove.append(agent_id)
                self.agent_visual_pos.pop(agent_id, None)
                continue
            agent_index = next((i for i, a in enumerate(state.agents) if a.get("id") == agent_id), None)
            if agent_index is None:
                to_remove.append(agent_id)
                self.agent_visual_pos.pop(agent_id, None)
                continue
            current_loc = state.agents[agent_index].get("location")
            if not current_loc or not isinstance(current_loc, (tuple, list)) or len(current_loc) != 2:
                to_remove.append(agent_id)
                self.agent_visual_pos.pop(agent_id, None)
                continue
            cur_x, cur_y = float(current_loc[0]), float(current_loc[1])
            # Use visual pos if we're mid-step, else current location
            vx, vy = self.agent_visual_pos.get(agent_id, (cur_x, cur_y))
            agent_move = self.agent_move_speed * dt_sec * effective_move_multiplier(
                state.agents[agent_index], state.turn_number
            )
            
            # Skip path points we've already reached (use distance check for smoother diagonal movement)
            while path:
                tx, ty = float(path[0][0]), float(path[0][1])
                dx_check = tx - vx
                dy_check = ty - vy
                dist_to_next = math.sqrt(dx_check * dx_check + dy_check * dy_check)
                
                # If we're very close to the next waypoint (within 0.1 tiles), consider it reached
                if dist_to_next < 0.1:
                    reached = path.pop(0)
                    vx, vy = float(reached[0]), float(reached[1])
                    state.update_agent(
                        agent_index, {"location": (int(round(vx)), int(round(vy)))}, validate=False
                    )
                    try_harvest_trees(state, [(int(round(vx)), int(round(vy)))])
                    if not path:
                        to_remove.append(agent_id)
                        self.agent_visual_pos.pop(agent_id, None)
                        break
                else:
                    break
            
            if not path:
                continue
            
            # Move toward path[0] with smooth interpolation
            tx, ty = float(path[0][0]), float(path[0][1])
            ix, iy = int(round(tx)), int(round(ty))
            if not (
                WORLD_MIN_X <= ix < WORLD_MAX_X
                and WORLD_MIN_Y <= iy < WORLD_MAX_Y
            ):
                path.pop(0)
                if not path:
                    to_remove.append(agent_id)
                    self.agent_visual_pos.pop(agent_id, None)
                continue

            # Water slows (~0.2x): O(1) from engine terrain grid
            if self.game:
                tile_speed = self.game.terrain_move_speed_at(ix, iy)
            else:
                tile_speed = float(
                    state.get_tile_at(ix, iy).get("move_speed", 1.0)
                )
            step_move_dist = agent_move * tile_speed
            
            # Calculate direction vector (normalized for smooth diagonal movement)
            dx, dy = tx - vx, ty - vy
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist <= 0.05:  # Very close, snap to target
                path.pop(0)
                vx, vy = tx, ty
                state.update_agent(
                    agent_index, {"location": (int(round(tx)), int(round(ty)))}, validate=False
                )
                try_harvest_trees(state, [(int(round(tx)), int(round(ty)))])
                self.agent_visual_pos[agent_id] = (vx, vy)
                if not path:
                    to_remove.append(agent_id)
                    self.agent_visual_pos.pop(agent_id, None)
            else:
                # Smooth movement: move along direction vector
                step = min(step_move_dist, dist)
                # Normalize direction for smooth diagonal movement
                if dist > 0:
                    vx += (dx / dist) * step
                    vy += (dy / dist) * step
                self.agent_visual_pos[agent_id] = (vx, vy)
                
                # Check if we've reached the waypoint
                new_dx = tx - vx
                new_dy = ty - vy
                new_dist = math.sqrt(new_dx * new_dx + new_dy * new_dy)
                if new_dist < 0.1 or step >= dist - 0.05:
                    path.pop(0)
                    vx, vy = tx, ty
                    state.update_agent(
                        agent_index, {"location": (int(round(tx)), int(round(ty)))}, validate=False
                    )
                    try_harvest_trees(state, [(int(round(tx)), int(round(ty)))])
                    self.agent_visual_pos[agent_id] = (vx, vy)
                    if not path:
                        to_remove.append(agent_id)
                        self.agent_visual_pos.pop(agent_id, None)
        
        for aid in to_remove:
            self.agent_paths.pop(aid, None)
            # When agent stops moving, clear selection and hover so highlight goes away
            if self.selected_agent_id == aid:
                self.selected_agent_id = None
            if self.hovered_agent_id == aid:
                self.hovered_agent_id = None
    
    def _store_paths_from_assignments(self, assignments: List[Dict[str, Any]]):
        """Store path_coords from turn report assignments into agent_paths."""
        for a in assignments or []:
            agent_id = a.get("agent_id")
            path_coords = a.get("path_coords")
            if agent_id is not None and path_coords:
                path_coords = list(path_coords)
                # Skip first point if it's the agent's current location
                state = self.game.get_state()
                agent = state.get_agent_by_id(agent_id)
                if agent:
                    loc = agent.get("location")
                    if loc and len(path_coords) > 0 and path_coords[0] == (int(loc[0]), int(loc[1])):
                        path_coords = path_coords[1:]
                if path_coords:
                    self.agent_paths[agent_id] = path_coords
    
    def _check_agent_deaths(self):
        """Check if any agent's resource reached 0 and mark as dead."""
        if not self.game:
            return
        state = self.game.get_state()
        for i, agent in enumerate(state.agents):
            if agent.get("status") == "dead":
                continue
            oxygen = agent.get("oxygen", 100.0)
            calories = agent.get("calories", 100.0)
            integrity = agent.get("integrity", 100.0)
            if oxygen <= 0 or calories <= 0 or integrity <= 0:
                state.update_agent(i, {"status": "dead"}, validate=False)
                state.floor_deaths_count = int(getattr(state, "floor_deaths_count", 0)) + 1
                agent_id = agent.get("id")
                if agent_id in self.agent_paths:
                    self.agent_paths.pop(agent_id)
                if agent_id in self.agent_visual_pos:
                    self.agent_visual_pos.pop(agent_id)
                self._show_event(f"Agent {agent.get('name', agent_id)} died!")
    
    def _apply_natural_decay(self, dt_sec: float):
        """
        Apply continuous natural resource decay to all agent resources based on elapsed time.
        Creates smooth, continuous pressure to visit resource stations regularly.
        
        Args:
            dt_sec: Time elapsed since last update in seconds
        """
        if not self.game or dt_sec <= 0:
            return
        state = self.game.get_state()
        # Decay rates per second - continuous smooth decay (multiplied by decay_multiplier)
        # At default 12s turn interval with multiplier 1.0, this matches previous per-turn rates:
        # oxygen: 4.0/12 = 0.333/sec, calories: 3.0/12 = 0.25/sec, integrity: 2.0/12 = 0.167/sec
        base_decay_rates_per_second = {
            "oxygen": 0.333,      # Oxygen depletes fastest (harsh)
            "calories": 0.25,     # Calories decay quickly
            "integrity": 0.167,   # Integrity decays moderately
        }
        decay_rates_per_second = {
            k: v * self.decay_multiplier for k, v in base_decay_rates_per_second.items()
        }
        for i, agent in enumerate(state.agents):
            if agent.get("status") == "dead":
                continue
            current_oxygen = agent.get("oxygen", 100.0)
            current_calories = agent.get("calories", 100.0)
            current_integrity = agent.get("integrity", 100.0)
            updates = {
                "oxygen": max(0.0, current_oxygen - decay_rates_per_second["oxygen"] * dt_sec),
                "calories": max(0.0, current_calories - decay_rates_per_second["calories"] * dt_sec),
                "integrity": max(0.0, current_integrity - decay_rates_per_second["integrity"] * dt_sec),
            }
            state.update_agent(i, updates, validate=False)
    
    def _update_game(self):
        """Update game state (automatic turn progression)."""
        if not self.game:
            return
        
        current_time = pygame.time.get_ticks()
        
        # Apply continuous resource decay every frame (smooth, not chunked)
        if self.last_decay_time > 0:
            dt_ms = current_time - self.last_decay_time
            dt_sec = dt_ms / 1000.0
            # Cap dt_sec to prevent large spikes (e.g., if game was paused)
            if dt_sec > 0 and dt_sec < 1.0:  # Max 1 second per frame
                self._apply_natural_decay(dt_sec)
                # Check for deaths after decay
                self._check_agent_deaths()
        self.last_decay_time = current_time
        
        # Check if it's time for next turn (adversarial events, task planning, etc.)
        if current_time - self.last_turn_time >= self.turn_timer:
            self.last_turn_time = current_time
            
            # Check for agent deaths before turn
            self._check_agent_deaths()
            
            # Execute turn with pending tasks (no agent movement here - that's smooth/frame-based)
            player_tasks = self.pending_tasks.copy()
            self.pending_tasks.clear()
            
            # Execute turn with selected algorithm
            turn_report = self.game.execute_turn(player_tasks if player_tasks else None, algorithm=self.algorithm)
            self.last_survival_assessment = turn_report.get("survival_assessment")
            turns_state = self.game.get_state()
            prune_expired_speed_boosts(turns_state.agents, turns_state.turn_number)
            self._ensure_viewport_trees_turn()
            self._maybe_spawn_turn_powerup(turns_state)
            
            # Check for deaths after turn (resources may have drained)
            self._check_agent_deaths()
            
            # Store paths from new assignments for walking
            planning = turn_report.get("phases", {}).get("planning", {})
            self._store_paths_from_assignments(planning.get("assignments", []))
            
            # Show event notification
            event_info = turn_report.get("phases", {}).get("adversarial", {})
            resolution_info = turn_report.get("phases", {}).get("resolution", {})
            specific_effects = resolution_info.get("specific_effects", {})
            event_type = event_info.get("event_selected", "")
            # Prefer concrete station target if provided (station_breakdown),
            # fall back to generic event location for other events.
            event_location = event_info.get("target_station_id") or event_info.get("location", "")
            target_agent_id = event_info.get("target_agent_id")
            if event_type and event_type != "no_adversarial_event":
                event_desc = f"{event_type.upper()} at {event_location}"
                if event_type == "station_breakdown":
                    status = specific_effects.get("status")
                    if status == "warning":
                        event_desc = f"STATION WARNING at {event_location}"
                    elif status == "failed":
                        event_desc = f"STATION BREAKDOWN at {event_location}"
                elif isinstance(target_agent_id, int):
                    event_desc = f"{event_type.upper()} on AGENT {target_agent_id}"
                self._show_event(event_desc)
                if event_type == "station_breakdown":
                    self._add_event_task(event_type, event_location)
            
            # Check for game over (only after a turn, so player sees why)
            if self.game.is_game_over():
                state = self.game.get_state()
                living = [a for a in state.agents if a.get("status") != "dead"]
                if not living and state.agents:
                    self.last_game_over_reason = "All agents have died. There is no one left to respond to disasters."
                else:
                    self.last_game_over_reason = "The colony can no longer continue operating."
                # Switch to a dedicated Game Over screen instead of jumping straight to menu
                self.game_state = STATE_GAME_OVER
    
    def _draw_menu(self):
        """Draw the main menu screen. Returns list of button rects for click detection."""
        self.screen.fill(COLOR_MENU_BG)
        
        # Title
        title = self.font_large.render("The Colony Manager", True, COLOR_TEXT)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)
        
        subtitle = self.font.render("AI-Adversarial Survival System", True, (150, 150, 150))
        subtitle_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 200))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Menu options
        menu_options = ["New Game", "Options", "Quit"]
        y_start = 300
        self.menu_button_rects = []
        
        for i, option in enumerate(menu_options):
            y = y_start + i * 60
            color = COLOR_BUTTON_SELECTED if i == self.menu_selection else COLOR_BUTTON
            
            # Button background
            button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 150, y - 10, 300, 50)
            self.menu_button_rects.append(button_rect)
            pygame.draw.rect(self.screen, color, button_rect)
            pygame.draw.rect(self.screen, COLOR_TEXT, button_rect, 2)
            
            # Button text
            text = self.font.render(option, True, COLOR_TEXT)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, y + 15))
            self.screen.blit(text, text_rect)
    
    def _draw_options(self):
        """Draw the options menu."""
        self.screen.fill(COLOR_MENU_BG)
        
        # Title
        title = self.font_large.render("Options", True, COLOR_TEXT)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        self.screen.blit(title, title_rect)
        
        # Options
        options_list = [
            f"Difficulty: {self.difficulty.capitalize()}",
            f"Fullscreen: {'On' if self.fullscreen else 'Off'}",
            "Advanced",
            "Controls",
            "Back"
        ]
        y_start = 250
        self.options_button_rects = []
        
        for i, option_text in enumerate(options_list):
            y = y_start + i * 60
            color = COLOR_BUTTON_SELECTED if i == self.options_selection else COLOR_BUTTON
            
            button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 200, y - 10, 400, 50)
            self.options_button_rects.append(button_rect)
            pygame.draw.rect(self.screen, color, button_rect)
            pygame.draw.rect(self.screen, COLOR_TEXT, button_rect, 2)
            
            text = self.font.render(option_text, True, COLOR_TEXT)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, y + 15))
            self.screen.blit(text, text_rect)
    
    def _draw_advanced(self):
        """Draw the advanced options menu."""
        self.screen.fill(COLOR_MENU_BG)
        
        # Title
        title = self.font_large.render("Advanced Options", True, COLOR_TEXT)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 80))
        self.screen.blit(title, title_rect)
        
        # Subtitle: click left/right or use keys
        hint = self.font_small.render("Click left side (−) or right side (+) to adjust  •  Arrow keys / +/- work too", True, (180, 180, 200))
        hint_rect = hint.get_rect(center=(WINDOW_WIDTH // 2, 115))
        self.screen.blit(hint, hint_rect)
        
        # Algorithm selection
        algo_text = f"Algorithm: {self.algorithm.upper()}"
        algo_options = ["A*", "IDA*", "Beam Search"]
        
        # Turn speed
        speed_text = f"Turn Speed: {self.turn_interval:.1f}s"
        
        # Decay rate
        decay_text = f"Decay Rate: {self.decay_multiplier:.2f}x"
        ai_aggression_text = f"AI Aggression: {self.ai_aggression:.2f}x"
        ai_randomness_text = f"AI Randomness: {self.ai_randomness:.2f}"
        ai_cooldown_text = f"AI Repeat Cooldown: {self.ai_repeat_cooldown} turns"
        map_size_name, map_size_tiles = MAP_SIZE_PRESETS[self.map_size_index]
        map_size_text = f"Map Size: {map_size_name} ({map_size_tiles}x{map_size_tiles})"
        
        options_list = [
            algo_text,
            speed_text,
            decay_text,
            ai_aggression_text,
            ai_randomness_text,
            ai_cooldown_text,
            map_size_text,
            "Back"
        ]
        # Rows that use left/right click to adjust (show split)
        slider_rows = {1, 2, 3, 4, 5, 6}
        
        y_start = 200
        self.advanced_button_rects = []
        
        for i, option_text in enumerate(options_list):
            y = y_start + i * 56
            color = COLOR_BUTTON_SELECTED if i == self.advanced_selection else COLOR_BUTTON
            
            button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 200, y - 8, 400, 48)
            self.advanced_button_rects.append(button_rect)
            
            pygame.draw.rect(self.screen, color, button_rect)
            pygame.draw.rect(self.screen, COLOR_TEXT, button_rect, 2)
            
            # For Turn Speed and Decay Rate: show − and + so user sees left=decrease, right=increase
            if i in slider_rows:
                mid_x = button_rect.centerx
                pygame.draw.line(self.screen, (100, 100, 120), (mid_x, button_rect.top + 4), (mid_x, button_rect.bottom - 4), 2)
                # Minus on left half (use Unicode minus for clarity)
                minus_surf = self.font.render("−", True, (200, 200, 220))
                minus_rect = minus_surf.get_rect(center=(button_rect.left + 40, button_rect.centery))
                self.screen.blit(minus_surf, minus_rect)
                # Plus on right half
                plus_surf = self.font.render("+", True, (200, 200, 220))
                plus_rect = plus_surf.get_rect(center=(button_rect.right - 40, button_rect.centery))
                self.screen.blit(plus_surf, plus_rect)
            
            # Main label (centered)
            text = self.font.render(option_text, True, COLOR_TEXT)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, y + 18))
            self.screen.blit(text, text_rect)
        
        # Show algorithm options when selected (position below buttons to avoid overlap)
        if self.advanced_selection == 0:
            algo_y = y_start + len(options_list) * 56 + 20  # After all buttons with spacing
            for i, algo in enumerate(algo_options):
                x = WINDOW_WIDTH // 2 - 100 + i * 70
                algo_color = COLOR_BUTTON_SELECTED if algo.lower().replace("*", "star").replace(" ", "_") == self.algorithm else COLOR_BUTTON
                algo_rect = pygame.Rect(x - 30, algo_y - 10, 60, 30)
                pygame.draw.rect(self.screen, algo_color, algo_rect)
                pygame.draw.rect(self.screen, COLOR_TEXT, algo_rect, 1)
                algo_text_small = self.font_small.render(algo, True, COLOR_TEXT)
                algo_text_rect = algo_text_small.get_rect(center=(x, algo_y + 5))
                self.screen.blit(algo_text_small, algo_text_rect)
        
        # Show turn speed adjustment when selected
        if self.advanced_selection == 1:
            speed_y = y_start + len(options_list) * 56 + 20  # After all buttons with spacing
            speed_text = self.font_small.render("- = harder (faster)  + = easier (slower)  Min: 1s", True, COLOR_TEXT)
            speed_text_rect = speed_text.get_rect(center=(WINDOW_WIDTH // 2, speed_y))
            self.screen.blit(speed_text, speed_text_rect)
        
        # Show decay rate adjustment when selected
        if self.advanced_selection == 2:
            decay_y = y_start + len(options_list) * 56 + 20  # After all buttons with spacing
            decay_text = self.font_small.render("- = faster decay (harder)  + = slower decay (easier)  Range: 0.1x-3.0x", True, COLOR_TEXT)
            decay_text_rect = decay_text.get_rect(center=(WINDOW_WIDTH // 2, decay_y))
            self.screen.blit(decay_text, decay_text_rect)

        if self.advanced_selection == 3:
            y = y_start + len(options_list) * 56 + 20
            txt = self.font_small.render("- = less punishing AI  + = more punishing AI  Range: 0.5x-2.0x", True, COLOR_TEXT)
            self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH // 2, y)))

        if self.advanced_selection == 4:
            y = y_start + len(options_list) * 56 + 20
            txt = self.font_small.render("- = more deterministic AI  + = more variety  Range: 0.0-1.0", True, COLOR_TEXT)
            self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH // 2, y)))

        if self.advanced_selection == 5:
            y = y_start + len(options_list) * 56 + 20
            txt = self.font_small.render("- = less cooldown  + = more cooldown  Range: 1-6 turns", True, COLOR_TEXT)
            self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH // 2, y)))
        if self.advanced_selection == 6:
            y = y_start + len(options_list) * 56 + 20
            txt = self.font_small.render("- / + = Small / Medium / Large map", True, COLOR_TEXT)
            self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH // 2, y)))
    
    def _draw_controls(self):
        """Draw controls help screen."""
        self.screen.fill(COLOR_MENU_BG)
        title = self.font_large.render("Controls", True, COLOR_TEXT)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 80))
        self.screen.blit(title, title_rect)
        
        controls = [
            "Movement:",
            "  Click agent to select",
            "  Drag from agent to assign destination",
            "  Right-click tile/station to assign task",
            "",
            "Camera:",
            "  WASD - Move camera",
            "  +/- or Mouse Wheel - Zoom in/out",
            "  F11 - Toggle fullscreen",
            "",
            "Gameplay:",
            "  Recruit Agent - Click button (costs 30 each)",
            "  Stations restore resources (O/C/R icons)",
            "  Powerups (O/Cal/Int/S): one at start, more over time; S = permanent move speed",
            "  auto-walk (agent goes to station if that resource < 20%)",
            "  Agents die if any resource reaches 0",
            "  Sidebar: Colony | Agents | Tasks tabs",
            "  Mouse wheel in Agents tab - Scroll agent list",
            "",
            "Menu:",
            "  ESC - Return to menu",
        ]
        
        y_start = 150
        for i, line in enumerate(controls):
            y = y_start + i * 22
            color = COLOR_TEXT if line and not line.startswith(" ") else (180, 180, 180)
            text = self.font_small.render(line, True, color)
            self.screen.blit(text, (WINDOW_WIDTH // 2 - 200, y))
        
        # Back button
        back_rect = pygame.Rect(WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 80, 200, 50)
        pygame.draw.rect(self.screen, COLOR_BUTTON, back_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT, back_rect, 2)
        back_text = self.font.render("Back", True, COLOR_TEXT)
        self.screen.blit(back_text, back_text.get_rect(center=back_rect.center))
        self.controls_back_rect = back_rect
    
    def _handle_controls_input(self):
        """Handle input in controls state."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if hasattr(self, 'controls_back_rect') and self.controls_back_rect.collidepoint(mouse_pos):
                    self.game_state = STATE_OPTIONS
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
                    self.game_state = STATE_OPTIONS
        return True
    
    def _draw_resource_stations(self):
        """Draw resource stations on the map. Always visible regardless of zoom."""
        ts = int(self._get_scaled_tile_size())
        for station in self.resource_stations:
            tiles = station.get_tiles()
            if not tiles:
                continue
            station_state = self._get_station_state(station)
            station_status = station_state.get("status", "operational")
            is_warning = station_status == "warning"
            is_failed = station_status == "failed"
            center_screen_x, center_screen_y = self._world_to_screen(station.center_x, station.center_y)

            # Prefer textured buildings if available
            img = None
            if station.station_type == STATION_OXYGEN and self.img_station_oxygen:
                img = self.img_station_oxygen
            elif station.station_type == STATION_CALORIES and self.img_station_calories:
                img = self.img_station_calories
            elif station.station_type == STATION_INTEGRITY and self.img_station_integrity:
                img = self.img_station_integrity

            if img is not None:
                margin = ts * 2  # Ensure visible when near screen
                if -margin <= center_screen_x <= self.camera_width + margin and -margin <= center_screen_y <= self.camera_height + margin:
                    # Scale building so its longest side ≈ STATION_SPRITE_VS_COLONIST × colonist sprite
                    colonist_px = self._colonist_map_sprite_px()
                    target = max(24, int(colonist_px * STATION_SPRITE_VS_COLONIST))
                    iw, ih = img.get_width(), img.get_height()
                    longest = max(iw, ih)
                    scale = target / float(longest)
                    new_w = max(1, int(round(iw * scale)))
                    new_h = max(1, int(round(ih * scale)))
                    scaled = pygame.transform.smoothscale(img, (new_w, new_h))
                    rect = scaled.get_rect(center=(center_screen_x, center_screen_y))
                    self.screen.blit(scaled, rect)
                    if is_failed:
                        # Failed stations are visibly darkened and marked.
                        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                        overlay.fill((0, 0, 0, 130))
                        self.screen.blit(overlay, rect.topleft)
                        pygame.draw.line(
                            self.screen,
                            (255, 80, 80),
                            rect.topleft,
                            rect.bottomright,
                            max(2, ts // 10),
                        )
                        pygame.draw.line(
                            self.screen,
                            (255, 80, 80),
                            rect.topright,
                            rect.bottomleft,
                            max(2, ts // 10),
                        )
                    elif is_warning:
                        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                        overlay.fill((255, 220, 70, 90))
                        self.screen.blit(overlay, rect.topleft)
                        pygame.draw.rect(self.screen, (255, 220, 80), rect, max(2, ts // 10))
            else:
                # Fallback: one square at station center, same visual weight as textured art (~3× colonist)
                if station.station_type == STATION_OXYGEN:
                    color = COLOR_STATION_OXYGEN
                elif station.station_type == STATION_CALORIES:
                    color = COLOR_STATION_CALORIES
                else:
                    color = COLOR_STATION_INTEGRITY
                margin = ts * 2
                if -margin <= center_screen_x <= self.camera_width + margin and -margin <= center_screen_y <= self.camera_height + margin:
                    colonist_px = self._colonist_map_sprite_px()
                    box = max(24, int(colonist_px * STATION_SPRITE_VS_COLONIST))
                    rect = pygame.Rect(
                        center_screen_x - box // 2,
                        center_screen_y - box // 2,
                        box,
                        box,
                    )
                    pygame.draw.rect(self.screen, color, rect)
                    pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)
                    if is_failed:
                        pygame.draw.line(self.screen, (255, 80, 80), rect.topleft, rect.bottomright, max(2, box // 16))
                        pygame.draw.line(self.screen, (255, 80, 80), rect.topright, rect.bottomleft, max(2, box // 16))
                    elif is_warning:
                        pygame.draw.rect(self.screen, (255, 220, 80), rect, max(2, box // 16))

            # Warning indicator for stations about to fail.
            if is_warning and -ts <= center_screen_x <= self.camera_width + ts and -ts <= center_screen_y <= self.camera_height + ts:
                warn = self.font_small.render("BREAKDOWN WARNING", True, (255, 230, 120))
                w1 = warn.get_rect(center=(center_screen_x, center_screen_y - max(20, ts)))
                bg = pygame.Rect(
                    center_screen_x - w1.width // 2 - 6,
                    w1.top - 3,
                    w1.width + 12,
                    w1.height + 8,
                )
                pygame.draw.rect(self.screen, (40, 32, 8), bg)
                pygame.draw.rect(self.screen, (140, 110, 30), bg, 1)
                self.screen.blit(warn, w1)

            # Repair status indicator for failed stations (active vs paused + continuous progress)
            if is_failed and -ts <= center_screen_x <= self.camera_width + ts and -ts <= center_screen_y <= self.camera_height + ts:
                remaining = int(station_state.get("repair_remaining_turns", 0))
                total = int(station_state.get("repair_total_turns", 5))
                total = max(1, total)
                agents_on_station = self._count_living_agents_on_station(station)
                active = agents_on_station > 0
                indicator = "REPAIRING" if active else "REPAIR PAUSED"
                line1_color = (255, 220, 120) if active else (255, 120, 120)
                line1 = self.font_small.render(indicator, True, line1_color)
                line1_rect = line1.get_rect(center=(center_screen_x, center_screen_y - max(24, ts)))
                bar_w = max(80, ts * 3)
                bar_h = max(8, ts // 4)
                bar_rect = pygame.Rect(center_screen_x - bar_w // 2, line1_rect.bottom + 2, bar_w, bar_h)

                # Continuous progress preview between turns based on elapsed turn fraction.
                progress_complete = total - max(0, remaining)
                if active and self.turn_timer > 0:
                    now = pygame.time.get_ticks()
                    turn_frac = max(0.0, min(1.0, (now - self.last_turn_time) / float(self.turn_timer)))
                    effective_agents = min(agents_on_station, VISUAL_REPAIR_AGENT_CAP)
                    progress_complete += effective_agents * turn_frac
                progress_ratio = max(0.0, min(1.0, progress_complete / float(total)))

                bg_w = max(line1_rect.width, bar_w) + 10
                bg_h = (bar_rect.bottom - line1_rect.top) + 6
                bg_rect = pygame.Rect(center_screen_x - bg_w // 2, line1_rect.top - 2, bg_w, bg_h)
                pygame.draw.rect(self.screen, (15, 15, 20), bg_rect)
                pygame.draw.rect(self.screen, (80, 80, 90), bg_rect, 1)
                self.screen.blit(line1, line1_rect)
                pygame.draw.rect(self.screen, (45, 45, 55), bar_rect)
                fill_w = int(bar_w * progress_ratio)
                if fill_w > 0:
                    fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_w, bar_h)
                    fill_color = (255, 200, 80) if active else (170, 95, 95)
                    pygame.draw.rect(self.screen, fill_color, fill_rect)
                pygame.draw.rect(self.screen, (210, 210, 220), bar_rect, 1)
    
    def _get_station_at(self, world_x: int, world_y: int) -> Optional[ResourceStation]:
        """Get station at world coordinates."""
        for station in self.resource_stations:
            tiles = station.get_tiles()
            if (world_x, world_y) in tiles:
                return station
        return None
    
    def _get_station_for_resource(self, resource_type: str) -> Optional[ResourceStation]:
        """Get the resource station that restores the given resource (oxygen, calories, integrity)."""
        for station in self.resource_stations:
            if station.get_resource_type() == resource_type:
                return station
        return None
    
    def _draw_powerups(self):
        """Draw powerup pickups on the map using textures when available."""
        ts = int(self._get_scaled_tile_size())
        for p in self.powerups:
            if not (WORLD_MIN_X <= p.x < WORLD_MAX_X and WORLD_MIN_Y <= p.y < WORLD_MAX_Y):
                continue
            screen_x, screen_y = self._world_to_screen(p.x, p.y)
            if -ts > screen_x or screen_x > self.camera_width + ts or -ts > screen_y or screen_y > self.camera_height + ts:
                continue

            img = None
            if p.powerup_type == POWERUP_AUTO_OXYGEN and self.img_powerup_o2:
                img = self.img_powerup_o2
            elif p.powerup_type == POWERUP_AUTO_CALORIES and self.img_powerup_cal:
                img = self.img_powerup_cal
            elif p.powerup_type == POWERUP_AUTO_INTEGRITY and self.img_powerup_int:
                img = self.img_powerup_int
            elif p.powerup_type == POWERUP_SPEED_BOOST and self.img_powerup_speed:
                img = self.img_powerup_speed

            if img is not None:
                size = max(20, int(ts * 1.05))
                scaled = pygame.transform.smoothscale(img, (size, size))
                rect = scaled.get_rect(center=(screen_x, screen_y))
                # Soft outer ring to improve visibility on busy terrain.
                ring_radius = max(10, size // 2 + 3)
                pygame.draw.circle(self.screen, (255, 245, 170), (screen_x, screen_y), ring_radius, 2)
                self.screen.blit(scaled, rect)
            else:
                # Fallback: colored circles with letters
                radius = max(8, int(ts * 0.42))
                if p.powerup_type == POWERUP_AUTO_OXYGEN:
                    color = COLOR_STATION_OXYGEN
                    icon = "O"
                elif p.powerup_type == POWERUP_AUTO_CALORIES:
                    color = COLOR_STATION_CALORIES
                    icon = "C"
                elif p.powerup_type == POWERUP_SPEED_BOOST:
                    color = (120, 220, 120)
                    icon = "S"
                else:
                    color = COLOR_STATION_INTEGRITY
                    icon = "R"
                pygame.draw.circle(self.screen, (255, 245, 170), (screen_x, screen_y), radius + 3, 2)
                pygame.draw.circle(self.screen, color, (screen_x, screen_y), radius)
                pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y), radius, 2)
                text = self.font_small.render(icon, True, (255, 255, 255))
                text_rect = text.get_rect(center=(screen_x, screen_y))
                self.screen.blit(text, text_rect)
    
    def _draw_setup(self):
        """Draw new game setup screen (starting agent count)."""
        self.screen.fill(COLOR_MENU_BG)
        title = self.font_large.render("New Game", True, COLOR_TEXT)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 120))
        self.screen.blit(title, title_rect)
        
        # Starting agents selector — label on its own line, number + arrows below with clear spacing
        label_text = self.font.render("Starting agents:", True, COLOR_TEXT)
        label_rect = label_text.get_rect(center=(WINDOW_WIDTH // 2, 195))
        self.screen.blit(label_text, label_rect)
        
        # Number in center, arrows on either side (well separated from label and number)
        number_text = self.font.render(str(self.starting_agents), True, COLOR_TEXT)
        number_rect = number_text.get_rect(center=(WINDOW_WIDTH // 2, 260))
        self.screen.blit(number_text, number_rect)
        
        # Left/Right arrows — below label, flanking the number with clear gap
        left_rect = pygame.Rect(WINDOW_WIDTH // 2 - 130, 235, 50, 50)
        right_rect = pygame.Rect(WINDOW_WIDTH // 2 + 80, 235, 50, 50)
        pygame.draw.rect(self.screen, COLOR_BUTTON, left_rect)
        pygame.draw.rect(self.screen, COLOR_BUTTON, right_rect)
        l_arrow = self.font.render("<", True, COLOR_TEXT)
        r_arrow = self.font.render(">", True, COLOR_TEXT)
        self.screen.blit(l_arrow, l_arrow.get_rect(center=left_rect.center))
        self.screen.blit(r_arrow, r_arrow.get_rect(center=right_rect.center))
        self.setup_left_rect = left_rect
        self.setup_right_rect = right_rect
        
        # Start Game button
        start_rect = pygame.Rect(WINDOW_WIDTH // 2 - 100, 320, 200, 50)
        pygame.draw.rect(self.screen, COLOR_BUTTON_SELECTED, start_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT, start_rect, 2)
        start_text = self.font.render("Start Game", True, COLOR_TEXT)
        self.screen.blit(start_text, start_text.get_rect(center=start_rect.center))
        self.setup_start_rect = start_rect
        
        # Back
        back_rect = pygame.Rect(WINDOW_WIDTH // 2 - 100, 400, 200, 40)
        pygame.draw.rect(self.screen, COLOR_BUTTON, back_rect)
        back_text = self.font.render("Back", True, COLOR_TEXT)
        self.screen.blit(back_text, back_text.get_rect(center=back_rect.center))
        self.setup_back_rect = back_rect
    
    def _handle_setup_input(self):
        """Handle input in setup state."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if hasattr(self, 'setup_left_rect') and self.setup_left_rect.collidepoint(mouse_pos):
                    self.starting_agents = max(1, self.starting_agents - 1)
                elif hasattr(self, 'setup_right_rect') and self.setup_right_rect.collidepoint(mouse_pos):
                    self.starting_agents = min(5, self.starting_agents + 1)
                elif hasattr(self, 'setup_start_rect') and self.setup_start_rect.collidepoint(mouse_pos):
                    self.game = self._create_initial_game()
                    self.game_state = STATE_PLAYING
                    self.last_turn_time = pygame.time.get_ticks()
                elif hasattr(self, 'setup_back_rect') and self.setup_back_rect.collidepoint(mouse_pos):
                    self.game_state = STATE_MENU
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.starting_agents = max(1, self.starting_agents - 1)
                elif event.key == pygame.K_RIGHT:
                    self.starting_agents = min(5, self.starting_agents + 1)
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    self.game = self._create_initial_game()
                    self.game_state = STATE_PLAYING
                    self.last_turn_time = pygame.time.get_ticks()
                elif event.key == pygame.K_ESCAPE:
                    self.game_state = STATE_MENU
        return True
    
    def _handle_menu_input(self):
        """Handle input in menu state."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if hasattr(self, 'menu_button_rects'):
                    for i, rect in enumerate(self.menu_button_rects):
                        if rect.collidepoint(mouse_pos):
                            if i == 0:  # New Game
                                self.game_state = STATE_SETUP
                            elif i == 1:  # Options
                                self.game_state = STATE_OPTIONS
                            elif i == 2:  # Quit
                                return False
                            break
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.menu_selection = (self.menu_selection - 1) % 3
                elif event.key == pygame.K_DOWN:
                    self.menu_selection = (self.menu_selection + 1) % 3
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.menu_selection == 0:  # New Game
                        self.game_state = STATE_SETUP
                    elif self.menu_selection == 1:  # Options
                        self.game_state = STATE_OPTIONS
                    elif self.menu_selection == 2:  # Quit
                        return False
                elif event.key == pygame.K_ESCAPE:
                    return False
        
        return True
    
    def _handle_options_input(self):
        """Handle input in options state."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if hasattr(self, 'options_button_rects'):
                    for i, rect in enumerate(self.options_button_rects):
                        if rect.collidepoint(mouse_pos):
                            if i == 0:  # Difficulty
                                difficulties = ["easy", "normal", "hard"]
                                self.difficulty_selection = (self.difficulty_selection + 1) % 3
                                self.difficulty = difficulties[self.difficulty_selection]
                                self._apply_difficulty_defaults()
                            elif i == 1:  # Fullscreen
                                self._toggle_fullscreen()
                            elif i == 2:  # Advanced
                                self.game_state = STATE_ADVANCED
                            elif i == 3:  # Controls
                                self.game_state = STATE_CONTROLS
                            elif i == 4:  # Back
                                self.game_state = STATE_MENU
                            break
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.options_selection = (self.options_selection - 1) % 5
                elif event.key == pygame.K_DOWN:
                    self.options_selection = (self.options_selection + 1) % 5
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.options_selection == 0:  # Difficulty
                        difficulties = ["easy", "normal", "hard"]
                        self.difficulty_selection = (self.difficulty_selection + 1) % 3
                        self.difficulty = difficulties[self.difficulty_selection]
                        self._apply_difficulty_defaults()
                    elif self.options_selection == 1:  # Fullscreen
                        self._toggle_fullscreen()
                    elif self.options_selection == 2:  # Advanced
                        self.game_state = STATE_ADVANCED
                    elif self.options_selection == 3:  # Controls
                        self.game_state = STATE_CONTROLS
                    elif self.options_selection == 4:  # Back
                        self.game_state = STATE_MENU
                elif event.key == pygame.K_ESCAPE:
                    self.game_state = STATE_MENU
        
        return True
    
    def _handle_advanced_input(self):
        """Handle input in advanced options state."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if hasattr(self, 'advanced_button_rects'):
                    for i, rect in enumerate(self.advanced_button_rects):
                        if rect.collidepoint(mouse_pos):
                            if i == 0:  # Algorithm - cycle on click
                                algorithms = ["astar", "idastar", "beam_search"]
                                self.algorithm_selection = (self.algorithm_selection + 1) % 3
                                self.algorithm = algorithms[self.algorithm_selection]
                            elif i == 1:  # Turn speed - click to cycle harder (LEFT half) or easier (RIGHT half)
                                mouse_x = mouse_pos[0]
                                if mouse_x < WINDOW_WIDTH // 2:
                                    # Left half: harder (lower interval, faster turns)
                                    self.turn_interval = max(1.0, self.turn_interval - 1.0)
                                else:
                                    # Right half: easier (higher interval, slower turns)
                                    self.turn_interval = min(15.0, self.turn_interval + 1.0)
                                self.turn_timer = self.turn_interval * 1000
                            elif i == 2:  # Decay rate - click to adjust
                                mouse_x = mouse_pos[0]
                                if mouse_x < WINDOW_WIDTH // 2:
                                    # Left half: faster decay (harder)
                                    self.decay_multiplier = max(0.1, self.decay_multiplier - 0.2)
                                else:
                                    # Right half: slower decay (easier)
                                    self.decay_multiplier = min(3.0, self.decay_multiplier + 0.2)
                            elif i == 3:  # AI Aggression
                                mouse_x = mouse_pos[0]
                                if mouse_x < WINDOW_WIDTH // 2:
                                    self.ai_aggression = max(0.5, self.ai_aggression - 0.1)
                                else:
                                    self.ai_aggression = min(2.0, self.ai_aggression + 0.1)
                                self._apply_ai_settings_to_engine()
                            elif i == 4:  # AI Randomness
                                mouse_x = mouse_pos[0]
                                if mouse_x < WINDOW_WIDTH // 2:
                                    self.ai_randomness = max(0.0, self.ai_randomness - 0.05)
                                else:
                                    self.ai_randomness = min(1.0, self.ai_randomness + 0.05)
                                self._apply_ai_settings_to_engine()
                            elif i == 5:  # AI Repeat Cooldown
                                mouse_x = mouse_pos[0]
                                if mouse_x < WINDOW_WIDTH // 2:
                                    self.ai_repeat_cooldown = max(1, self.ai_repeat_cooldown - 1)
                                else:
                                    self.ai_repeat_cooldown = min(6, self.ai_repeat_cooldown + 1)
                                self._apply_ai_settings_to_engine()
                            elif i == 6:  # Map size
                                mouse_x = mouse_pos[0]
                                if mouse_x < WINDOW_WIDTH // 2:
                                    self.map_size_index = max(0, self.map_size_index - 1)
                                else:
                                    self.map_size_index = min(len(MAP_SIZE_PRESETS) - 1, self.map_size_index + 1)
                                self._set_world_size(MAP_SIZE_PRESETS[self.map_size_index][1])
                            elif i == 7:  # Back
                                self.game_state = STATE_OPTIONS
                            break
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.advanced_selection = (self.advanced_selection - 1) % 8
                elif event.key == pygame.K_DOWN:
                    self.advanced_selection = (self.advanced_selection + 1) % 8
                elif event.key == pygame.K_LEFT:
                    if self.advanced_selection == 0:  # Algorithm
                        algorithms = ["astar", "idastar", "beam_search"]
                        self.algorithm_selection = (self.algorithm_selection - 1) % 3
                        self.algorithm = algorithms[self.algorithm_selection]
                    elif self.advanced_selection == 1:  # Turn speed - harder (faster turns)
                        self.turn_interval = max(1.0, self.turn_interval - 1.0)
                        self.turn_timer = self.turn_interval * 1000
                    elif self.advanced_selection == 2:  # Decay rate - faster decay (harder)
                        self.decay_multiplier = max(0.1, self.decay_multiplier - 0.2)
                    elif self.advanced_selection == 3:  # AI aggression
                        self.ai_aggression = max(0.5, self.ai_aggression - 0.1)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 4:  # AI randomness
                        self.ai_randomness = max(0.0, self.ai_randomness - 0.05)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 5:  # AI repeat cooldown
                        self.ai_repeat_cooldown = max(1, self.ai_repeat_cooldown - 1)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 6:  # Map size
                        self.map_size_index = max(0, self.map_size_index - 1)
                        self._set_world_size(MAP_SIZE_PRESETS[self.map_size_index][1])
                elif event.key == pygame.K_RIGHT:
                    if self.advanced_selection == 0:  # Algorithm
                        algorithms = ["astar", "idastar", "beam_search"]
                        self.algorithm_selection = (self.algorithm_selection + 1) % 3
                        self.algorithm = algorithms[self.algorithm_selection]
                    elif self.advanced_selection == 1:  # Turn speed - easier (slower turns)
                        self.turn_interval = min(15.0, self.turn_interval + 1.0)
                        self.turn_timer = self.turn_interval * 1000
                    elif self.advanced_selection == 2:  # Decay rate - slower decay (easier)
                        self.decay_multiplier = min(3.0, self.decay_multiplier + 0.2)
                    elif self.advanced_selection == 3:  # AI aggression
                        self.ai_aggression = min(2.0, self.ai_aggression + 0.1)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 4:  # AI randomness
                        self.ai_randomness = min(1.0, self.ai_randomness + 0.05)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 5:  # AI repeat cooldown
                        self.ai_repeat_cooldown = min(6, self.ai_repeat_cooldown + 1)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 6:  # Map size
                        self.map_size_index = min(len(MAP_SIZE_PRESETS) - 1, self.map_size_index + 1)
                        self._set_world_size(MAP_SIZE_PRESETS[self.map_size_index][1])
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.advanced_selection == 7:  # Back
                        self.game_state = STATE_OPTIONS
                elif event.key == pygame.K_ESCAPE:
                    self.game_state = STATE_OPTIONS
                elif event.key in (pygame.K_MINUS, pygame.K_EQUALS, pygame.K_PLUS):
                    if self.advanced_selection == 1:  # Turn speed adjustment
                        if event.key == pygame.K_MINUS:
                            self.turn_interval = max(1.0, self.turn_interval - 0.5)  # Harder
                        else:  # K_EQUALS or K_PLUS
                            self.turn_interval = min(15.0, self.turn_interval + 0.5)  # Easier
                        self.turn_timer = self.turn_interval * 1000
                    elif self.advanced_selection == 2:  # Decay rate adjustment
                        if event.key == pygame.K_MINUS:
                            self.decay_multiplier = max(0.1, self.decay_multiplier - 0.1)  # Faster decay
                        else:  # K_EQUALS or K_PLUS
                            self.decay_multiplier = min(3.0, self.decay_multiplier + 0.1)  # Slower decay
                    elif self.advanced_selection == 3:  # AI aggression adjustment
                        if event.key == pygame.K_MINUS:
                            self.ai_aggression = max(0.5, self.ai_aggression - 0.1)
                        else:
                            self.ai_aggression = min(2.0, self.ai_aggression + 0.1)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 4:  # AI randomness adjustment
                        if event.key == pygame.K_MINUS:
                            self.ai_randomness = max(0.0, self.ai_randomness - 0.05)
                        else:
                            self.ai_randomness = min(1.0, self.ai_randomness + 0.05)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 5:  # AI cooldown adjustment
                        if event.key == pygame.K_MINUS:
                            self.ai_repeat_cooldown = max(1, self.ai_repeat_cooldown - 1)
                        else:
                            self.ai_repeat_cooldown = min(6, self.ai_repeat_cooldown + 1)
                        self._apply_ai_settings_to_engine()
                    elif self.advanced_selection == 6:  # Map size adjustment
                        if event.key == pygame.K_MINUS:
                            self.map_size_index = max(0, self.map_size_index - 1)
                        else:
                            self.map_size_index = min(len(MAP_SIZE_PRESETS) - 1, self.map_size_index + 1)
                        self._set_world_size(MAP_SIZE_PRESETS[self.map_size_index][1])
        
        return True
    
    def _check_powerup_pickups(self):
        """If an agent is on a powerup tile, collect it and grant that agent the powerup."""
        if not self.game or not self.powerups:
            return
        state = self.game.get_state()
        to_remove = []
        for p in self.powerups:
            for idx, agent in enumerate(state.agents):
                if agent.get("status") == "dead":
                    continue
                loc = agent.get("location")
                if not loc or len(loc) != 2:
                    continue
                if (int(loc[0]), int(loc[1])) != (p.x, p.y):
                    continue
                agent_id = agent.get("id")
                if agent_id is None:
                    break
                to_remove.append(p)
                if p.powerup_type == POWERUP_SPEED_BOOST:
                    cur = float(agent.get("speed") or 1.0)
                    new_spd = min(2.25, cur * 1.5)
                    state.update_agent(idx, {"speed": new_spd}, validate=False)
                    a2 = state.agents[idx]
                    a2.pop("speed_boost_end_turn", None)
                    a2.pop("speed_boost_mult", None)
                    self._show_event(f"Speed powerup! Permanent move speed ×{new_spd:.2f}")
                else:
                    self.agent_powerups.setdefault(agent_id, set()).add(p.powerup_type)
                    powerup_name = {
                        POWERUP_AUTO_OXYGEN: "Auto Oxygen",
                        POWERUP_AUTO_CALORIES: "Auto Calories",
                        POWERUP_AUTO_INTEGRITY: "Auto Integrity",
                    }.get(p.powerup_type, "Auto-walk")
                    self._show_event(f"{powerup_name} powerup collected!")
                break
        self.powerups = [p for p in self.powerups if p not in to_remove]
    
    def _apply_auto_walk_powerups(self):
        """
        If an agent has auto-walk powerups and resources are below 20%, prioritize the LOWEST resource.
        Walk to that station first, then after restoring, walk to the next lowest.
        Prevents loops by only assigning one task at a time and tracking which resource we're targeting.
        """
        if not self.game:
            return
        state = self.game.get_state()
        
        # Safety check: clear auto-target if agent has no path (pathfinding might have failed)
        for agent_id in list(self.agent_auto_target.keys()):
            if agent_id not in self.agent_paths:
                self.agent_auto_target.pop(agent_id, None)
        
        for agent in state.agents:
            if agent.get("status") == "dead":
                continue
            agent_id = agent.get("id")
            if agent_id is None:
                continue
            
            powers = self.agent_powerups.get(agent_id) or set()
            if not powers:
                continue
            
            # Map powerup types to resource types and collect resources below threshold
            resource_map = {
                POWERUP_AUTO_OXYGEN: "oxygen",
                POWERUP_AUTO_CALORIES: "calories",
                POWERUP_AUTO_INTEGRITY: "integrity"
            }
            
            # Find all resources below 20% for which agent has powerups
            low_resources = []
            for powerup_type, resource_type in resource_map.items():
                if powerup_type not in powers:
                    continue
                value = agent.get(resource_type, 100.0)
                if value < AUTO_WALK_THRESHOLD:
                    low_resources.append((value, resource_type, powerup_type))
            
            if not low_resources:
                # All resources are above threshold - clear any auto-target if set
                self.agent_auto_target.pop(agent_id, None)
                continue
            
            # Sort by value (lowest first) - prioritize the most critical resource
            low_resources.sort(key=lambda x: x[0])
            lowest_value, lowest_resource_type, _ = low_resources[0]
            
            # Check if agent is already auto-walking to a station
            current_target = self.agent_auto_target.get(agent_id)
            
            # If already walking to a station, check if we need to switch to a lower priority resource
            if current_target:
                # Find the value of the resource we're currently targeting
                current_value = agent.get(current_target, 100.0)
                # If the lowest resource is lower than what we're targeting, switch
                if lowest_value < current_value:
                    # Switch to lower priority resource
                    station = self._get_station_for_resource(lowest_resource_type)
                    if station:
                        self.agent_paths.pop(agent_id, None)
                        self._assign_task_at(station.center_x, station.center_y, agent_id=agent_id)
                        # Only set auto-target if path was successfully assigned
                        if agent_id in self.agent_paths:
                            self.agent_auto_target[agent_id] = lowest_resource_type
                # Otherwise, continue walking to current target
            else:
                # Not currently auto-walking - assign task to lowest resource
                station = self._get_station_for_resource(lowest_resource_type)
                if station:
                    self.agent_paths.pop(agent_id, None)
                    self._assign_task_at(station.center_x, station.center_y, agent_id=agent_id)
                    # Only set auto-target if path was successfully assigned
                    if agent_id in self.agent_paths:
                        self.agent_auto_target[agent_id] = lowest_resource_type
    
    def _check_station_visits(self):
        """Check if agents are at stations and restore resources."""
        if not self.game:
            return
        
        state = self.game.get_state()
        for agent in state.agents:
            loc = agent.get("location")
            if not loc or not isinstance(loc, (tuple, list)) or len(loc) != 2:
                continue
            
            x, y = int(loc[0]), int(loc[1])
            station = self._get_station_at(x, y)
            
            if station:
                station_state = state.infrastructure.get(station.station_id, {})
                # Failed stations are unusable until repaired.
                if station_state.get("status") == "failed":
                    continue
                resource_type = station.get_resource_type()
                current_value = agent.get(resource_type, 100.0)
                if current_value < 100.0:
                    # Restore resource
                    new_value = min(100.0, current_value + station.restore_amount)
                    agent_id = agent.get("id")
                    if agent_id is not None:
                        self.game.state.update_agent(
                            state.agents.index(agent),
                            {resource_type: new_value},
                            validate=False
                        )
                        # Only clear auto-target if this is the resource we were targeting
                        if self.agent_auto_target.get(agent_id) == resource_type:
                            self.agent_auto_target.pop(agent_id, None)
                            # Immediately check if there are other low resources to walk to
                            # (will be handled by _apply_auto_walk_powerups next frame)
    
    def run(self):
        """Main game loop."""
        running = True
        
        while running:
            # Handle input based on game state
            if self.game_state == STATE_MENU:
                running = self._handle_menu_input()
            elif self.game_state == STATE_SETUP:
                running = self._handle_setup_input()
            elif self.game_state == STATE_OPTIONS:
                running = self._handle_options_input()
            elif self.game_state == STATE_ADVANCED:
                running = self._handle_advanced_input()
            elif self.game_state == STATE_CONTROLS:
                running = self._handle_controls_input()
            elif self.game_state == STATE_CONFIRM_QUIT:
                running = self._handle_confirm_quit_input()
            elif self.game_state == STATE_GAME_OVER:
                running = self._handle_game_over_input()
            else:  # STATE_PLAYING
                running = self._handle_input()
            
            # Update game - only when playing and not paused
            if self.game_state == STATE_PLAYING and self.game and not self.paused:
                # Smooth agent movement every frame (independent of turn timer)
                dt_ms = self.clock.get_time()
                self._update_smooth_agent_movement(dt_ms / 1000.0)
                # Turn progression (resource drain, etc.) on second-based timer
                self._update_game()
                self._check_station_visits()
                self._check_powerup_pickups()
                self._apply_auto_walk_powerups()
            
            # Clear screen
            self.screen.fill(COLOR_BACKGROUND)
            
            # Draw based on game state
            if self.game_state == STATE_MENU:
                self._draw_menu()
            elif self.game_state == STATE_SETUP:
                self._draw_setup()
            elif self.game_state == STATE_OPTIONS:
                self._draw_options()
            elif self.game_state == STATE_ADVANCED:
                self._draw_advanced()
            elif self.game_state == STATE_CONTROLS:
                self._draw_controls()
            elif self.game_state == STATE_CONFIRM_QUIT:
                # Draw paused gameplay in background + overlay
                if self.game:
                    self._draw_map()
                    self._draw_trees()
                    self._draw_graph_location_labels()
                    self._draw_resource_stations()
                    self._draw_powerups()
                    self._draw_task_destinations()
                    self._draw_agents()
                    self._draw_drag_preview()
                    self._draw_sidebar()
                    self._draw_event_notification()
                self._draw_confirm_quit_overlay()
            elif self.game_state == STATE_GAME_OVER:
                self._draw_game_over_screen()
            else:  # STATE_PLAYING
                if self.game:
                    # Update which agent is under the mouse (for hover highlight)
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    if mouse_x < self.camera_width:
                        self.hovered_agent_id = self._get_agent_id_at_screen(mouse_x, mouse_y)
                    elif mouse_x >= self.camera_width and self.sidebar_tab == "agents":
                        agents_list_top = SIDEBAR_AGENTS_LIST_TOP
                        agent_entry_height = SIDEBAR_AGENT_ROW_PX
                        agents_per_page = 5
                        state = self.game.get_state()
                        if agents_list_top <= mouse_y < agents_list_top + agents_per_page * agent_entry_height:
                            row = (mouse_y - agents_list_top) // agent_entry_height
                            visible = state.agents[self.agent_list_scroll:self.agent_list_scroll + agents_per_page]
                            if 0 <= row < len(visible):
                                self.hovered_agent_id = visible[row].get("id")
                            else:
                                self.hovered_agent_id = None
                        else:
                            self.hovered_agent_id = None
                    else:
                        self.hovered_agent_id = None
                    # Draw everything
                    self._draw_map()
                    self._draw_trees()
                    self._draw_graph_location_labels()
                    self._draw_resource_stations()
                    self._draw_powerups()
                    self._draw_task_destinations()
                    self._draw_agents()
                    self._draw_drag_preview()
                    self._draw_sidebar()
                    self._draw_event_notification()
            
            # Update display
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS
        
        pygame.quit()
        sys.exit()


def main():
    """Entry point for visual game."""
    game = VisualGame()
    game.run()


if __name__ == "__main__":
    main()
