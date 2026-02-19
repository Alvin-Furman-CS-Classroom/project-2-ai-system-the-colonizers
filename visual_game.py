"""
Visual Game Interface for The Colony Manager

Top-down tile-based game with automatic turn progression.
Player manages agents and tasks while resources degrade over time.
"""

import pygame
import sys
import math
import random
from typing import Dict, List, Tuple, Optional, Any
from src.game_engine import GameEngine
from src.module1_state.colony_state import ColonyState
from src.module2_search.task_planner import Task
from src.module1_state.procedural_tiles import clear_tile_cache

# Constants
TILE_SIZE = 32  # Size of each tile in pixels
CAMERA_WIDTH = 800  # Width of game view
CAMERA_HEIGHT = 600  # Height of game view
SIDEBAR_WIDTH = 300  # Width of sidebar
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

# Colors
COLOR_GRASS = (34, 139, 34)
COLOR_WATER = (0, 119, 190)
COLOR_ROCK = (105, 105, 105)
COLOR_SAND = (238, 203, 173)
COLOR_DIRT = (101, 67, 33)
COLOR_AGENT = (255, 215, 0)  # Gold
COLOR_AGENT_LOW_HEALTH = (255, 0, 0)  # Red
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

# Game States
STATE_MENU = "menu"
STATE_SETUP = "setup"  # New game: select starting agents
STATE_OPTIONS = "options"
STATE_ADVANCED = "advanced"
STATE_CONTROLS = "controls"  # Controls help screen
STATE_PLAYING = "playing"


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
        
        # Player task queue (for assigning tasks)
        self.pending_tasks: List[Task] = []
        self.selected_agent_id = None
        
        # Agent walking: path coords per agent (agent_id -> remaining steps to walk)
        self.agent_paths: Dict[int, List[Tuple[int, int]]] = {}
        # Smooth movement: interpolated (x, y) for agents in transit
        self.agent_visual_pos: Dict[int, Tuple[float, float]] = {}
        self.agent_move_speed = 2.5  # Tiles per second
        
        # Click-and-drag: assign destination by dragging from agent
        self.drag_agent_id: Optional[int] = None
        self.drag_start_screen: Optional[Tuple[int, int]] = None
        
        # Resource stations
        self.resource_stations: List[ResourceStation] = []
        
        # Menu navigation
        self.menu_selection = 0  # 0 = New Game, 1 = Options, 2 = Quit
        self.options_selection = 0  # 0 = Difficulty, 1 = Advanced, 2 = Controls, 3 = Back
        self.advanced_selection = 0  # 0 = Algorithm, 1 = Turn Speed, 2 = Decay Rate, 3 = Back
        self.difficulty_selection = 1  # 0 = Easy, 1 = Normal, 2 = Hard
        self.algorithm_selection = 0  # 0 = A*, 1 = IDA*, 2 = Beam Search
        self.starting_agents = 2  # 1-5, selected at new game setup
        
        # Decay rate multipliers (1.0 = default, higher = faster decay)
        self.decay_multiplier = 1.0  # Multiplier for decay rates
        
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
    
    def _create_initial_game(self) -> GameEngine:
        """Create initial game state with agents and resource stations."""
        # Clear tile cache to ensure fresh map generation
        clear_tile_cache()
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
        
        # Create resource stations
        self.resource_stations = [
            ResourceStation("oxy_station_1", STATION_OXYGEN, -10, -10, size=2),
            ResourceStation("cal_station_1", STATION_CALORIES, 10, -10, size=2),
            ResourceStation("int_station_1", STATION_INTEGRITY, 0, 10, size=3),
        ]
        
        # Adjust difficulty based on settings (slower game)
        if self.difficulty == "easy":
            self.turn_interval = 15.0  # Was 10.0
        elif self.difficulty == "hard":
            self.turn_interval = 8.0  # Was 5.0
        else:
            self.turn_interval = 12.0  # Was 8.0
        
        self.turn_timer = self.turn_interval * 1000
        self.last_decay_time = pygame.time.get_ticks()  # Initialize decay timer
        
        self.agent_paths.clear()
        self.agent_visual_pos.clear()
        return GameEngine(initial_state)
    
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
    
    def _world_to_screen(self, world_x: int, world_y: int) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        ts = self._get_scaled_tile_size()
        screen_x = (world_x - self.camera_x) * ts + self.camera_width // 2
        screen_y = (world_y - self.camera_y) * ts + self.camera_height // 2
        return int(screen_x), int(screen_y)
    
    def _screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """Convert screen coordinates to world coordinates."""
        ts = self._get_scaled_tile_size()
        world_x = (screen_x - self.camera_width // 2) / ts + self.camera_x
        world_y = (screen_y - self.camera_height // 2) / ts + self.camera_y
        return int(world_x), int(world_y)
    
    def _draw_tile(self, x: int, y: int, terrain: str):
        """Draw a single tile at world coordinates."""
        screen_x, screen_y = self._world_to_screen(x, y)
        ts = int(self._get_scaled_tile_size())
        
        # Only draw if tile is visible
        if -ts <= screen_x <= self.camera_width + ts and -ts <= screen_y <= self.camera_height + ts:
            color = self._get_tile_color(terrain)
            rect = pygame.Rect(screen_x - ts // 2, screen_y - ts // 2, ts, ts)
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
            
            # Grey out dead agents
            if status == "dead":
                color = (100, 100, 100)  # Grey for dead agents
                border_color = (60, 60, 60)  # Darker grey border
                text_color = (150, 150, 150)  # Grey text
            else:
                # Determine color based on health for living agents
                oxygen = agent.get("oxygen", 100.0)
                integrity = agent.get("integrity", 100.0)
                avg_health = (oxygen + integrity) / 2.0
                
                if avg_health < 30:
                    color = COLOR_AGENT_LOW_HEALTH
                else:
                    color = COLOR_AGENT
                border_color = (0, 0, 0)  # Black border for living agents
                text_color = COLOR_TEXT
            
            # Draw agent circle (scale with zoom)
            radius = max(4, int(self._get_scaled_tile_size() // 3))
            pygame.draw.circle(self.screen, color, (screen_x, screen_y), radius)
            pygame.draw.circle(self.screen, border_color, (screen_x, screen_y), radius, 2)
            
            # Draw agent ID/name
            agent_id = agent.get("id", "?")
            text = self.font_small.render(str(agent_id), True, text_color)
            text_rect = text.get_rect(center=(screen_x, screen_y))
            self.screen.blit(text, text_rect)
            
            # Highlight selected agent (only if alive)
            if self.selected_agent_id == agent.get("id") and status != "dead":
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
    
    def _draw_sidebar(self):
        """Draw the sidebar with agent status, resources, and tasks."""
        sidebar_x = self.camera_width
        
        # Background
        sidebar_rect = pygame.Rect(sidebar_x, 0, self.sidebar_width, self.window_height)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR_BG, sidebar_rect)
        
        y_offset = 20
        
        # Title
        title = self.font.render("Colony Status", True, COLOR_TEXT)
        self.screen.blit(title, (sidebar_x + 10, y_offset))
        y_offset += 40
        
        # Resources (average of all agents)
        state = self.game.get_state()
        agents = [a for a in state.agents if a.get("status") != "dead"]
        if agents:
            avg_oxygen = sum(a.get("oxygen", 0) for a in agents) / len(agents)
            avg_calories = sum(a.get("calories", 0) for a in agents) / len(agents)
            avg_integrity = sum(a.get("integrity", 0) for a in agents) / len(agents)
        else:
            avg_oxygen = avg_calories = avg_integrity = 0.0
        y_offset = self._draw_resource_bar(sidebar_x + 10, y_offset, "Oxygen", avg_oxygen, COLOR_RESOURCE_OXYGEN)
        y_offset = self._draw_resource_bar(sidebar_x + 10, y_offset, "Calories", avg_calories, COLOR_RESOURCE_CALORIES)
        y_offset = self._draw_resource_bar(sidebar_x + 10, y_offset, "Integrity", avg_integrity, COLOR_RESOURCE_INTEGRITY)
        y_offset += 20
        
        # Turn number
        turn_text = self.font.render(f"Turn: {state.turn_number}", True, COLOR_TEXT)
        self.screen.blit(turn_text, (sidebar_x + 10, y_offset))
        y_offset += 40
        
        # Agents list with scrolling
        agents_title = self.font.render(f"Agents ({len(state.agents)}):", True, COLOR_TEXT)
        self.screen.blit(agents_title, (sidebar_x + 10, y_offset))
        y_offset += 30
        
        # Calculate visible agents (with scrolling)
        agents_per_page = 4  # Number of agents visible at once
        total_agents = len(state.agents)
        max_scroll = max(0, total_agents - agents_per_page)
        self.agent_list_scroll = max(0, min(self.agent_list_scroll, max_scroll))
        
        # Scroll buttons
        if total_agents > agents_per_page:
            scroll_up_rect = pygame.Rect(sidebar_x + self.sidebar_width - 30, y_offset, 25, 20)
            scroll_down_rect = pygame.Rect(sidebar_x + self.sidebar_width - 30, y_offset + agents_per_page * 85, 25, 20)
            self.agent_scroll_up_rect = scroll_up_rect
            self.agent_scroll_down_rect = scroll_down_rect
            
            # Draw scroll buttons
            up_color = COLOR_BUTTON if self.agent_list_scroll > 0 else (50, 50, 50)
            down_color = COLOR_BUTTON if self.agent_list_scroll < max_scroll else (50, 50, 50)
            pygame.draw.rect(self.screen, up_color, scroll_up_rect)
            pygame.draw.rect(self.screen, down_color, scroll_down_rect)
            pygame.draw.polygon(self.screen, COLOR_TEXT, [
                (scroll_up_rect.centerx, scroll_up_rect.top + 5),
                (scroll_up_rect.left + 5, scroll_up_rect.bottom - 5),
                (scroll_up_rect.right - 5, scroll_up_rect.bottom - 5)
            ])
            pygame.draw.polygon(self.screen, COLOR_TEXT, [
                (scroll_down_rect.centerx, scroll_down_rect.bottom - 5),
                (scroll_down_rect.left + 5, scroll_down_rect.top + 5),
                (scroll_down_rect.right - 5, scroll_down_rect.top + 5)
            ])
        
        # Display visible agents
        visible_agents = state.agents[self.agent_list_scroll:self.agent_list_scroll + agents_per_page]
        for agent in visible_agents:
            agent_entry_start_y = y_offset  # Track where this agent entry starts
            agent_id = agent.get("id", "?")
            name = agent.get("name", "Unknown")
            oxygen = agent.get("oxygen", 0)
            calories = agent.get("calories", 0)
            integrity = agent.get("integrity", 0)
            status = agent.get("status", "active")
            loc = agent.get("location", (0, 0))
            
            # Highlight selected agent with background
            is_selected = (self.selected_agent_id == agent_id and status != "dead")
            if is_selected:
                # Draw highlight background for selected agent (entire entry)
                highlight_rect = pygame.Rect(sidebar_x + 5, agent_entry_start_y - 5, self.sidebar_width - 10, 85)
                pygame.draw.rect(self.screen, (60, 80, 100), highlight_rect)  # Dark blue highlight
                pygame.draw.rect(self.screen, (255, 255, 0), highlight_rect, 2)  # Yellow border
            
            # Agent info line (grayed out if dead, brighter if selected)
            agent_text = f"{agent_id}: {name} ({status})"
            if status == "dead":
                text_color = (150, 150, 150)
            elif is_selected:
                text_color = (255, 255, 200)  # Bright yellow-white for selected
            else:
                text_color = COLOR_TEXT
            text_surface = self.font_small.render(agent_text, True, text_color)
            self.screen.blit(text_surface, (sidebar_x + 10, y_offset))
            y_offset += 20
            
            # Health bars (grayed out if dead)
            if status == "dead":
                # Draw grayed out bars for dead agents
                y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "O2", 0, (80, 80, 80))
                y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Cal", 0, (80, 80, 80))
                y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Int", 0, (80, 80, 80))
            else:
                y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "O2", oxygen, COLOR_RESOURCE_OXYGEN)
                y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Cal", calories, COLOR_RESOURCE_CALORIES)
                y_offset = self._draw_small_bar(sidebar_x + 20, y_offset, "Int", integrity, COLOR_RESOURCE_INTEGRITY)
            
            # Location
            loc_text = f"  Loc: {loc[0]}, {loc[1]}"
            loc_color = (255, 255, 200) if is_selected else COLOR_TEXT
            text_surface = self.font_small.render(loc_text, True, loc_color)
            self.screen.blit(text_surface, (sidebar_x + 10, y_offset))
            y_offset += 25
        
        y_offset += 10
        
        # Recruit Agent button (check average resources)
        RECRUIT_COST = (30, 30, 30)  # O2, Cal, Int
        can_recruit = (
            agents and avg_oxygen >= RECRUIT_COST[0]
            and avg_calories >= RECRUIT_COST[1]
            and avg_integrity >= RECRUIT_COST[2]
        )
        recruit_rect = pygame.Rect(sidebar_x + 10, y_offset, self.sidebar_width - 20, 36)
        self.recruit_button_rect = recruit_rect
        recruit_color = COLOR_BUTTON_SELECTED if can_recruit else (80, 60, 60)
        pygame.draw.rect(self.screen, recruit_color, recruit_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT, recruit_rect, 2)
        recruit_text = self.font_small.render("Recruit Agent (30 each)", True, COLOR_TEXT)
        self.screen.blit(recruit_text, recruit_text.get_rect(center=recruit_rect.center))
        y_offset += 50
        
        # Active tasks
        tasks_title = self.font.render("Active Tasks:", True, COLOR_TEXT)
        self.screen.blit(tasks_title, (sidebar_x + 10, y_offset))
        y_offset += 30
        
        for task in state.active_tasks:
            task_id = task.get("task_id", "?")
            agent_id = task.get("agent_id", None)
            progress = task.get("progress", 0.0)
            task_text = f"{task_id} (Agent {agent_id}, {progress*100:.0f}%)"
            text_surface = self.font_small.render(task_text, True, COLOR_TEXT)
            self.screen.blit(text_surface, (sidebar_x + 10, y_offset))
            y_offset += 20
        
    
    def _draw_resource_bar(self, x: int, y: int, label: str, value: float, color: Tuple[int, int, int]) -> int:
        """Draw a resource bar and return next y position."""
        label_text = self.font_small.render(label, True, COLOR_TEXT)
        self.screen.blit(label_text, (x, y))
        
        bar_width = self.sidebar_width - 40
        bar_height = 20
        bar_x = x
        bar_y = y + 20
        
        # Background
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLOR_RESOURCE_BAR_BG, bg_rect)
        
        # Fill
        fill_width = int(bar_width * max(0, min(100, value)) / 100)
        fill_rect = pygame.Rect(bar_x, bar_y, fill_width, bar_height)
        pygame.draw.rect(self.screen, color, fill_rect)
        
        # Border
        pygame.draw.rect(self.screen, (0, 0, 0), bg_rect, 2)
        
        # Value text
        value_text = self.font_small.render(f"{value:.1f}%", True, COLOR_TEXT)
        text_rect = value_text.get_rect(center=(bar_x + bar_width // 2, bar_y + bar_height // 2))
        self.screen.blit(value_text, text_rect)
        
        return bar_y + bar_height + 10
    
    def _draw_small_bar(self, x: int, y: int, label: str, value: float, color: Tuple[int, int, int]) -> int:
        """Draw a small resource bar and return next y position."""
        bar_width = SIDEBAR_WIDTH - 50
        bar_height = 12
        
        # Label
        label_text = self.font_small.render(f"{label}:", True, COLOR_TEXT)
        self.screen.blit(label_text, (x, y))
        
        # Bar
        bar_x = x + 30
        bar_y = y
        
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLOR_RESOURCE_BAR_BG, bg_rect)
        
        fill_width = int(bar_width * max(0, min(100, value)) / 100)
        fill_rect = pygame.Rect(bar_x, bar_y, fill_width, bar_height)
        pygame.draw.rect(self.screen, color, fill_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), bg_rect, 1)
        
        return bar_y + bar_height + 5
    
    def _draw_event_notification(self):
        """Draw event notification (red flashing text)."""
        if self.current_event_text and self.event_start_time:
            current_time = pygame.time.get_ticks()
            elapsed = current_time - self.event_start_time
            
            if elapsed < self.event_duration:
                # Flash effect (on/off every 200ms)
                visible = (elapsed // 200) % 2 == 0
                if visible:
                    # Draw large red text in center
                    text_surface = self.font_large.render(self.current_event_text, True, COLOR_EVENT_TEXT)
                    text_rect = text_surface.get_rect(center=(CAMERA_WIDTH // 2, CAMERA_HEIGHT // 2))
                    
                    # Add black outline for visibility
                    outline_surface = self.font_large.render(self.current_event_text, True, (0, 0, 0))
                    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]:
                        outline_rect = text_rect.copy()
                        outline_rect.x += dx
                        outline_rect.y += dy
                        self.screen.blit(outline_surface, outline_rect)
                    
                    self.screen.blit(text_surface, text_rect)
            else:
                # Clear event after duration
                self.current_event_text = None
                self.event_start_time = None
    
    def _show_event(self, event_description: str):
        """Show an event notification."""
        self.current_event_text = event_description
        self.event_start_time = pygame.time.get_ticks()
    
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
        
        # Mouse clicks and wheel
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                # Agent list scrolling (when mouse is over sidebar)
                if mouse_x >= self.camera_width and self.game:
                    state = self.game.get_state()
                    total_agents = len(state.agents)
                    if total_agents > 4:
                        if event.y > 0:
                            self.agent_list_scroll = max(0, self.agent_list_scroll - 1)
                        elif event.y < 0:
                            self.agent_list_scroll = min(max(0, total_agents - 4), self.agent_list_scroll + 1)
                else:
                    # Zoom controls (when mouse is over game area)
                    if event.y > 0:
                        self.zoom_level = min(self.zoom_max, self.zoom_level + 0.1)
                    elif event.y < 0:
                        self.zoom_level = max(self.zoom_min, self.zoom_level - 0.1)
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    # Toggle fullscreen
                    self.fullscreen = not self.fullscreen
                    if self.fullscreen:
                        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        # Update window dimensions
                        self.window_width, self.window_height = self.screen.get_size()
                        self.camera_width = int(self.window_width * 0.7)  # 70% for game area
                        self.sidebar_width = self.window_width - self.camera_width
                        self.camera_height = self.window_height
                    else:
                        self.screen = pygame.display.set_mode(self.original_size)
                        self.window_width, self.window_height = self.original_size
                        self.camera_width = CAMERA_WIDTH
                        self.camera_height = CAMERA_HEIGHT
                        self.sidebar_width = SIDEBAR_WIDTH
                elif event.key == pygame.K_ESCAPE:
                    # Return to menu
                    self.game_state = STATE_MENU
                    self.game = None
                    return True
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                mouse_pos = (mouse_x, mouse_y)
                
                # Sidebar interactions
                if mouse_x >= self.camera_width:
                    # Agent list scroll buttons
                    if hasattr(self, 'agent_scroll_up_rect') and self.agent_scroll_up_rect.collidepoint(mouse_pos):
                        self.agent_list_scroll = max(0, self.agent_list_scroll - 1)
                    elif hasattr(self, 'agent_scroll_down_rect') and self.agent_scroll_down_rect.collidepoint(mouse_pos):
                        self.agent_list_scroll = min(max(0, len(self.game.get_state().agents) - 4), self.agent_list_scroll + 1)
                    # Recruit Agent button
                    elif hasattr(self, 'recruit_button_rect') and self.recruit_button_rect.collidepoint(mouse_pos):
                        self._recruit_agent()
                
                # Check if click is in game area
                if mouse_x < self.camera_width:
                    world_x, world_y = self._screen_to_world(mouse_x, mouse_y)
                    
                    if event.button == 1:  # Left click - select or start drag
                        agent_here = self._get_agent_id_at(world_x, world_y)
                        if agent_here is not None:
                            self.drag_agent_id = agent_here
                            self.drag_start_screen = (mouse_x, mouse_y)
                            self.selected_agent_id = agent_here
                        else:
                            self._select_agent_at(world_x, world_y)
                    elif event.button == 3:  # Right click - assign task
                        if self.selected_agent_id is not None:
                            self._assign_task_at(world_x, world_y)
            
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.drag_agent_id is not None:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    if mouse_x < self.camera_width:
                        world_x, world_y = self._screen_to_world(mouse_x, mouse_y)
                        self._assign_task_at(world_x, world_y, agent_id=self.drag_agent_id)
                    self.drag_agent_id = None
                    self.drag_start_screen = None
        
        return True
    
    def _get_agent_id_at(self, world_x: int, world_y: int) -> Optional[int]:
        """Return agent id at world coordinates, or None. Uses visual pos when agent is walking. Skips dead agents."""
        if not self.game:
            return None
        state = self.game.get_state()
        for agent in state.agents:
            # Skip dead agents
            if agent.get("status") == "dead":
                continue
            agent_id = agent.get("id")
            if agent_id in self.agent_visual_pos:
                ax, ay = self.agent_visual_pos[agent_id]
            else:
                loc = agent.get("location")
                if not loc or not isinstance(loc, (tuple, list)) or len(loc) != 2:
                    continue
                ax, ay = float(loc[0]), float(loc[1])
            if abs(ax - world_x) <= 1.5 and abs(ay - world_y) <= 1.5:
                return agent_id
        return None
    
    def _select_agent_at(self, world_x: int, world_y: int):
        """Select agent at world coordinates. Skips dead agents."""
        state = self.game.get_state()
        self.selected_agent_id = None
        
        for agent in state.agents:
            # Skip dead agents
            if agent.get("status") == "dead":
                continue
            loc = agent.get("location")
            if loc and isinstance(loc, (tuple, list)) and len(loc) == 2:
                ax, ay = int(loc[0]), int(loc[1])
                # Check if click is near agent (within 1 tile)
                if abs(ax - world_x) <= 1 and abs(ay - world_y) <= 1:
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
        move_dist = self.agent_move_speed * dt_sec  # Distance to travel this frame
        
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
                    state.update_agent(agent_index, {"location": (int(round(vx)), int(round(vy)))}, validate=False)
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
            tile = state.get_tile_at(int(round(tx)), int(round(ty)))
            if not tile.get("passable", True):
                path.pop(0)
                if not path:
                    to_remove.append(agent_id)
                    self.agent_visual_pos.pop(agent_id, None)
                continue
            
            # Water slows movement (0.2x), other terrain normal speed
            tile_speed = tile.get("move_speed", 1.0)
            step_move_dist = move_dist * tile_speed
            
            # Calculate direction vector (normalized for smooth diagonal movement)
            dx, dy = tx - vx, ty - vy
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist <= 0.05:  # Very close, snap to target
                path.pop(0)
                vx, vy = tx, ty
                state.update_agent(agent_index, {"location": (int(round(tx)), int(round(ty)))}, validate=False)
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
                    state.update_agent(agent_index, {"location": (int(round(tx)), int(round(ty)))}, validate=False)
                    self.agent_visual_pos[agent_id] = (vx, vy)
                    if not path:
                        to_remove.append(agent_id)
                        self.agent_visual_pos.pop(agent_id, None)
        
        for aid in to_remove:
            self.agent_paths.pop(aid, None)
    
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
            
            # Check for deaths after turn (resources may have drained)
            self._check_agent_deaths()
            
            # Store paths from new assignments for walking
            planning = turn_report.get("phases", {}).get("planning", {})
            self._store_paths_from_assignments(planning.get("assignments", []))
            
            # Show event notification
            event_info = turn_report.get("phases", {}).get("adversarial", {})
            event_type = event_info.get("event_selected", "")
            event_location = event_info.get("location", "")
            if event_type:
                event_desc = f"{event_type.upper()} at {event_location}"
                self._show_event(event_desc)
            
            # Check for game over
            if self.game.is_game_over():
                self._show_event("GAME OVER - COLONY FAILED")
                # Return to menu after a delay
                pygame.time.wait(3000)
                self.game_state = STATE_MENU
                self.game = None
    
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
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        self.screen.blit(title, title_rect)
        
        # Algorithm selection
        algo_text = f"Algorithm: {self.algorithm.upper()}"
        algo_options = ["A*", "IDA*", "Beam Search"]
        
        # Turn speed
        speed_text = f"Turn Speed: {self.turn_interval:.1f}s"
        
        # Decay rate
        decay_text = f"Decay Rate: {self.decay_multiplier:.2f}x"
        
        options_list = [
            algo_text,
            speed_text,
            decay_text,
            "Back"
        ]
        y_start = 250
        self.advanced_button_rects = []
        
        for i, option_text in enumerate(options_list):
            y = y_start + i * 60
            color = COLOR_BUTTON_SELECTED if i == self.advanced_selection else COLOR_BUTTON
            
            button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 200, y - 10, 400, 50)
            self.advanced_button_rects.append(button_rect)
            
            pygame.draw.rect(self.screen, color, button_rect)
            pygame.draw.rect(self.screen, COLOR_TEXT, button_rect, 2)
            
            text = self.font.render(option_text, True, COLOR_TEXT)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, y + 15))
            self.screen.blit(text, text_rect)
        
        # Show algorithm options when selected (position below buttons to avoid overlap)
        if self.advanced_selection == 0:
            # Position algorithm options after all buttons (button 2 ends at y_start + 2*60 + 40 = 370)
            # Place options at 380+ to ensure no overlap
            algo_y = y_start + len(options_list) * 60 + 20  # After all buttons with spacing
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
            # Position speed controls after all buttons to avoid overlap
            speed_y = y_start + len(options_list) * 60 + 20  # After all buttons with spacing
            speed_text = self.font_small.render("- = harder (faster)  + = easier (slower)  Min: 1s", True, COLOR_TEXT)
            speed_text_rect = speed_text.get_rect(center=(WINDOW_WIDTH // 2, speed_y))
            self.screen.blit(speed_text, speed_text_rect)
        
        # Show decay rate adjustment when selected
        if self.advanced_selection == 2:
            # Position decay controls after all buttons to avoid overlap
            decay_y = y_start + len(options_list) * 60 + 20  # After all buttons with spacing
            decay_text = self.font_small.render("- = faster decay (harder)  + = slower decay (easier)  Range: 0.1x-3.0x", True, COLOR_TEXT)
            decay_text_rect = decay_text.get_rect(center=(WINDOW_WIDTH // 2, decay_y))
            self.screen.blit(decay_text, decay_text_rect)
    
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
            "  Agents die if any resource reaches 0",
            "  Mouse wheel on sidebar - Scroll agents",
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
            
            # Get station color based on type
            if station.station_type == STATION_OXYGEN:
                color = COLOR_STATION_OXYGEN
            elif station.station_type == STATION_CALORIES:
                color = COLOR_STATION_CALORIES
            else:
                color = COLOR_STATION_INTEGRITY
            
            # Draw station tiles (completely cover terrain underneath)
            for x, y in tiles:
                if WORLD_MIN_X <= x < WORLD_MAX_X and WORLD_MIN_Y <= y < WORLD_MAX_Y:
                    screen_x, screen_y = self._world_to_screen(x, y)
                    if -ts <= screen_x <= self.camera_width + ts and -ts <= screen_y <= self.camera_height + ts:
                        rect = pygame.Rect(screen_x - ts // 2, screen_y - ts // 2, ts, ts)
                        # Draw solid filled rectangle to completely cover terrain
                        pygame.draw.rect(self.screen, color, rect)
                        pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)
            
            # Draw station center marker (generous visibility check for zoom)
            center_screen_x, center_screen_y = self._world_to_screen(station.center_x, station.center_y)
            margin = ts * 2  # Ensure icon visible when station tiles are on screen
            if -margin <= center_screen_x <= self.camera_width + margin and -margin <= center_screen_y <= self.camera_height + margin:
                icon_text = "O" if station.station_type == STATION_OXYGEN else ("C" if station.station_type == STATION_CALORIES else "R")
                icon = self.font.render(icon_text, True, (255, 255, 255))
                icon_rect = icon.get_rect(center=(center_screen_x, center_screen_y))
                self.screen.blit(icon, icon_rect)
    
    def _get_station_at(self, world_x: int, world_y: int) -> Optional[ResourceStation]:
        """Get station at world coordinates."""
        for station in self.resource_stations:
            tiles = station.get_tiles()
            if (world_x, world_y) in tiles:
                return station
        return None
    
    def _draw_setup(self):
        """Draw new game setup screen (starting agent count)."""
        self.screen.fill(COLOR_MENU_BG)
        title = self.font_large.render("New Game", True, COLOR_TEXT)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 120))
        self.screen.blit(title, title_rect)
        
        # Starting agents selector
        agents_text = self.font.render(f"Starting Agents: {self.starting_agents}", True, COLOR_TEXT)
        agents_rect = agents_text.get_rect(center=(WINDOW_WIDTH // 2, 220))
        self.screen.blit(agents_text, agents_rect)
        
        # Left/Right arrows
        left_rect = pygame.Rect(WINDOW_WIDTH // 2 - 120, 200, 50, 50)
        right_rect = pygame.Rect(WINDOW_WIDTH // 2 + 70, 200, 50, 50)
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
                            elif i == 1:  # Advanced
                                self.game_state = STATE_ADVANCED
                            elif i == 2:  # Controls
                                self.game_state = STATE_CONTROLS
                            elif i == 3:  # Back
                                self.game_state = STATE_MENU
                            break
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.options_selection = (self.options_selection - 1) % 4
                elif event.key == pygame.K_DOWN:
                    self.options_selection = (self.options_selection + 1) % 4
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.options_selection == 0:  # Difficulty
                        difficulties = ["easy", "normal", "hard"]
                        self.difficulty_selection = (self.difficulty_selection + 1) % 3
                        self.difficulty = difficulties[self.difficulty_selection]
                    elif self.options_selection == 1:  # Advanced
                        self.game_state = STATE_ADVANCED
                    elif self.options_selection == 2:  # Controls
                        self.game_state = STATE_CONTROLS
                    elif self.options_selection == 3:  # Back
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
                            elif i == 3:  # Back
                                self.game_state = STATE_OPTIONS
                            break
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.advanced_selection = (self.advanced_selection - 1) % 4
                elif event.key == pygame.K_DOWN:
                    self.advanced_selection = (self.advanced_selection + 1) % 4
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
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.advanced_selection == 3:  # Back
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
        
        return True
    
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
            else:  # STATE_PLAYING
                running = self._handle_input()
            
            # Update game - only when playing
            if self.game_state == STATE_PLAYING and self.game:
                # Smooth agent movement every frame (independent of turn timer)
                dt_ms = self.clock.get_time()
                self._update_smooth_agent_movement(dt_ms / 1000.0)
                # Turn progression (resource drain, etc.) on second-based timer
                self._update_game()
                self._check_station_visits()
            
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
            else:  # STATE_PLAYING
                if self.game:
                    # Draw everything
                    self._draw_map()
                    self._draw_resource_stations()
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
