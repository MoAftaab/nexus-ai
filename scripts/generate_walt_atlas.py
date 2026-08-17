"""Build WALT's local Codex/Petdex atlas from the approved character anchor.

The output follows the transparent 8x9 atlas contract (192x208 cells).  The
source frames are also kept individually so an animator can replace or refine
any motion without changing the application integration.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance


CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9

ROW_DEFINITIONS = (
    ("idle", 6),
    ("running-right", 8),
    ("running-left", 8),
    ("waving", 4),
    ("jumping", 5),
    ("failed", 8),
    ("waiting", 6),
    ("running", 6),
    ("review", 6),
)

CYAN = (56, 207, 228, 220)
BLUE = (140, 190, 230, 220)
NEON = (194, 254, 6, 235)
AMBER = (252, 205, 34, 230)
CORAL = (230, 115, 100, 230)
DEEP = (0, 39, 51, 225)


def _contain(image: Image.Image, maximum_width: int = 178, maximum_height: int = 198) -> Image.Image:
    alpha_bounds = image.getchannel("A").getbbox()
    if alpha_bounds:
        image = image.crop(alpha_bounds)
    scale = min(maximum_width / image.width, maximum_height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _transformed(base: Image.Image, *, scale: float = 1.0, angle: float = 0, flip: bool = False) -> Image.Image:
    width = max(1, round(base.width * scale))
    height = max(1, round(base.height * scale))
    frame = base.resize((width, height), Image.Resampling.LANCZOS)
    if flip:
        frame = frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if angle:
        frame = frame.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    return frame


def _speed_lines(draw: ImageDraw.ImageDraw, direction: str, phase: int, strong: bool = False) -> None:
    color = CYAN if strong else BLUE
    lengths = (23, 14, 31)
    for index, length in enumerate(lengths):
        y = 98 + (index * 18) + ((phase + index) % 2) * 3
        if direction == "right":
            x = 4 + ((phase * 5 + index * 9) % 16)
            draw.rounded_rectangle((x, y, x + length, y + 2), radius=1, fill=color)
        else:
            x = CELL_WIDTH - 4 - ((phase * 5 + index * 9) % 16)
            draw.rounded_rectangle((x - length, y, x, y + 2), radius=1, fill=color)


def _review_overlay(draw: ImageDraw.ImageDraw, phase: int) -> None:
    x = 120 + (phase % 2)
    y = 66 - (phase % 3)
    draw.rounded_rectangle((x, y, x + 57, y + 48), radius=7, fill=(0, 39, 51, 218), outline=BLUE, width=2)
    draw.rectangle((x + 8, y + 9, x + 35, y + 12), fill=CYAN)
    bars = (18, 31, 23, 38)
    for index, value in enumerate(bars):
        bar_x = x + 8 + index * 9
        draw.rounded_rectangle((bar_x, y + 39 - value // 3, bar_x + 5, y + 39), radius=2, fill=NEON if index == phase % 4 else BLUE)
    scan_y = y + 7 + ((phase * 7) % 33)
    draw.line((x + 5, scan_y, x + 52, scan_y), fill=NEON, width=2)


def _frame(base: Image.Image, row_name: str, frame_index: int) -> Image.Image:
    canvas = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    scale = 1.0
    angle = 0.0
    offset_x = 0
    offset_y = 0
    flip = row_name == "running-left"

    if row_name == "idle":
        offset_y = (-1, -3, -5, -3, -1, 0)[frame_index]
        scale = (1.0, 1.008, 1.016, 1.008, 1.0, .995)[frame_index]
    elif row_name in {"running-right", "running-left"}:
        offset_y = (0, -4, -1, -5, 0, -3, -1, -4)[frame_index]
        offset_x = (2, 4, 3, 5, 2, 4, 3, 5)[frame_index] * (1 if row_name == "running-right" else -1)
        angle = (-1.5, 1.5, -2, 2, -1, 1, -2, 2)[frame_index] * (1 if row_name == "running-right" else -1)
        _speed_lines(draw, "right" if row_name == "running-right" else "left", frame_index)
    elif row_name == "waving":
        offset_y = (0, -3, -1, -4)[frame_index]
        angle = (-1.0, 1.8, -1.7, 1.2)[frame_index]
        for ray in range(3):
            ray_y = 28 + ray * 9 + (frame_index % 2) * 2
            draw.arc((145 + ray * 2, ray_y, 181, ray_y + 22), 205, 304, fill=NEON, width=2)
    elif row_name == "jumping":
        offset_y = (0, -17, -31, -17, 0)[frame_index]
        scale = (1.0, .97, .94, .97, 1.0)[frame_index]
        glow_width = (48, 39, 29, 39, 48)[frame_index]
        draw.ellipse((96 - glow_width, 192, 96 + glow_width, 201), fill=(194, 254, 6, 55))
    elif row_name == "failed":
        angle = (0, 8, 18, 31, 48, 63, 69, 66)[frame_index]
        offset_x = (0, 1, 3, 5, 8, 10, 12, 12)[frame_index]
        offset_y = (0, 1, 4, 9, 15, 21, 24, 24)[frame_index]
        glitch_y = 45 + (frame_index * 17) % 100
        draw.rectangle((13, glitch_y, 67, glitch_y + 2), fill=CORAL)
        draw.rectangle((124, glitch_y + 8, 180, glitch_y + 10), fill=CORAL)
    elif row_name == "waiting":
        offset_y = (0, -1, -2, -1, 0, 1)[frame_index]
        offset_x = (-2, -1, 0, 1, 2, 0)[frame_index]
        for dot in range(3):
            alpha = 235 if dot == frame_index % 3 else 90
            draw.ellipse((75 + dot * 15, 13, 82 + dot * 15, 20), fill=(*AMBER[:3], alpha))
    elif row_name == "running":
        offset_y = (0, -6, -2, -7, -2, -5)[frame_index]
        angle = (-2.5, 2.5, -2.5, 2.5, -1.5, 1.5)[frame_index]
        scale = 1.02
        _speed_lines(draw, "right", frame_index, strong=True)
    elif row_name == "review":
        offset_y = (0, -1, -2, -1, 0, -1)[frame_index]
        angle = (-1, 0, 1, 1, 0, -1)[frame_index]
        _review_overlay(draw, frame_index)

    character = _transformed(base, scale=scale, angle=angle, flip=flip)
    x = round((CELL_WIDTH - character.width) / 2) + offset_x
    y = CELL_HEIGHT - character.height - 3 + offset_y
    canvas.alpha_composite(character, (x, y))

    if row_name == "failed" and frame_index >= 4:
        canvas = ImageEnhance.Brightness(canvas).enhance(.84)
    return canvas


def build(source: Path, output_root: Path) -> None:
    anchor = Image.open(source).convert("RGBA")
    base = _contain(anchor)
    frames_root = output_root / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGBA", (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS), (0, 0, 0, 0))

    for row_index, (row_name, frame_count) in enumerate(ROW_DEFINITIONS):
        for frame_index in range(frame_count):
            frame = _frame(base, row_name, frame_index)
            frame.save(frames_root / f"{row_index:02}-{row_name}-{frame_index:02}.png", optimize=True)
            atlas.alpha_composite(frame, (frame_index * CELL_WIDTH, row_index * CELL_HEIGHT))

    atlas.save(output_root / "spritesheet.png", optimize=True)
    atlas.save(output_root / "spritesheet.webp", format="WEBP", lossless=True, method=6)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    default_root = project_root / "frontend" / "public" / "mascots" / "walt"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=default_root / "source" / "walt-character-anchor.png")
    parser.add_argument("--output", type=Path, default=default_root)
    arguments = parser.parse_args()
    build(arguments.source.resolve(), arguments.output.resolve())


if __name__ == "__main__":
    main()
