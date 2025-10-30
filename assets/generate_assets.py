from __future__ import annotations

import logging
import math
import struct
import zlib
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent
_GENERATED_DIR = _BASE_DIR / "generated"
_ASSETS = {
    "background": _GENERATED_DIR / "ai_bg.png",
    "logo": _GENERATED_DIR / "ztt_logo.png",
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _write_png(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int, int]]]) -> None:
    """Write a simple RGBA PNG file using raw pixel values."""
    rows = []
    for row in pixels:
        row_bytes = bytearray()
        for r, g, b, a in row:
            row_bytes.extend([r, g, b, a])
        rows.append(bytes(row_bytes))
    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0
    compressed = zlib.compress(raw)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes = PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")
    path.write_bytes(png_bytes)


def _generate_background(width: int = 640, height: int = 360) -> list[list[tuple[int, int, int, int]]]:
    pixels: list[list[tuple[int, int, int, int]]] = []
    for y in range(height):
        row: list[tuple[int, int, int, int]] = []
        for x in range(width):
            t = x / max(1, width - 1)
            u = y / max(1, height - 1)
            # blue to purple gradient with subtle grid noise
            r = int(30 + 70 * t + 25 * math.sin(12 * t + 3 * u))
            g = int(45 + 90 * u)
            b = int(120 + 100 * (1 - t) + 15 * math.cos(8 * u))
            # clamp values
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            alpha = 235
            row.append((r, g, b, alpha))
        pixels.append(row)
    return pixels


def _generate_logo(size: int = 220) -> list[list[tuple[int, int, int, int]]]:
    pixels: list[list[tuple[int, int, int, int]]] = []
    center = size / 2
    radius = size * 0.45
    for y in range(size):
        row: list[tuple[int, int, int, int]] = []
        for x in range(size):
            dx = x - center
            dy = y - center
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius:
                base = 30 + int(40 * (1 - dist / radius))
                r = base
                g = base + 20
                b = 80 + int(120 * (1 - dist / radius))
                alpha = 255
            else:
                r = g = b = 0
                alpha = 0
            row.append((r, g, b, alpha))
        pixels.append(row)

    # Draw block letters for ZTT AI using simple rectangles
    def paint_rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
        for yy in range(max(0, y0), min(size, y1)):
            row = pixels[yy]
            for xx in range(max(0, x0), min(size, x1)):
                row[xx] = color

    white = (240, 240, 255, 255)
    cyan = (0, 224, 255, 255)
    amber = (255, 180, 60, 255)

    # Z letter
    paint_rect(int(size * 0.2), int(size * 0.28), int(size * 0.8), int(size * 0.35), white)
    paint_rect(int(size * 0.2), int(size * 0.65), int(size * 0.8), int(size * 0.72), white)
    for i in range(int(size * 0.42)):
        y = int(size * 0.35) + i
        x = int(size * 0.2) + i
        if y < size and x < size:
            pixels[y][x] = white

    # T blocks
    paint_rect(int(size * 0.22), int(size * 0.75), int(size * 0.78), int(size * 0.8), cyan)
    paint_rect(int(size * 0.34), int(size * 0.8), int(size * 0.42), int(size * 0.92), cyan)
    paint_rect(int(size * 0.58), int(size * 0.8), int(size * 0.66), int(size * 0.92), cyan)

    # AI badge
    paint_rect(int(size * 0.65), int(size * 0.18), int(size * 0.82), int(size * 0.38), amber)
    paint_rect(int(size * 0.66), int(size * 0.25), int(size * 0.7), int(size * 0.33), white)
    paint_rect(int(size * 0.72), int(size * 0.25), int(size * 0.74), int(size * 0.33), white)
    paint_rect(int(size * 0.76), int(size * 0.25), int(size * 0.8), int(size * 0.33), white)
    paint_rect(int(size * 0.73), int(size * 0.18), int(size * 0.75), int(size * 0.24), white)
    paint_rect(int(size * 0.73), int(size * 0.33), int(size * 0.75), int(size * 0.38), white)

    return pixels


def ensure_assets(force: bool = False) -> None:
    """Ensure placeholder PNG assets exist as real images."""
    _GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    background = _ASSETS["background"]
    logo = _ASSETS["logo"]

    if force or not background.exists() or not background.read_bytes().startswith(PNG_SIGNATURE):
        logging.info("生成占位背景图 %s", background.name)
        pixels = _generate_background()
        _write_png(background, len(pixels[0]), len(pixels), pixels)

    if force or not logo.exists() or not logo.read_bytes().startswith(PNG_SIGNATURE):
        logging.info("生成占位 Logo %s", logo.name)
        pixels = _generate_logo()
        _write_png(logo, len(pixels[0]), len(pixels), pixels)


if __name__ == "__main__":
    ensure_assets(force=True)
