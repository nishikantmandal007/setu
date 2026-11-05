"""Mesh along the span set by element length, with finer elements at the bearings; named presets (numerical choices, not IRC values)."""

import numpy as np
import pytest

from setu.builder.mesh import stations_along_span
from setu.models.bridge import MESH_PRESETS, MeshSettings

BRACE_LINES_M = np.array([0.0, 17.5, 35.0])


def test_element_length_splits_each_bay_into_the_fewest_equal_elements():
    stations = stations_along_span(BRACE_LINES_M, MeshSettings(None, 0.15, element_length_m=1.5))
    steps = np.diff(stations)

    assert steps.max() <= 1.5 + 1e-9
    assert len(stations) == 2 * 12 + 1
    assert set(np.round(BRACE_LINES_M, 6)) <= set(np.round(stations, 6))


def test_the_bearing_zone_takes_short_elements_and_the_rest_stays_coarse():
    stations = stations_along_span(BRACE_LINES_M, MeshSettings.preset("standard"))
    near_start = stations[stations <= 1.5 + 1e-9]
    near_end = stations[stations >= 35.0 - 1.5 - 1e-9]

    assert np.diff(near_start).max() <= 0.1 + 1e-9
    assert np.diff(near_end).max() <= 0.1 + 1e-9
    assert np.diff(stations).max() == pytest.approx(17.5 / 12, abs=1e-4)  # stations are stored to 5 decimals


def test_presets_and_their_order():
    assert MESH_PRESETS["fast"][0] > MESH_PRESETS["standard"][0] > MESH_PRESETS["fine"][0]
    assert MESH_PRESETS["fast"][3] > MESH_PRESETS["standard"][3] > MESH_PRESETS["fine"][3]
    with pytest.raises(ValueError, match="preset"):
        MeshSettings.preset("medium")


def test_one_way_along_the_span():
    with pytest.raises(ValueError, match="either"):
        MeshSettings(4, 0.15, element_length_m=1.5)
    with pytest.raises(ValueError, match="go together"):
        MeshSettings(None, 0.15, element_length_m=1.5, support_zone_m=1.5)
