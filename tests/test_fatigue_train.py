"""IRC:6-2017 cl. 204.6 with the Fig. 7A Fatigue Load Train of Amendment 8 (reprinted in Amendment 10 S.No. 35).

The 400 kN truck (120, 140, 140 kN at 4.5, 1.4 m) must be in the train; 120 kN trucks (36, 42, 42 kN, same spacings) stand ahead
and behind at 20 m (min) from rear axle to the next front axle, as many as the influence line holds. Single passage, worst range.
"""

import numpy as np
import pytest

from setu.analysis.along_span import along_the_mesh, positions_along_span, response_to_one_vehicle_everywhere
from setu.analysis.fatigue import fatigue_range
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.fatigue import centreline_band_m, fatigue_impact_factor, fatigue_train_offsets, fatigue_train_pitch_m, light_trucks_that_fit

from test_golden_values import DUAL_CARRIAGEWAY, sagging_surface


def test_the_train_geometry_is_fig_7a():
    offsets = fatigue_train_offsets(1, 1)
    axles = sorted({round(float(dx), 6) for dx in offsets[:, 0]})
    loads = {round(float(dx), 6): 0.0 for dx in offsets[:, 0]}
    for dx, _, load in offsets:
        loads[round(float(dx), 6)] += load

    assert fatigue_train_pitch_m() == pytest.approx(5.9 + 20.0)
    assert axles == pytest.approx([0.0, 4.5, 5.9, 25.9, 30.4, 31.8, 51.8, 56.3, 57.7])
    assert [loads[a] for a in axles] == pytest.approx([36, 42, 42, 120, 140, 140, 36, 42, 42])
    assert offsets[:, 2].sum() == pytest.approx(120 + 400 + 120)


def test_light_trucks_that_fit_on_the_span():
    assert light_trucks_that_fit(25.9) == 1
    assert light_trucks_that_fit(35.0) == 2


def brute_force_range(surface, cross_section, span_m):
    """Every train configuration and every line of every carriageway, on a fine grid, without the production search."""
    on_the_mesh = surface.along_the_mesh()
    most = light_trucks_that_fit(span_m)
    factor = fatigue_impact_factor(span_m)
    best = 0.0
    for ahead in range(most + 1):
        for behind in range(most + 1):
            sheared = along_the_mesh(fatigue_train_offsets(ahead, behind), surface.skew)
            x_front_m = positions_along_span(on_the_mesh, sheared)
            for carriageway in cross_section.carriageways():
                z_from_m, z_to_m = centreline_band_m(carriageway)
                z_m = np.linspace(z_from_m, z_to_m, 41)
                r = factor * response_to_one_vehicle_everywhere(on_the_mesh, sheared, x_front_m, z_m, DEFAULT_SAMPLING)
                best = max(best, float((np.maximum(r.max(axis=0), 0) - np.minimum(r.min(axis=0), 0)).max()))
    return best


def test_the_search_finds_the_brute_force_range():
    surface = sagging_surface()
    found = fatigue_range(surface, DUAL_CARRIAGEWAY, 35.0, DEFAULT_SAMPLING)

    assert found.range >= brute_force_range(surface, DUAL_CARRIAGEWAY, 35.0) - 1e-9


def test_the_train_is_never_less_than_the_400_kn_truck_alone():
    from setu.analysis.fatigue import fatigue_range_of_one_train
    surface = sagging_surface()
    alone = fatigue_range_of_one_train(surface.along_the_mesh(), surface.skew, DUAL_CARRIAGEWAY, 35.0, DEFAULT_SAMPLING, 0, 0)
    found = fatigue_range(surface, DUAL_CARRIAGEWAY, 35.0, DEFAULT_SAMPLING)

    assert found.range >= alone.range
