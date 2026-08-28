# A smoke test for the pictures, because there was none.
#
# These do not check that a drawing looks right - nothing automatic can. They
# check that every drawing function still runs end to end on a real answer and
# puts something on its axes, which is enough to catch a rewrite that breaks
# one of them. Without this the largest file in the library had no coverage at
# all.

from __future__ import annotations

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from setu import (  # noqa: E402
    DeckCrossSection,
    InfluenceSurface,
    find_critical_position,
)
from setu.drawing import (  # noqa: E402
    animate_vehicle_along_span,
    draw_cross_section,
    draw_everything,
    draw_influence_along_span,
    draw_influence_surface,
    draw_response_across_width,
)

SPAN_M = 35.0
WIDTH_M = 13.5


@pytest.fixture(scope="module")
def deck() -> DeckCrossSection:
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


@pytest.fixture(scope="module")
def surface() -> InfluenceSurface:
    length_mesh_m = np.round(np.linspace(0.0, SPAN_M, 71), 9)
    width_mesh_m = np.round(np.linspace(0.0, WIDTH_M, 41), 9)
    at_midspan = SPAN_M / 2

    along = np.where(
        length_mesh_m <= at_midspan,
        length_mesh_m * (SPAN_M - at_midspan) / SPAN_M,
        at_midspan * (SPAN_M - length_mesh_m) / SPAN_M,
    )
    across = 1.0 + 0.35 * np.cos(np.pi * (width_mesh_m - WIDTH_M / 2) / WIDTH_M)

    return InfluenceSurface(
        values=along[:, None] * across[None, :],
        length_mesh_m=length_mesh_m,
        width_mesh_m=width_mesh_m,
        name="midspan sagging moment",
    )


@pytest.fixture(scope="module")
def critical(surface, deck):
    return find_critical_position(surface, deck, span_m=SPAN_M, adverse="maximum")


@pytest.fixture(autouse=True)
def close_every_figure():
    yield
    plt.close("all")


def test_the_whole_answer_draws_on_one_figure(surface, deck, critical):
    figure = draw_everything(surface, deck, critical, span_m=SPAN_M)

    assert len(figure.axes) == 4
    assert critical.response_name in figure._suptitle.get_text()


def test_the_influence_surface_draws(surface, critical):
    ax = draw_influence_surface(surface, critical)

    assert ax.has_data()


def test_the_influence_surface_draws_without_an_answer(surface):
    ax = draw_influence_surface(surface)

    assert ax.has_data()


def test_the_cross_section_draws_every_strip(deck, critical):
    ax = draw_cross_section(deck, critical)

    assert len(ax.patches) >= len(deck.strips)


def test_the_cross_section_draws_without_an_answer(deck):
    ax = draw_cross_section(deck)

    assert len(ax.patches) >= len(deck.strips)


def test_the_response_across_the_width_draws_a_line_per_vehicle(surface, deck, critical):
    ax = draw_response_across_width(surface, deck, critical, span_m=SPAN_M)

    assert ax.lines
    assert ax.get_legend() is not None


def test_the_influence_line_along_the_span_draws(surface, critical):
    ax = draw_influence_along_span(surface, critical)

    assert ax.lines


def test_the_vehicle_sweep_animates(surface, critical, tmp_path):
    # Actually written out, because that is what runs the frame function - and
    # the frame function is where the closures over the surface live.
    sweep = animate_vehicle_along_span(surface, critical, frames=4)
    gif = tmp_path / "sweep.gif"

    sweep.save(gif, writer="pillow", fps=4)

    assert gif.stat().st_size > 0
