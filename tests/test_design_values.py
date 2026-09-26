"""One call, every girder: IRC:6 Annex B design values from all the loads setu builds."""

import pytest

from setu.models.custom_load import CustomLoad
from setu.models.site import SeismicSite, TemperatureSite, WindSite
from setu.irc6.combinations import custom_combination
from setu.postprocess.design_values import girder_design_values
from setu.utils.constants import (
    BASIC,
    BIGGER_IS_WORSE,
    DEAD,
    LIVE,
    MIDSPAN_MOMENT,
    PLAIN_TERRAIN,
    POINT,
    SEISMIC_COMBINATION,
    SMALLER_IS_WORSE,
    SUPPORT_SHEAR,
    SURFACING,
    WIND,
)

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")

from test_design_forces import BRIDGE  # noqa: E402

WIND_SITE = WindSite(basic_wind_speed_mps=39.0, terrain=PLAIN_TERRAIN, height_m=12.0, funnelling=False, solid_barrier_height_m=1.1)
SEISMIC_SITE = SeismicSite(zone="IV", soil="II", importance_factor=1.2, period_s=0.8, response_reduction=1.0)
HOARDING = CustomLoad("hoarding", POINT, 40.0, x_from_bearing_m=17.5, z_from_left_edge_m=3.0)


@pytest.fixture(scope="module")
def results():
    return girder_design_values(
        BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE, temperature=TemperatureSite(shade_max_c=45.0, shade_min_c=2.0),
        custom_loads=[HOARDING], custom_combinations=[custom_combination("hoarding check", {DEAD: 1.35, SURFACING: 1.75, "hoarding": 1.5})],
    )


def test_every_girder_and_response_gets_every_limit_state(results):
    for by_response in results.girders.values():
        for response in (MIDSPAN_MOMENT, SUPPORT_SHEAR):
            assert set(by_response[response]) >= {BASIC, SEISMIC_COMBINATION}
            assert set(by_response[response][BASIC]) == {BIGGER_IS_WORSE, SMALLER_IS_WORSE}


def test_a_design_value_is_the_sum_of_its_shares(results):
    governing = results.girders[1][MIDSPAN_MOMENT][BASIC][BIGGER_IS_WORSE]

    assert governing.value == pytest.approx(sum(governing.shares.values()))
    assert governing.shares[DEAD] > 0 and governing.shares[LIVE] > 0


def test_sagging_is_governed_by_live_load_leading(results):
    """For midspan sagging on this deck, live load (1.5) outweighs wind leading (1.5 on a much smaller effect)."""
    assert results.girders[1][MIDSPAN_MOMENT][BASIC][BIGGER_IS_WORSE].combination.endswith("live leading")


def test_symmetric_deck_gives_mirror_girders_the_same_values(results):
    """Wind is enveloped from both sides and the custom load only enters its own combination, so ULS is symmetric."""
    first = results.girders[0][MIDSPAN_MOMENT][BASIC][BIGGER_IS_WORSE].value
    last = results.girders[BRIDGE.girders.count - 1][MIDSPAN_MOMENT][BASIC][BIGGER_IS_WORSE].value

    assert first == pytest.approx(last, rel=1e-6)


def test_the_custom_group_only_shows_in_its_own_combination(results):
    by_limit_state = results.girders[0][MIDSPAN_MOMENT]

    assert "hoarding" not in by_limit_state[BASIC][BIGGER_IS_WORSE].shares
    assert by_limit_state["custom"][BIGGER_IS_WORSE].shares["hoarding"] > 0


def test_the_governing_girder_is_reported(results):
    girder, governing = results.governing(MIDSPAN_MOMENT, BASIC)

    assert governing.value == max(results.girders[g][MIDSPAN_MOMENT][BASIC][BIGGER_IS_WORSE].value for g in results.girders)


def test_temperature_comes_back_as_stresses_and_bearing_movement(results):
    thermal = results.thermal

    assert thermal["positive difference"].slab_top_kpa < 0
    assert thermal["free bearing movement m"] == pytest.approx(12e-6 * 35.0 * 68.0)
    assert "reverse difference" not in thermal


def test_high_wind_keeps_live_load_off(results):
    """Vb 55 m/s at 30 m: hourly mean speed above 36 m/s, so wind and live load never act together."""
    stormy = girder_design_values(BRIDGE, wind=WindSite(basic_wind_speed_mps=55.0, terrain=PLAIN_TERRAIN, height_m=30.0, funnelling=False, solid_barrier_height_m=0.0))

    for by_response in stormy.girders.values():
        for by_direction in by_response[MIDSPAN_MOMENT].values():
            for governing in by_direction.values():
                assert not (governing.shares.get(LIVE) and governing.shares.get(WIND))


def test_braking_rides_with_the_live_load(results):
    """The live group carries the searched vehicles plus braking (211), in whichever direction adds."""
    from setu.analysis.critical_position import find_critical_position
    from setu.analysis.influence_surface import InfluenceSolver
    from setu.builder.assembly import build_bridge_model

    model = build_bridge_model(BRIDGE)
    surface = InfluenceSolver(model.as_deck_model()).for_girder_shear("v", model.element_of_girder_at(1, 0))
    vehicles_only = find_critical_position(surface, BRIDGE.cross_section, span_m=BRIDGE.span_m, adverse=SMALLER_IS_WORSE,
                                           wearing_course_thickness_m=BRIDGE.wearing_course_thickness_m).response
    live_share = results.girders[1][SUPPORT_SHEAR][BASIC][SMALLER_IS_WORSE].shares[LIVE]

    assert live_share / 1.5 < vehicles_only


def test_seismic_is_symmetric_too(results):
    """Each girder's seismic mass carries 20 % of its own governing traffic, so mirror girders match."""
    first = results.girders[0][MIDSPAN_MOMENT][SEISMIC_COMBINATION][BIGGER_IS_WORSE].value
    last = results.girders[BRIDGE.girders.count - 1][MIDSPAN_MOMENT][SEISMIC_COMBINATION][BIGGER_IS_WORSE].value

    assert first == pytest.approx(last, rel=1e-6)
