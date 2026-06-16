"""
keepout.py – Converts named polygon zones into a Nav2-compatible keepout filter map.

The output is a YAML + PGM pair that Nav2's costmap_filter_info_server can load
directly.  On zone change the caller must reload the relevant Nav2 lifecycle node
(see main.py → apply_zones).

HARDWARE NOTE: The final integration (writing the map files to the paths expected
by your Nav2 launch file and calling the lifecycle service) requires the real
robot.  In mock mode the files are written to /tmp and no lifecycle call is made.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

Zone = dict  # {"name": str, "points": [[x_m, y_m], ...]}


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

def zones_to_keepout_pgm(
    zones: Sequence[Zone],
    map_origin_x: float,
    map_origin_y: float,
    resolution: float,   # metres per pixel
    width_px: int,
    height_px: int,
    output_pgm: Path,
    output_yaml: Path,
) -> None:
    """
    Render *zones* into a binary keepout PGM and write the companion YAML.

    Pixels inside any zone polygon → 0 (lethal / occupied).
    All other pixels → 254 (free).

    Nav2 keepout filter convention:
      0   = keepout (obstacle)
      254 = free
    """
    canvas = np.full((height_px, width_px), 254, dtype=np.uint8)

    for zone in zones:
        pts_m = zone.get("points", [])
        if len(pts_m) < 3:
            continue
        # Convert metres → pixel indices
        pts_px = [
            (
                int((x - map_origin_x) / resolution),
                # ROS map Y is up; image Y is down → flip
                height_px - 1 - int((y - map_origin_y) / resolution),
            )
            for x, y in pts_m
        ]
        _fill_polygon(canvas, pts_px, value=0)

    img = Image.fromarray(canvas, mode="L")
    img.save(str(output_pgm))

    _write_yaml(output_yaml, output_pgm, map_origin_x, map_origin_y, resolution)


def _write_yaml(
    yaml_path: Path,
    pgm_path: Path,
    origin_x: float,
    origin_y: float,
    resolution: float,
) -> None:
    content = (
        f"image: {pgm_path.name}\n"
        f"resolution: {resolution}\n"
        f"origin: [{origin_x}, {origin_y}, 0.0]\n"
        "negate: 0\n"
        "occupied_thresh: 0.65\n"
        "free_thresh: 0.196\n"
    )
    yaml_path.write_text(content)


# ---------------------------------------------------------------------------
# Polygon rasterisation (no external polygon library needed)
# ---------------------------------------------------------------------------

def _fill_polygon(canvas: np.ndarray, vertices: list[tuple[int, int]], value: int) -> None:
    """Scanline fill of an integer-coordinate polygon onto *canvas* in-place."""
    if not vertices:
        return
    h, w = canvas.shape
    min_y = max(0, min(v[1] for v in vertices))
    max_y = min(h - 1, max(v[1] for v in vertices))

    for y in range(min_y, max_y + 1):
        xs = _scanline_intersections(vertices, y)
        for i in range(0, len(xs) - 1, 2):
            x0 = max(0, min(w - 1, xs[i]))
            x1 = max(0, min(w - 1, xs[i + 1]))
            canvas[y, x0 : x1 + 1] = value


def _scanline_intersections(vertices: list[tuple[int, int]], y: int) -> list[int]:
    """Return sorted list of x-coordinates where scan line y crosses polygon edges."""
    xs: list[float] = []
    n = len(vertices)
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        if y0 == y1:
            continue
        if not (min(y0, y1) <= y < max(y0, y1)):
            continue
        x_intersect = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        xs.append(x_intersect)
    xs.sort()
    return [int(round(x)) for x in xs]


# ---------------------------------------------------------------------------
# Convenience wrapper used by main.py
# ---------------------------------------------------------------------------

def build_keepout_map(
    zones: list[Zone],
    map_meta: dict,
    output_dir: Path,
) -> tuple[Path, Path]:
    """
    Build PGM + YAML from *zones* using *map_meta* (from /api/map response).

    Returns (pgm_path, yaml_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pgm = output_dir / "keepout.pgm"
    yml = output_dir / "keepout.yaml"

    zones_to_keepout_pgm(
        zones=zones,
        map_origin_x=map_meta["origin_x"],
        map_origin_y=map_meta["origin_y"],
        resolution=map_meta["resolution"],
        width_px=map_meta["width"],
        height_px=map_meta["height"],
        output_pgm=pgm,
        output_yaml=yml,
    )
    return pgm, yml
