"""IRC:6-2017 clause 206.3: footway live load falls with span, and with footway width past 30 m."""

import pytest

from setu.irc6.lanes import footway_pressure_kpa

KPA_PER_KG_M2 = 9.81 / 1000


@pytest.mark.parametrize(
    "span_m, width_m, kg_m2",
    [
        (5.0, 1.5, 400.0),
        (7.5, 1.5, 400.0),
        (20.0, 1.5, 400.0 - (40 * 20.0 - 300) / 9),
        (30.0, 1.5, 400.0 - (40 * 30.0 - 300) / 9),
        (35.0, 1.5, (400.0 - 260 + 4800 / 35.0) * (16.5 - 1.5) / 15),
        (35.0, 3.0, (400.0 - 260 + 4800 / 35.0) * (16.5 - 3.0) / 15),
    ],
)
def test_footway_pressure_follows_clause_206_3(span_m, width_m, kg_m2):
    assert footway_pressure_kpa(span_m, width_m) == pytest.approx(kg_m2 * KPA_PER_KG_M2)


@pytest.mark.parametrize("span_m", [5.0, 20.0, 35.0])
def test_a_crowd_is_never_reduced(span_m):
    assert footway_pressure_kpa(span_m, 1.5, crowd=True) == pytest.approx(500.0 * KPA_PER_KG_M2)
