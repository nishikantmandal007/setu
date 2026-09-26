"""IRC:6-2017 Annex B load combinations, applied to a girder's effects.

Para 3: one variable load leads at a time, the others accompany, and a variable
load that relieves the effect is ignored. Permanent loads take their adding or
relieving factor. Table B.2 (ULS strength) and Table B.3 (SLS) give the factors.
"""

import pytest

from setu.irc6.combinations import custom_combination, design_value, irc6_combinations
from setu.utils.constants import (
    BASIC,
    BIGGER_IS_WORSE,
    DEAD,
    FREQUENT,
    LIVE,
    QUASI_PERMANENT,
    RARE,
    SEISMIC,
    SEISMIC_COMBINATION,
    SMALLER_IS_WORSE,
    SURFACING,
    THERMAL,
    WIND,
)


def _named(limit_state, leading=None, **options):
    for combination in irc6_combinations(**options):
        if combination.limit_state == limit_state and combination.leading == leading:
            return combination
    raise AssertionError(f"no {limit_state} combination with {leading} leading")


def test_one_combination_per_leading_variable_load():
    """ULS basic and SLS rare/frequent: live, wind and thermal each lead once; seismic and quasi-permanent once."""
    counts = {}
    for combination in irc6_combinations():
        counts[combination.limit_state] = counts.get(combination.limit_state, 0) + 1

    assert counts == {BASIC: 3, SEISMIC_COMBINATION: 1, RARE: 3, FREQUENT: 3, QUASI_PERMANENT: 1}


def test_table_b2_basic_with_live_leading():
    factors = _named(BASIC, LIVE).factors

    assert factors[DEAD] == (1.35, 1.0)
    assert factors[SURFACING] == (1.75, 1.0)
    assert factors[LIVE] == (1.5, 0.0)
    assert factors[WIND] == (0.9, 0.0)
    assert factors[THERMAL] == (0.9, 0.0)


def test_table_b2_basic_with_wind_leading():
    factors = _named(BASIC, WIND).factors

    assert factors[WIND] == (1.5, 0.0)
    assert factors[LIVE] == (1.15, 0.0)
    assert factors[THERMAL] == (0.9, 0.0)


def test_table_b2_seismic_column_has_no_wind():
    factors = _named(SEISMIC_COMBINATION, SEISMIC).factors

    assert factors[SEISMIC] == (1.5, 0.0)
    assert factors[LIVE] == (0.2, 0.0)
    assert factors[THERMAL] == (0.5, 0.0)
    assert WIND not in factors


def test_table_b3_serviceability_factors():
    assert _named(RARE, LIVE).factors[LIVE] == (1.0, 0.0)
    assert _named(RARE, LIVE).factors[WIND] == (0.6, 0.0)
    assert _named(FREQUENT, LIVE).factors[LIVE] == (0.75, 0.0)
    assert _named(FREQUENT, WIND).factors[LIVE] == (0.2, 0.0)
    assert _named(QUASI_PERMANENT).factors[LIVE] == (0.0, 0.0)
    assert _named(QUASI_PERMANENT).factors[THERMAL] == (0.5, 0.0)
    for combination in irc6_combinations():
        if combination.limit_state in (RARE, FREQUENT, QUASI_PERMANENT):
            assert combination.factors[DEAD] == (1.0, 1.0)
            assert combination.factors[SURFACING] == (1.2, 1.0)


def test_permanent_and_leading_loads_add_up():
    """1.35 x 100 + 1.75 x 20 + 1.5 x 50 + 0.9 x 10 = 135 + 35 + 75 + 9 = 254."""
    effects = {DEAD: 100.0, SURFACING: 20.0, LIVE: 50.0, WIND: 10.0}

    value, shares = design_value(effects, _named(BASIC, LIVE), BIGGER_IS_WORSE)

    assert value == pytest.approx(254.0)
    assert shares == pytest.approx({DEAD: 135.0, SURFACING: 35.0, LIVE: 75.0, WIND: 9.0, THERMAL: 0.0})


def test_a_relieving_variable_load_is_ignored():
    """Wind that pulls the other way is left out, not subtracted."""
    effects = {DEAD: 100.0, SURFACING: 20.0, LIVE: 50.0, WIND: -30.0}

    value, shares = design_value(effects, _named(BASIC, LIVE), BIGGER_IS_WORSE)

    assert value == pytest.approx(135.0 + 35.0 + 75.0)
    assert shares[WIND] == 0.0


def test_a_relieving_permanent_load_takes_its_relieving_factor():
    """Dead load that works against the live load's hogging moment counts at 1.0, not 1.35."""
    effects = {DEAD: 100.0, LIVE: -300.0}

    value, _ = design_value(effects, _named(BASIC, LIVE), SMALLER_IS_WORSE)

    assert value == pytest.approx(1.0 * 100.0 + 1.5 * -300.0)


def test_the_worst_direction_of_a_reversible_load_is_taken():
    effects = {DEAD: 100.0, WIND: [40.0, -40.0]}

    biggest, _ = design_value(effects, _named(BASIC, WIND), BIGGER_IS_WORSE)
    smallest, _ = design_value(effects, _named(BASIC, WIND), SMALLER_IS_WORSE)

    assert biggest == pytest.approx(1.35 * 100.0 + 1.5 * 40.0)
    assert smallest == pytest.approx(1.0 * 100.0 + 1.5 * -40.0)


def test_clause_209_3_7_no_live_load_in_high_wind():
    """Above 36 m/s at deck level the bridge carries no live load while that wind blows."""
    calm = _named(BASIC, WIND, wind_speed_at_deck_mps=30.0)
    stormy = _named(BASIC, WIND, wind_speed_at_deck_mps=40.0)
    live_leading_in_a_storm = _named(BASIC, LIVE, wind_speed_at_deck_mps=40.0)

    assert LIVE in calm.factors
    assert LIVE not in stormy.factors
    assert WIND not in live_leading_in_a_storm.factors


def test_a_custom_group_joins_only_a_custom_combination():
    effects = {DEAD: 100.0, "hoarding": 12.0}
    irc = _named(BASIC, LIVE)
    user = custom_combination("site hoarding", {DEAD: 1.35, "hoarding": 1.2})

    assert design_value(effects, irc, BIGGER_IS_WORSE)[0] == pytest.approx(135.0)
    assert design_value(effects, user, BIGGER_IS_WORSE)[0] == pytest.approx(135.0 + 14.4)
    assert user.factors["hoarding"] == (1.2, 1.2)
