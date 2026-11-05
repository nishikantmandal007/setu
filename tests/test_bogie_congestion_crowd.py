"""70R maximum single axle and bogie (Fig. 1 note 3), congestion (cl. 204.4, Table 7) and crowd load (cl. 206.1, 206.3), IRC:6-2017 with
Amendment 10.

Fig. 1 note 3: 'maximum loads for the wheeled vehicle shall be 200 kN for a single axle or 400 kN for a bogie of two axles spaced not
more than 1.22 m centres'. 204.4: Table 7 factor on the longitudinal (vertical) effect of vehicular live load after impact; the cl. 205
reduction still applies; no braking, centrifugal, thermal or eccentricity effects; not with SV. 206.1: footways 5 kN/m2 where crowd load
is likely, and the entire carriageway occupied by crowd load; 206.3: no span reduction when crowd load is considered.
"""

import copy

import pytest

from setu.analysis.critical_position import congested, find_critical_position, rank_all_positions
from setu.irc6.braking import design_lanes_of
from setu.irc6.impact import impact_fraction
from setu.irc6.lanes import congestion_factor, footway_loaded_strips
from setu.irc6.vehicles import IRC_VEHICLES
from setu.models.deck import DeckCrossSection
from setu.utils.constants import BIGGER_IS_WORSE

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")

from test_design_forces import CROSS_SECTION, SPAN_M  # noqa: E402
from test_golden_values import sagging_surface  # noqa: E402

WIDTHS = {"footpath_left": 1.5, "kerb_left": 0.45, "carriageway_1": 7.5, "kerb_right": 0.45, "footpath_right": 1.5}


@pytest.mark.parametrize("span_m, factor", [(10.5, 1.15), (30.0, 1.15), (35.0, 1.225), (40.0, 1.30), (55.0, 1.525), (70.0, 1.70), (90.0, 1.70)])
def test_table_7(span_m, factor):
    assert congestion_factor(span_m) == pytest.approx(factor)


def test_table_7_starts_above_10_m():
    with pytest.raises(ValueError, match="above 10 m"):
        congestion_factor(10.0)


def test_bogie_and_single_axle_are_wheeled_70r():
    """Wheeled 70R impact (not tracked) and two design lanes for braking, like the 70R wheeled."""
    for name in ("Class_70R_Bogie", "Class_70R_Single_Axle"):
        assert impact_fraction(name, SPAN_M) == pytest.approx(impact_fraction("Class_70R_Wheeled", SPAN_M)) != impact_fraction("Class_70R_Tracked", SPAN_M)
        placed = type("Placed", (), {"vehicle_name": name})()
        assert design_lanes_of(placed) == 2


def test_the_bogie_and_single_axle_are_offered_in_every_70r_zone():
    from setu.irc6.vehicles import vehicles_allowed_in_each_block
    names = {v.name.split(" ")[0] for v in vehicles_allowed_in_each_block()["zone_70r"]}
    assert {"Class_70R_Bogie", "Class_70R_Single_Axle"} <= {n for n in IRC_VEHICLES if any(x.startswith(n) for x in names)}


def test_congestion_scales_only_the_vehicles_and_drops_braking():
    plain = find_critical_position(sagging_surface(), CROSS_SECTION, SPAN_M, BIGGER_IS_WORSE, 0.065)
    twin = congested(plain, 1.225)
    footway = plain.footway_response * plain.lane_reduction

    assert twin.response == pytest.approx(1.225 * (plain.response - footway) + footway)
    assert twin.lane_reduction == plain.lane_reduction
    assert not twin.takes_braking and plain.takes_braking


def test_congestion_competes_in_the_search_when_the_authority_asks():
    crowded = copy.copy(CROSS_SECTION)
    crowded.congestion = True
    worst = find_critical_position(sagging_surface(), crowded, SPAN_M, BIGGER_IS_WORSE, 0.065)
    plain = find_critical_position(sagging_surface(), CROSS_SECTION, SPAN_M, BIGGER_IS_WORSE, 0.065)

    assert "congested" in worst.lane_pattern
    assert worst.response > plain.response


def test_crowd_load_puts_5_kpa_on_footways_without_the_span_reduction():
    normal = DeckCrossSection.from_widths(WIDTHS)
    crowd = DeckCrossSection.from_widths(WIDTHS, crowd_load=True)

    assert all(p < 4.0 for _, _, p in footway_loaded_strips(normal, SPAN_M))
    assert all(p == 5.0 for _, _, p in footway_loaded_strips(crowd, SPAN_M))


def test_crowd_on_the_whole_deck_is_a_case_of_its_own():
    """206.1: the entire carriageway occupied by crowd load; the case equals 5 kN/m2 times the adverse influence volume over the
    carriageways and footways."""
    crowd = copy.copy(CROSS_SECTION)
    crowd.crowd_load = True
    ranked = rank_all_positions(sagging_surface(), crowd, SPAN_M, BIGGER_IS_WORSE, 0.065)
    whole = next(p for p in ranked if "crowd load on the whole deck" in p.lane_pattern)

    assert not whole.vehicles and not whole.takes_braking
    from setu.helpers import DEFAULT_SAMPLING
    from setu.irc6.lanes import footway_live_load_strips, response_to_area_load
    strips = [(c.left_m, c.right_m) for c in crowd.carriageways()] + [(s.z_from_m, s.z_to_m) for s in footway_live_load_strips(crowd)]
    assert whole.response == pytest.approx(response_to_area_load(sagging_surface().along_the_mesh(), strips, BIGGER_IS_WORSE, 5.0, DEFAULT_SAMPLING))


def test_a_congested_placement_replays_with_its_factor():
    """The loads solved for the plots and the CSV export carry the Table 7 factor on wheels and residual UDL, not on the footway, so the
    replay gives back the congested design value."""
    from setu.builder.assembly import build_bridge_model
    from setu.loads.load_builders import applied_live_loads, live_load
    from test_design_forces import BRIDGE
    surface = sagging_surface()
    plain = find_critical_position(surface, CROSS_SECTION, SPAN_M, BIGGER_IS_WORSE, 0.065)
    twin = congested(plain, 1.225)
    model = build_bridge_model(BRIDGE)
    (plain_wheels, plain_patches), (twin_wheels, twin_patches) = (applied_live_loads(model.bridge, p, surface) for p in (plain, twin))

    assert [w["applied_kn"] for w in twin_wheels] == pytest.approx([1.225 * w["applied_kn"] for w in plain_wheels])
    for a, b in zip(plain_patches, twin_patches, strict=True):
        assert b["pressure_kpa"] == pytest.approx(a["pressure_kpa"] * (1.225 if a["kind"] != "footway" else 1.0))
    total = lambda p: -sum(fy for _, _, fy, *_ in live_load(model, p, surface).nodal_loads)
    footway_kn = sum(r["pressure_kpa"] * (r["along_to_m"] - r["along_from_m"]) * (r["z_to_m"] - r["z_from_m"]) for r in plain_patches if r["kind"] == "footway")
    assert total(twin) == pytest.approx(1.225 * (total(plain) - footway_kn) + footway_kn, rel=1e-6)
