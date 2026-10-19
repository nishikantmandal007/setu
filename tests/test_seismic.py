"""Seismic forces per IRC:SP:114-2018, which replaced IRC:6-2017 clause 218.

5.2.1: Ah = (Z/2) (I/R) (Sa/g), at 5 % damping for every material. Table 4.2 zone factors,
Table 5.2 minimum Ah; I, T and R come from OsdagBridge. Sa/g from Fig. 5.1(a) (IS 1893:2016).
4.2.1/4.2.3: vertical in zones IV and V, with the zone factor taken as two thirds and Sa/g 2.5.
4.2.2: directions combined r1 + 0.3 r2 (+ 0.3 r3) and its turns. 4.6: 20 % live load
(no impact) across the traffic and vertically, none along it.
"""

import pytest

from setu.analysis.results import CriticalPosition, VehiclePlacement
from setu.builder.assembly import build_bridge_model
from setu.irc6.seismic import (
    combine_directions,
    horizontal_seismic_coefficient,
    minimum_horizontal_coefficient,
    spectral_acceleration,
    vertical_seismic_coefficient,
    zone_factor,
)
from setu.loads.seismic_loads import seismic_load_cases
from setu.models.site import SeismicSite

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")
from setu.solver import backend  # noqa: E402

from test_design_forces import BRIDGE  # noqa: E402


def test_table_4_2_zone_factors():
    assert [zone_factor(zone) for zone in ("II", "III", "IV", "V")] == [0.10, 0.16, 0.24, 0.36]


def test_fig_5_1a_spectrum():
    """Plateau 2.5 to 0.40 / 0.55 / 0.67 s, then 1.00/T, 1.36/T, 1.67/T to 4 s, then 0.25 / 0.34 / 0.42."""
    assert spectral_acceleration(0.05, "I") == pytest.approx(2.5)
    assert spectral_acceleration(0.8, "I") == pytest.approx(1.00 / 0.8)
    assert spectral_acceleration(0.8, "II") == pytest.approx(1.36 / 0.8)
    assert spectral_acceleration(1.0, "III") == pytest.approx(1.67)
    assert spectral_acceleration(0.5, "II") == pytest.approx(2.5)
    assert spectral_acceleration(5.0, "I") == pytest.approx(0.25)
    assert spectral_acceleration(5.0, "II") == pytest.approx(0.34)
    assert spectral_acceleration(5.0, "III") == pytest.approx(0.42)


def test_horizontal_coefficient():
    """Zone IV, important, soil II, T = 0.8 s, R = 1: (0.24 / 2) x (1.2 / 1) x (1.36 / 0.8) = 0.2448."""
    site = SeismicSite(zone="IV", soil="II", importance_factor=1.2, period_s=0.8, response_reduction=1.0)

    assert horizontal_seismic_coefficient(site) == pytest.approx(0.12 * 1.2 * 1.36 / 0.8)


def test_table_5_2_minimum_governs():
    """Zone II, soil I, T = 4 s, R = 3: (0.10 / 2) x (1 / 3) x 0.25 = 0.0042, below the 0.011 minimum."""
    site = SeismicSite(zone="II", soil="I", importance_factor=1.0, period_s=4.0, response_reduction=3.0)

    assert minimum_horizontal_coefficient("II") == 0.011
    assert horizontal_seismic_coefficient(site) == pytest.approx(0.011)


def test_vertical_coefficient_uses_two_thirds_of_the_zone_factor():
    """Zone V, normal, soil I, R = 1: (2/3) x (0.36 / 2) x 1 x 2.5 = 0.30, whatever the horizontal period."""
    site = SeismicSite(zone="V", soil="I", importance_factor=1.0, period_s=2.0, response_reduction=1.0)

    assert vertical_seismic_coefficient(site) == pytest.approx(2.0 / 3.0 * 0.18 * 2.5)


def test_vertical_only_where_the_code_asks():
    assert SeismicSite("III", "II", 1.0, 0.5, 1.0).include_vertical is False
    assert SeismicSite("IV", "II", 1.0, 0.5, 1.0).include_vertical is True


def test_combining_the_three_directions():
    """r1 = 10, r2 = 4, r3 = 5: worst of 10 + 1.2 + 1.5, 3 + 4 + 1.5 and 3 + 1.2 + 5 is 12.7."""
    combined = combine_directions(10.0, 4.0, 5.0)

    assert max(combined) == pytest.approx(12.7)
    assert min(combined) == pytest.approx(-12.7)
    assert max(combine_directions(10.0, 4.0)) == pytest.approx(11.2)


SITE = SeismicSite(zone="IV", soil="II", importance_factor=1.2, period_s=0.8, response_reduction=1.0)
ONE_CLASS_A = CriticalPosition("t", "maximum", 0.0, 0.0, 1.0, 1, "", [VehiclePlacement("Class_A", 5.0, 5.0, 1.3, (5.0,))], 0.0, [], [], 0.0)
CLASS_A_KN = 55.4 * 9.81


@pytest.fixture(scope="module")
def seismic():
    model = build_bridge_model(BRIDGE)
    return model, seismic_load_cases(model, SITE, live_critical=ONE_CLASS_A)


def _totals(case):
    with backend.solved(case.nodal_loads, case.element_loads, pattern=103):
        backend.calculate_reactions()
        tags = backend.node_tags()
        totals = [sum(backend.node_reaction(node, dof) for node in tags) for dof in (1, 2, 3)]

    return totals


