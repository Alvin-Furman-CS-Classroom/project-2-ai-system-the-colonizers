#!/usr/bin/env python3
"""Render the same failed-station overlay as visual_game.py and save a PNG (headless-safe)."""

import os
import sys

# Allow running without a display window
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

# Match visual_game.py
STATION_SPRITE_VS_COLONIST = 3.0
COLONIST_PX = 32  # typical map sprite size; scales station like the client


def _failed_overlay(surface: pygame.Surface) -> None:
    w, h = surface.get_size()
    rect = surface.get_rect()
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 130))
    surface.blit(overlay, (0, 0))
    ts = max(8, w // 24)
    pygame.draw.line(surface, (255, 80, 80), rect.topleft, rect.bottomright, max(2, ts // 10))
    pygame.draw.line(surface, (255, 80, 80), rect.topright, rect.bottomleft, max(2, ts // 10))


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets = os.path.join(root, "assets", "stations")
    out = os.path.join(root, "docs", "station_integrity_failed_preview.png")
    which = sys.argv[1] if len(sys.argv) > 1 else "integrity"
    files = {
        "integrity": "station_integrity_3x3.png",
        "calories": "station_calories_2x2.png",
        "oxygen": "station_oxygen_3x3.png",
    }
    path = os.path.join(assets, files.get(which, files["integrity"]))
    if not os.path.isfile(path):
        print(f"Missing asset: {path}", file=sys.stderr)
        return 1

    pygame.init()
    # Needed for convert_alpha() on some SDL builds
    pygame.display.set_mode((64, 64), pygame.HIDDEN)
    img = pygame.image.load(path).convert_alpha()
    iw, ih = img.get_width(), img.get_height()
    target = max(24, int(COLONIST_PX * STATION_SPRITE_VS_COLONIST))
    longest = max(iw, ih)
    scale = target / float(longest)
    new_w = max(1, int(round(iw * scale)))
    new_h = max(1, int(round(ih * scale)))
    scaled = pygame.transform.smoothscale(img, (new_w, new_h))

    pad = 24
    canvas = pygame.Surface((new_w + pad * 2, new_h + pad * 2), pygame.SRCALPHA)
    canvas.fill((40, 42, 48, 255))
    dest = scaled.get_rect(center=(canvas.get_width() // 2, canvas.get_height() // 2))
    canvas.blit(scaled, dest)
    sub = canvas.subsurface(dest).copy()
    _failed_overlay(sub)
    canvas.blit(sub, dest)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    pygame.image.save(canvas, out)
    print(out)
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
