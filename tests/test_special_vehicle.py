"""Class SV, IRC:6-2017 cl. 204.5 with Amendment 10 (3850 kN, Fig. 6 with 5427 mm; required for new bridges, cl. 201.1).

Fig. 6A: 8 tyres an axle at 403, 647, 1153, 1397 mm either side of the centreline. 204.5.3: centreline within 300 mm of the
carriageway centreline. 204.5.4: no other live load or footway load on its carriageway, no impact or braking on it; SV factor 1.15 ULS
basic, 1.0 SLS rare, 0.75 SLS frequent. Fig. 6B case 4: on a dual carriageway the other carriageway keeps its traffic.
"""

import numpy as np
import pytest

from setu.analysis.special_vehicle import special_vehicle_offsets, special_vehicle_on_each_carriageway, without_the_special_vehicle_carriageway
from setu.builder.assembly import build_bridge_model
from setu.helpers import DEFAULT_SAMPLING
from setu.loads.load_builders import as_a_load_case, share_between_nodes
from setu.models.bridge import AddedDeadLoads, BridgeInput
from setu.models.deck import DeckCrossSection
from setu.postprocess.girder_response import analyze_load_case
from setu.postprocess.special_vehicle import SPECIAL_VEHICLE, special_vehicle_design_values
from setu.utils.constants import BASIC, BIGGER_IS_WORSE, FREQUENT, LIVE, MAX_MOMENT, RARE

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")

from test_design_forces import BRIDGE, CROSS_SECTION, SPAN_M  # noqa: E402
from test_golden_values import sagging_surface  # noqa: E402

SINGLE = DeckCrossSection.from_widths({"footpath_left": 1.5, "kerb_left": 0.45, "carriageway_1": 7.5, "kerb_right": 0.45, "footpath_right": 1.5})
NO_MEDIAN = AddedDeadLoads(footpath_kpa=3.6, kerb_kn_per_m=3.24, median_kn_per_m=0.0, crash_barrier_kn_per_m=0.0, railing_kn_per_m=0.0)


def test_the_vehicle_is_fig_6_and_6a():
    offsets = special_vehicle_offsets()
    axles = sorted({round(float(dx), 6) for dx in offsets[:, 0]})

    assert offsets[:, 2].sum() == pytest.approx(3850.0)
    assert len(offsets) == 23 * 8
    assert axles[:4] == pytest.approx([0.0, 3.2, 4.57, 9.997])
    assert axles[-1] - axles[3] == pytest.approx(28.5)
    assert sorted({round(abs(float(dz)), 3) for dz in offsets[:, 1]}) == [0.403, 0.647, 1.153, 1.397]
    assert set(np.round(offsets[3 * 8:, 2], 6)) == {22.5}


def test_the_sv_stays_within_300_mm_of_the_carriageway_centreline():
    for found in special_vehicle_on_each_carriageway(sagging_surface(), CROSS_SECTION, BIGGER_IS_WORSE, DEFAULT_SAMPLING):
        carriageway = CROSS_SECTION.carriageways()[found.carriageway]
        assert abs(found.z_centre_m - (carriageway.left_m + carriageway.right_m) / 2) <= 0.300 + 1e-9


def test_its_carriageway_and_the_footways_beside_it_take_nothing_else():
    others = without_the_special_vehicle_carriageway(CROSS_SECTION, 0)

    assert len(others.carriageways()) == 1
    assert others.carriageways()[0].left_m == pytest.approx(CROSS_SECTION.carriageways()[1].left_m)
    assert [s.name for s in others.footways()] == ["footpath_right"]
    assert not without_the_special_vehicle_carriageway(SINGLE, 0).carriageways()
    assert not without_the_special_vehicle_carriageway(SINGLE, 0).footways()


def test_statics_the_girders_carry_the_whole_vehicle():
    """SV centred at midspan on the first carriageway: the girders' midspan moments add up to the moment of the axle loads on a
    simply supported 35 m span (no impact)."""
    model = build_bridge_model(BRIDGE)
    offsets = special_vehicle_offsets()
    front_m = SPAN_M / 2 - 19.0
    z_m = sum((CROSS_SECTION.carriageways()[0].left_m, CROSS_SECTION.carriageways()[0].right_m)) / 2
    nodal = {}
    for dx, dz, load in offsets:
        share_between_nodes(model, front_m + dx, z_m + dz, load, nodal)
    forces = analyze_load_case(model, as_a_load_case(model, nodal, "SV"))
    midspan = model.mesh.stations_along_span // 2
    x_mid = model.mesh.length_mesh_m[midspan]
    on_span = [(front_m + dx, load) for dx, _, load in offsets if 0.0 <= front_m + dx <= SPAN_M]
    left_reaction = sum(load * (SPAN_M - x) for x, load in on_span) / SPAN_M
    by_hand = left_reaction * x_mid - sum(load * (x_mid - x) for x, load in on_span if x < x_mid)

    assert sum(forces[k].composite_moment_kn_m[midspan] for k in forces) == pytest.approx(by_hand, rel=0.01)


@pytest.fixture(scope="module")
def dual():
    return special_vehicle_design_values(BRIDGE)


def test_factors_of_204_5_4(dual):
    for limit_state, factor in ((BASIC, 1.15), (RARE, 1.0), (FREQUENT, 0.75)):
        governing = dual.girders[0][MAX_MOMENT][limit_state][BIGGER_IS_WORSE]
        assert governing.value == pytest.approx(sum(governing.shares.values()))
        assert SPECIAL_VEHICLE in governing.shares and governing.combination.endswith("special vehicle leading")
    basic = dual.girders[0][MAX_MOMENT][BASIC][BIGGER_IS_WORSE].shares[SPECIAL_VEHICLE]
    rare = dual.girders[0][MAX_MOMENT][RARE][BIGGER_IS_WORSE].shares[SPECIAL_VEHICLE]
    assert basic / rare == pytest.approx(1.15)


def test_on_a_dual_carriageway_the_other_carriageway_keeps_its_traffic(dual):
    assert dual.girders[2][MAX_MOMENT][BASIC][BIGGER_IS_WORSE].shares[LIVE] > 0


def test_on_a_single_carriageway_nothing_else_rides_with_it():
    single = BridgeInput(**{**vars(BRIDGE), "cross_section": SINGLE, "added_dead_loads": NO_MEDIAN})
    values = special_vehicle_design_values(single)

    for by_limit in values.girders[2].values():
        for by_direction in by_limit.values():
            for governing in by_direction.values():
                assert governing.shares.get(LIVE, 0.0) == 0.0


def test_no_impact_on_the_special_vehicle(dual):
    """The SV share at ULS is 1.15 x the bare influence-surface response: no cl. 208 factor."""
    model = build_bridge_model(BRIDGE)
    from setu.analysis.influence_surface import InfluenceSolver
    from setu.postprocess.design_values import surface_for
    governing = dual.girders[0][MAX_MOMENT][BASIC][BIGGER_IS_WORSE]
    station = int(abs(model.mesh.length_mesh_m - governing.at_m).argmin())
    surface = surface_for(InfluenceSolver(model.as_deck_model()), model, 0, (MAX_MOMENT, station))
    bare = max(found.response for found in special_vehicle_on_each_carriageway(surface, CROSS_SECTION, BIGGER_IS_WORSE, DEFAULT_SAMPLING))

    assert governing.shares[SPECIAL_VEHICLE] == pytest.approx(1.15 * bare, rel=1e-9)
