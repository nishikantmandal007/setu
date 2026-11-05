"""Construction stage on the bare steel (un-propped, IRC:22-2015 cl. 604.1.1), factored per IRC:6-2017 Annex B Table B.2.

Loads: steel self weight and wet slab (+1 kN/m3, Amendment 10 Table 1 note) as dead load (1.35 / 1.0), shuttering as a construction
dead load (1.35, row 2.4), construction live load (1.35 basic, 1.0 seismic, row 2.1 c), wind during construction (1.5 leading /
0.9 accompanying, row 2.2; 10-year return period, Table 1 note 1; CD = 2(1 + c / 20d) <= 4, Table 8 II(a)), seismic during
construction (0.75, row 4 b; importance factor 1, IRC:SP:114 cl. 4.5 note). Construction loads are project inputs (IRC:6 cl. 218).
"""

import pytest

from setu.builder.assembly import build_bridge_model
from setu.loads.dead_loads import bare_steel_area_load
from setu.postprocess.construction import (
    CONSTRUCTION_LIVE,
    TEMPORARY_DEAD,
    ULS_CONSTRUCTION,
    ULS_SEISMIC_DURING_CONSTRUCTION,
    ConstructionLoads,
    construction_design_values,
    construction_seismic_cases,
    construction_wind_cases,
)
from setu.postprocess.girder_response import analyze_load_case
from setu.utils.constants import BIGGER_IS_WORSE, DEAD, MAX_MOMENT, SEISMIC

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")
from setu.solver import backend  # noqa: E402

from test_design_forces import BRIDGE, SPAN_M  # noqa: E402
from test_seismic import SITE as SEISMIC_SITE  # noqa: E402
from test_wind import SITE as WIND_SITE  # noqa: E402

LOADS = ConstructionLoads(shuttering_kpa=0.5, construction_live_load_kpa=1.5)


@pytest.fixture(scope="module")
def values():
    return construction_design_values(BRIDGE, LOADS, wind=WIND_SITE, seismic=SEISMIC_SITE)


@pytest.fixture(scope="module")
def steel():
    return build_bridge_model(BRIDGE, composite=False)


def test_the_bare_steel_carries_the_whole_construction_load(steel):
    """Statics: the girders' midspan moments under a uniform 1.5 kN/m2 add up to q B L^2 / 8."""
    forces = analyze_load_case(steel, bare_steel_area_load(steel, 1.5, "construction live load"))
    midspan = steel.mesh.stations_along_span // 2
    total = sum(forces[k].moment_kn_m[midspan] for k in forces)

    assert total == pytest.approx(1.5 * BRIDGE.width_m() * SPAN_M ** 2 / 8, rel=0.005)


def test_table_b2_factors_in_the_basic_construction_combination(values, steel):
    governing = values.girders[2][MAX_MOMENT][ULS_CONSTRUCTION][BIGGER_IS_WORSE]
    station = int(abs(steel.mesh.length_mesh_m - governing.at_m).argmin())
    unfactored = analyze_load_case(steel, bare_steel_area_load(steel, 1.5, "construction live load"))[2].moment_kn_m[station]
    shuttering = analyze_load_case(steel, bare_steel_area_load(steel, 0.5, "shuttering"))[2].moment_kn_m[station]

    assert governing.shares[CONSTRUCTION_LIVE] == pytest.approx(1.35 * unfactored)
    assert governing.shares[TEMPORARY_DEAD] == pytest.approx(1.35 * shuttering)
    assert governing.value == pytest.approx(sum(governing.shares.values()))


def test_seismic_during_construction_takes_live_load_at_1_0_and_seismic_at_0_75(values, steel):
    governing = values.girders[2][MAX_MOMENT][ULS_SEISMIC_DURING_CONSTRUCTION][BIGGER_IS_WORSE]
    station = int(abs(steel.mesh.length_mesh_m - governing.at_m).argmin())
    unfactored = analyze_load_case(steel, bare_steel_area_load(steel, 1.5, "construction live load"))[2].moment_kn_m[station]

    assert governing.shares[CONSTRUCTION_LIVE] == pytest.approx(1.0 * unfactored)
    assert governing.shares[SEISMIC] > 0
    assert governing.value == pytest.approx(sum(governing.shares.values()))


