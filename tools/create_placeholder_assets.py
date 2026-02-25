import os

import pygame


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_placeholder(rel_path: str, size: tuple[int, int], color: tuple[int, int, int, int]) -> None:
    full_path = os.path.join(ASSETS_DIR, rel_path)
    ensure_dir(os.path.dirname(full_path))
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.image.save(surf, full_path)


def main() -> None:
    pygame.init()

    # Tiles (32x32)
    save_placeholder(r"tiles\tile_grass_01.png", (32, 32), (34, 139, 34, 255))   # grass green
    save_placeholder(r"tiles\tile_sand_01.png", (32, 32), (238, 214, 175, 255))  # sand
    save_placeholder(r"tiles\tile_water_01.png", (32, 32), (0, 119, 190, 255))   # water
    save_placeholder(r"tiles\tile_rock_01.png", (32, 32), (105, 105, 105, 255))  # rock
    save_placeholder(r"tiles\tile_dirt_01.png", (32, 32), (101, 67, 33, 255))    # dirt

    # Agents (32x32)
    save_placeholder(r"agents\agent_idle.png", (32, 32), (200, 200, 220, 255))
    save_placeholder(r"agents\agent_walk_1.png", (32, 32), (180, 200, 220, 255))
    save_placeholder(r"agents\agent_walk_2.png", (32, 32), (160, 190, 220, 255))
    save_placeholder(r"agents\agent_dead.png", (32, 32), (120, 120, 120, 255))

    # Stations (multi-tile footprints, rough sizes)
    save_placeholder(r"stations\station_oxygen_3x3.png", (96, 96), (0, 191, 255, 255))     # cyan
    save_placeholder(r"stations\station_calories_2x2.png", (64, 64), (255, 165, 0, 255))   # orange
    save_placeholder(r"stations\station_integrity_3x3.png", (96, 96), (255, 69, 0, 255))   # red-orange

    # Powerups (32x32)
    save_placeholder(r"powerups\powerup_auto_oxygen.png", (32, 32), (0, 191, 255, 255))
    save_placeholder(r"powerups\powerup_auto_calories.png", (32, 32), (255, 165, 0, 255))
    save_placeholder(r"powerups\powerup_auto_integrity.png", (32, 32), (255, 69, 0, 255))

    # UI backgrounds (match window size roughly: 1100x600)
    save_placeholder(r"ui\menu_background.png", (1100, 600), (20, 20, 35, 255))
    save_placeholder(r"ui\game_over_background.png", (1100, 600), (10, 10, 20, 255))

    # UI buttons (simple 160x48)
    save_placeholder(r"ui\ui_button_primary_default.png", (160, 48), (80, 120, 200, 255))
    save_placeholder(r"ui\ui_button_primary_hover.png", (160, 48), (100, 140, 220, 255))
    save_placeholder(r"ui\ui_button_secondary_default.png", (160, 48), (70, 70, 90, 255))
    save_placeholder(r"ui\ui_button_secondary_hover.png", (160, 48), (90, 90, 110, 255))

    # Resource icons (32x32)
    save_placeholder(r"ui\icon_oxygen.png", (32, 32), (0, 191, 255, 255))
    save_placeholder(r"ui\icon_calories.png", (32, 32), (255, 165, 0, 255))
    save_placeholder(r"ui\icon_integrity.png", (32, 32), (255, 69, 0, 255))

    print("Placeholder assets created under", ASSETS_DIR)


if __name__ == "__main__":
    main()

