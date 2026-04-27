Game graphics asset layout
==========================

All game images/sprites should live under this `assets/` folder.

Recommended structure:

- `assets/tiles/`
  - Terrain tiles: `tile_grass_01.png`, `tile_sand_01.png`, `tile_water_01.png`, `tile_rock_01.png`, `tile_dirt_01.png`, etc.
- `assets/agents/`
  - Agent sprites and animations: `agent_idle.png`, `agent_walk_1.png`, `agent_walk_2.png`, `agent_dead.png`, etc.
- `assets/stations/`
  - Resource station buildings: `station_oxygen_3x3.png`, `station_calories_2x2.png`, `station_integrity_3x3.png`, plus any variants.
- `assets/powerups/`
  - Powerup pickups: `powerup_auto_oxygen.png`, `powerup_auto_calories.png`, `powerup_auto_integrity.png`.
- `assets/ui/`
  - UI and screen art:
    - `menu_background.png`, `game_over_background.png`
    - Button sprites: `ui_button_primary_default.png`, `ui_button_primary_hover.png`, etc.
    - Resource icons: `icon_oxygen.png`, `icon_calories.png`, `icon_integrity.png`.

You can drop the generated PNGs into these folders using the suggested names (or similar).
`visual_game.py` can then load them with paths like:

- `assets/tiles/tile_grass_01.png`
- `assets/agents/agent_idle.png`
- `assets/stations/station_oxygen_3x3.png`
- `assets/powerups/powerup_auto_oxygen.png`
- `assets/ui/menu_background.png`

