"""IRC:6-2017 clause 206.3 as Amendment 10 prints it in kN/m2: footway live load falls with span, and with footway width past 30 m."""

import pytest

from setu.irc6.lanes import footway_pressure_kpa


@pytest.mark.parametrize(
    "span_m, width_m, kpa",
    [
        (5.0, 1.5, 4.0),
        (7.5, 1.5, 4.0),
        (20.0, 1.5, 4.0 - (40 * 20.0 - 300) / 900),
        (30.0, 1.5, 4.0 - (40 * 30.0 - 300) / 900),
        (35.0, 1.5, (4.0 - 2.6 + 48 / 35.0) * (16.5 - 1.5) / 15),
        (35.0, 3.0, (4.0 - 2.6 + 48 / 35.0) * (16.5 - 3.0) / 15),
    ],
)
def test_footway_pressure_follows_clause_206_3(span_m, width_m, kpa):
    assert footway_pressure_kpa(span_m, width_m) == pytest.approx(kpa)


@pytest.mark.parametrize("span_m, width_m, kpa", [(20.0, 1.5, 3.4444444), (30.0, 1.5, 3.0), (35.0, 1.5, 2.7714286), (35.0, 3.0, 2.4942857)])
def test_footway_pressure_by_hand(span_m, width_m, kpa):
    """Worked by hand: 4 - 500/900; 4 - 900/900; (1.4 + 48/35) x 1; (1.4 + 48/35) x 13.5/15."""
    assert footway_pressure_kpa(span_m, width_m) == pytest.approx(kpa, abs=1e-6)
