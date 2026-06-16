"""Tests for keepout zone rendering – no hardware needed."""

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from keepout import zones_to_keepout_pgm, build_keepout_map


@pytest.fixture
def tmp_output(tmp_path):
    return tmp_path


def test_empty_zones_produces_all_free_map(tmp_output):
    pgm = tmp_output / "k.pgm"
    yml = tmp_output / "k.yaml"
    zones_to_keepout_pgm(
        zones=[],
        map_origin_x=0.0, map_origin_y=0.0,
        resolution=0.05, width_px=100, height_px=100,
        output_pgm=pgm, output_yaml=yml,
    )
    arr = np.array(Image.open(pgm))
    assert arr.min() == 254, "Empty zone map should be entirely free (254)"


def test_full_coverage_zone_produces_lethal_map(tmp_output):
    pgm = tmp_output / "k.pgm"
    yml = tmp_output / "k.yaml"
    # A huge polygon covering the whole 5×5 m map
    zones = [{
        "name": "all",
        "points": [[-0.1, -0.1], [5.1, -0.1], [5.1, 5.1], [-0.1, 5.1]],
    }]
    zones_to_keepout_pgm(
        zones=zones,
        map_origin_x=0.0, map_origin_y=0.0,
        resolution=0.05, width_px=100, height_px=100,
        output_pgm=pgm, output_yaml=yml,
    )
    arr = np.array(Image.open(pgm))
    # Expect most pixels to be 0 (keepout); allow a small boundary margin
    assert arr.mean() < 50, "Full-coverage zone should mark most pixels as keepout"


def test_partial_zone_marks_correct_area(tmp_output):
    pgm = tmp_output / "k.pgm"
    yml = tmp_output / "k.yaml"
    # 5m×5m map, resolution 0.05 → 100×100 px
    # Zone covers bottom-left quarter (x∈[0,2.5], y∈[0,2.5])
    zones = [{
        "name": "bottom-left",
        "points": [[0.0, 0.0], [2.5, 0.0], [2.5, 2.5], [0.0, 2.5]],
    }]
    zones_to_keepout_pgm(
        zones=zones,
        map_origin_x=0.0, map_origin_y=0.0,
        resolution=0.05, width_px=100, height_px=100,
        output_pgm=pgm, output_yaml=yml,
    )
    arr = np.array(Image.open(pgm))
    # Top-right pixel should be free
    assert arr[0, 99] == 254
    # Bottom-left interior should be keepout (0)
    assert arr[99, 0] == 0 or arr[95, 4] == 0


def test_yaml_is_written_with_correct_fields(tmp_output):
    pgm = tmp_output / "k.pgm"
    yml = tmp_output / "k.yaml"
    zones_to_keepout_pgm(
        zones=[],
        map_origin_x=-1.5, map_origin_y=-2.0,
        resolution=0.1, width_px=50, height_px=50,
        output_pgm=pgm, output_yaml=yml,
    )
    text = yml.read_text()
    assert "resolution: 0.1" in text
    assert "-1.5" in text
    assert "-2.0" in text
    assert "image:" in text


def test_build_keepout_map_wrapper(tmp_output):
    zones = [{"name": "z1", "points": [[1, 1], [2, 1], [2, 2], [1, 2]]}]
    map_meta = {
        "origin_x": 0.0, "origin_y": 0.0,
        "resolution": 0.05,
        "width": 100, "height": 100,
    }
    pgm, yml = build_keepout_map(zones, map_meta, tmp_output / "out")
    assert pgm.exists()
    assert yml.exists()


def test_degenerate_zone_with_less_than_3_points_is_skipped(tmp_output):
    pgm = tmp_output / "k.pgm"
    yml = tmp_output / "k.yaml"
    zones = [{"name": "bad", "points": [[0, 0], [1, 0]]}]  # only 2 points
    zones_to_keepout_pgm(
        zones=zones,
        map_origin_x=0.0, map_origin_y=0.0,
        resolution=0.05, width_px=100, height_px=100,
        output_pgm=pgm, output_yaml=yml,
    )
    arr = np.array(Image.open(pgm))
    # Should still be all free
    assert arr.min() == 254
