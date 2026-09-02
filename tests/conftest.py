"""Shared fixtures: influence surfaces with known shapes, and a deck to put them on."""


import numpy as np
import pytest

from src.models.deck import DeckCrossSection
from src.services.influence_surface import InfluenceSurface

SPAN_M = 35.0
WIDTH_M = 13.5


def _across_the_width(width_mesh_m: np.ndarray, width_m: float) -> np.ndarray:
    """A gentle transverse variation, so which lane a vehicle uses matters."""
    return 1.0 + 0.35 * np.cos(np.pi * (width_mesh_m - width_m / 2) / width_m)


@pytest.fixture
def cross_section() -> DeckCrossSection:
    """A dual carriageway deck with a median, kerbs and footpaths."""
    return DeckCrossSection.from_widths(
        {
            "footpath_left": 1.50,
            "kerb_left": 0.45,
            "carriageway_1": 4.50,
            "median": 0.60,
            "carriageway_2": 4.50,
            "kerb_right": 0.45,
            "footpath_right": 1.50,
        }
    )


@pytest.fixture
def narrow_cross_section() -> DeckCrossSection:
    """A single carriageway narrow enough to attract the residual UDL."""
    return DeckCrossSection.from_widths(
        {"kerb_left": 0.50, "carriageway": 4.60, "kerb_right": 0.50}
    )


@pytest.fixture
def sagging_surface() -> InfluenceSurface:
    """A simply supported deck: midspan moment, one sign everywhere."""
    length_mesh_m = np.round(np.linspace(0, SPAN_M, 71), 9)
    width_mesh_m = np.round(np.linspace(0, WIDTH_M, 41), 9)

    at_midspan = SPAN_M / 2
    along = np.where(
        length_mesh_m <= at_midspan,
        length_mesh_m * (SPAN_M - at_midspan) / SPAN_M,
        at_midspan * (SPAN_M - length_mesh_m) / SPAN_M,
    )

    return InfluenceSurface(
        values=along[:, None] * _across_the_width(width_mesh_m, WIDTH_M)[None, :],
        length_mesh_m=length_mesh_m,
        width_mesh_m=width_mesh_m,
        name="midspan sagging moment",
    )


@pytest.fixture
def hogging_surface() -> InfluenceSurface:
    """A two-span continuous deck: hogging over the pier, adverse in both spans.

    This is the shape where a train of vehicles genuinely governs, because a
    second vehicle in the far span makes the hogging worse rather than relieving
    it.
    """
    length_mesh_m = np.round(np.linspace(0, 2 * SPAN_M, 141), 9)
    width_mesh_m = np.round(np.linspace(0, WIDTH_M, 41), 9)

    into_the_span = np.where(
        length_mesh_m <= SPAN_M,
        length_mesh_m / SPAN_M,
        (2 * SPAN_M - length_mesh_m) / SPAN_M,
    )
    along = -0.25 * SPAN_M * into_the_span * (1 - into_the_span) * (1 + into_the_span)

    return InfluenceSurface(
        values=along[:, None] * _across_the_width(width_mesh_m, WIDTH_M)[None, :],
        length_mesh_m=length_mesh_m,
        width_mesh_m=width_mesh_m,
        name="hogging moment over the pier",
    )