def test_construction_wind_by_hand(steel):
    """Vb 39 m/s, 10 years (k1 0.83, Table 1 note 1), TC2 at 12 m (k2 1.02): Pz = 0.6 (39 x 0.83 x 1.02)^2. Area = span x (girder + slab);
    CD = 2(1 + c / 20d) with c the girder spacing and d the windward girder depth, not more than 4."""
    cases, total_kn = construction_wind_cases(steel, WIND_SITE)
    pz_kpa = 0.6 * (39 * 0.83 * 1.02) ** 2 / 1000
    depth_m = steel.girder.depth_m
    drag = min(2 * (1 + steel.mesh.girder_spacing_m / (20 * depth_m)), 4.0)

    assert total_kn == pytest.approx(pz_kpa * SPAN_M * (depth_m + BRIDGE.deck.thickness_m) * drag)
    with backend.solved(cases["from the left"].nodal_loads, cases["from the left"].element_loads, pattern=131):
        backend.calculate_reactions()
        across_kn = sum(backend.node_reaction(node, 3) for node in backend.node_tags())
    assert -across_kn == pytest.approx(total_kn, rel=1e-9)


def test_seismic_during_construction_uses_importance_factor_1(steel):
    """IRC:SP:114 cl. 4.5 note: importance factor 1 during construction, whatever the bridge's own I (1.2 here)."""
    from setu.irc6.seismic import horizontal_seismic_coefficient
    import copy
    one = copy.copy(SEISMIC_SITE)
    one.importance_factor = 1.0
    cases = construction_seismic_cases(steel, SEISMIC_SITE, [])
    total_kn = sum(load[3] for load in cases["transverse"].nodal_loads)
    weight_kn = sum(BRIDGE.steel.unit_weight_kn_m3 * steel.girders[k].area_m2 * SPAN_M for k in range(BRIDGE.girders.count))

    assert SEISMIC_SITE.importance_factor == 1.2
    assert total_kn == pytest.approx(horizontal_seismic_coefficient(one) * weight_kn, rel=1e-9)


@pytest.mark.parametrize("key", ["shuttering_kpa", "construction_live_load_kpa"])
def test_construction_loads_are_required_and_nonnegative(key):
    with pytest.raises(ValueError, match=key):
        ConstructionLoads(**{"shuttering_kpa": 0.5, "construction_live_load_kpa": 1.5, key: -1.0})


def test_explicit_seismic_coefficients_are_refused_during_construction(steel):
    import copy
    site = copy.copy(SEISMIC_SITE)
    site.horizontal_coefficient = 0.1
    with pytest.raises(ValueError, match="importance factor of 1"):
        construction_seismic_cases(steel, site, [])


def test_coefficients_worked_out_with_importance_factor_1_are_accepted(steel):
    import copy
    site = copy.copy(SEISMIC_SITE)
    site.importance_factor, site.horizontal_coefficient, site.vertical_coefficient = 1.0, 0.05, None
    cases = construction_seismic_cases(steel, site, [])
    weight_kn = sum(BRIDGE.steel.unit_weight_kn_m3 * steel.girders[k].area_m2 * SPAN_M for k in range(BRIDGE.girders.count))

    assert sum(load[3] for load in cases["transverse"].nodal_loads) == pytest.approx(0.05 * weight_kn, rel=1e-9)


def test_every_brace_member_gets_construction_values(values, steel):
    assert set(values.braces) == set(steel.brace_elements)
    for by_limit in values.braces.values():
        assert set(by_limit) == {ULS_CONSTRUCTION, ULS_SEISMIC_DURING_CONSTRUCTION}
        assert DEAD in by_limit[ULS_CONSTRUCTION][BIGGER_IS_WORSE].shares