def test_longitudinal_base_shear_carries_no_live_load(seismic):
    _, cases = seismic
    along_kn, _, _ = _totals(cases["longitudinal"])

    assert -along_kn == pytest.approx(horizontal_seismic_coefficient(SITE) * cases.dead_weight_kn, rel=1e-9)


def test_transverse_base_shear_carries_a_fifth_of_the_live_load(seismic):
    _, cases = seismic
    _, _, across_kn = _totals(cases["transverse"])

    assert -across_kn == pytest.approx(horizontal_seismic_coefficient(SITE) * (cases.dead_weight_kn + 0.2 * CLASS_A_KN), rel=1e-9)


def test_vertical_seismic_force(seismic):
    _, cases = seismic
    _, up_kn, _ = _totals(cases["vertical"])

    assert up_kn == pytest.approx(vertical_seismic_coefficient(SITE) * (cases.dead_weight_kn + 0.2 * CLASS_A_KN), rel=1e-9)


def test_the_seismic_weight_is_the_whole_dead_load(seismic):
    """Slab, surfacing, footpaths and kerbs, girders and bracing: the same total the dead load puts down."""
    from setu.loads.dead_loads import steel_self_weight_load, superimposed_dead_load, surfacing_load, wet_slab_load

    model, cases = seismic
    steel_stage = steel_self_weight_load(model)
    element_kn = -sum(p[0] for _, _, p in steel_stage.element_loads) * BRIDGE.span_m / (model.mesh.stations_along_span - 1)
    nodal_kn = -sum(fy for _, _, fy, *_ in steel_stage.nodal_loads + wet_slab_load(model).nodal_loads + superimposed_dead_load(model).nodal_loads + surfacing_load(model).nodal_loads)

    assert cases.dead_weight_kn == pytest.approx(element_kn + nodal_kn, rel=1e-9)


def test_explicit_effective_coefficients_and_full_weight_overrides():
    model = build_bridge_model(BRIDGE)
    site = SeismicSite("II", "I", 1., .5, 2., horizontal_coefficient=.1, vertical_coefficient=.05,
                       dead_weight_kn=1000., live_weight_kn=500.)
    cases = seismic_load_cases(model, site, ONE_CLASS_A)
    assert cases.horizontal_coefficient == .1
    assert cases.vertical_coefficient == .05
    assert cases.dead_weight_kn == pytest.approx(1000.)
    assert cases.live_weight_kn == pytest.approx(100.)
    assert sum(load[1] for load in cases["longitudinal"].nodal_loads) == pytest.approx(100.)
    assert sum(load[3] for load in cases["transverse"].nodal_loads) == pytest.approx(110.)
    assert sum(load[2] for load in cases["vertical"].nodal_loads) == pytest.approx(-55.)


def test_zero_overrides_are_not_replaced_by_automatic_values():
    model = build_bridge_model(BRIDGE)
    site = SeismicSite("IV", "II", 1., .5, 1., horizontal_coefficient=0., vertical_coefficient=0.,
                       dead_weight_kn=0., live_weight_kn=0.)
    cases = seismic_load_cases(model, site, ONE_CLASS_A)
    assert cases.horizontal_coefficient == cases.vertical_coefficient == 0.
    assert cases.dead_weight_kn == cases.live_weight_kn == 0.
    assert all(not any(load[1:]) for case in cases.values() for load in case.nodal_loads)


def test_custom_live_weight_without_traffic_has_a_defined_distribution():
    model = build_bridge_model(BRIDGE)
    site = SeismicSite("II", "I", 1., .5, 1., horizontal_coefficient=.1, dead_weight_kn=0., live_weight_kn=500.)
    cases = seismic_load_cases(model, site)
    assert sum(load[3] for load in cases["transverse"].nodal_loads) == pytest.approx(10.)
    assert cases.live_weight_kn == pytest.approx(100.)


def test_vertical_policy_can_be_requested_or_disabled_explicitly():
    assert SeismicSite("II", "I", 1., .5, 1., include_vertical=True).include_vertical
    assert not SeismicSite("IV", "I", 1., .5, 1., vertical_coefficient=.1, include_vertical=False).include_vertical


@pytest.mark.parametrize("field", ["horizontal_coefficient", "vertical_coefficient", "dead_weight_kn", "live_weight_kn"])
@pytest.mark.parametrize("value", [-1., float("nan"), float("inf")])
def test_invalid_seismic_overrides_are_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        SeismicSite("IV", "II", 1., .5, 1., **{field: value})


# the dead weight map is built once per model, never changed by the live placements or a site override
def test_seismic_dead_weight_is_built_once_per_model():
    import setu.loads.seismic_loads as loads

    model = build_bridge_model(BRIDGE)
    dead = dict(loads.dead_weight_at_nodes(model))
    built_before = loads.dead_weight_at_nodes.cache_info().misses
    for critical in (None, ONE_CLASS_A, None):
        cases = loads.seismic_load_cases(model, SITE, critical)
        assert cases["longitudinal"].nodal_loads == loads.inertia(dead, cases.horizontal_coefficient, 1, "expected").nodal_loads
    loads.seismic_load_cases(model, SeismicSite("IV", "II", 1., .5, 1., dead_weight_kn=1000.), ONE_CLASS_A)
    assert loads.dead_weight_at_nodes.cache_info().misses == built_before
    assert list(loads.dead_weight_at_nodes(model).items()) == list(dead.items())
