# Expected runtime: ~10-15 s (solves and searches 36 brace influence surfaces across both adverse directions).
import pytest

from setu import (
    Bracing,
    BridgeInput,
    InfluenceSolver,
    TemperatureSite,
    analyze_load_case,
    brace_design_values,
    brace_forces,
    build_bridge_model,
    live_load,
)
from setu.analysis.influence_surface import response_to_load_case
from setu.analysis.results import CriticalPosition, VehiclePlacement
from setu.helpers import adverse_sign
from setu.irc6.impact import impact_factor
from setu.loads.load_cases import LoadCase
from setu.utils.constants import (
    BASIC,
    BIGGER_IS_WORSE,
    FREQUENT,
    QUASI_PERMANENT,
    RARE,
    SEISMIC_COMBINATION,
    SMALLER_IS_WORSE,
)

backend = pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")

from test_bearings import bearing_bridge  # noqa: E402
from test_design_forces import BRIDGE  # noqa: E402
from test_seismic import SITE as SEISMIC_SITE  # noqa: E402
from test_wind import SITE as WIND_SITE  # noqa: E402

RECIPROCITY_REL_TOLERANCE = 1e-6
TRAFFIC_SEARCH_REL_TOLERANCE = 0.005
ZERO_FORCE_ABS_TOLERANCE_KN = 1e-9
LIVE_REPLAY_ABS_TOLERANCE_KN = 1e-3
ROLES_BY_ARRANGEMENT = {
    "XT": ("diagonal_down", "diagonal_up", "top_chord"),
    "KT": ("k_top_left", "k_bottom_left", "top_chord"),
}
MIRROR_ROLE = {
    "diagonal_down": "diagonal_up",
    "diagonal_up": "diagonal_down",
    "top_chord": "top_chord",
}
BRACE_BRIDGE = BridgeInput(**{**vars(BRIDGE), "bracing": Bracing(station_count=3, area_m2=0.01, arrangement="XT")})
CHECKED_BRACE = (0, 1, "diagonal_down")
HAND_PLACED_CLASS_A = (
    ((3.10, 5.0),),
    ((5.30, 10.0), (8.20, 10.0)),
    ((10.40, 15.0),),
)


# run brace_design_values once with wind and seismic active
@pytest.fixture(scope="module")
def results():
    return brace_design_values(BRACE_BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE)


# every float and label of a design value tree, in a fixed order
def flattened(values):
    if isinstance(values, dict):
        return [(str(key), *flattened(values[key])) for key in sorted(values, key=str)]
    return [(values.value, values.combination, values.adverse, values.at_m)]


# one shared analysis gives exactly what the two separate runs give, solving the dead load stages once
def test_bridge_design_values_share_one_analysis(monkeypatch, results):
    import setu.postprocess.design_values as design_values
    from setu import bridge_design_values, girder_design_values

    temperature = TemperatureSite(shade_max_c=45.0, shade_min_c=2.0)
    alone = girder_design_values(BRACE_BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE, temperature=temperature, workers=1)
    solved = []
    dead_load_forces = design_values.dead_load_forces
    monkeypatch.setattr(design_values, "dead_load_forces", lambda bridge: solved.append(bridge) or dead_load_forces(bridge))
    both = bridge_design_values(BRACE_BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE, temperature=temperature, workers=1)
    assert len(solved) == 1
    assert flattened(both.girders.girders) == flattened(alone.girders)
    assert flattened(both.braces.members) == flattened(results.members)


# build a legal Class A CriticalPosition from (z_centre_m, x_front_m) pairs
def _hand_placed_class_a(placements, adverse):
    impact = impact_factor("Class_A", BRACE_BRIDGE.span_m)
    vehicles = [
        VehiclePlacement("Class_A", z_centre_m=z_m, x_front_m=x_m, impact_factor=impact, train_x_front_m=(x_m,))
        for z_m, x_m in placements
    ]
    return CriticalPosition(
        "hand placed Class A",
        adverse,
        0.0,
        0.0,
        1.0,
        len(vehicles),
        " + ".join(["class_a"] * len(vehicles)),
        vehicles,
        0.0,
        [],
        [],
        BRACE_BRIDGE.wearing_course_thickness_m,
    )


# reciprocity check for diagonals and chords at end and interior stations on X and K bridges
@pytest.mark.parametrize("arrangement", ["XT", "KT"])
def test_brace_axial_influence_surface_matches_direct_solve_by_reciprocity(arrangement):
    model = build_bridge_model(bearing_bridge(arrangement))
    solver = InfluenceSolver(model.as_deck_model())
    interior_station = model.bridge.bracing.station_count // 2
    keys = [(0, station, role) for station in (0, interior_station) for role in ROLES_BY_ARRANGEMENT[arrangement]]
    surfaces = {key: solver.for_brace_axial(f"brace {key}", model.brace_elements[key]) for key in keys}
    midspan = model.mesh.stations_along_span // 2
    quarter = model.mesh.stations_along_span // 4
    load_case = LoadCase(
        "deck point loads",
        nodal_loads=[
            (model.deck_nodes[0, 2], 0.0, -75.0, 0.0, 0.0, 0.0, 0.0),
            (model.deck_nodes[1, 4], 0.0, -90.0, 0.0, 0.0, 0.0, 0.0),
            (model.deck_nodes[quarter, 6], 0.0, -110.0, 0.0, 0.0, 0.0, 0.0),
            (model.deck_nodes[midspan, 3], 0.0, -150.0, 0.0, 0.0, 0.0, 0.0),
        ],
    )

    analyze_load_case(model, load_case)
    solved = brace_forces(model)

    assert max(abs(solved[key]) for key in keys) > 1e-2
    for key in keys:
        predicted = response_to_load_case(surfaces[key], load_case)
        assert predicted == pytest.approx(solved[key], rel=RECIPROCITY_REL_TOLERANCE, abs=ZERO_FORCE_ABS_TOLERANCE_KN)


# searched critical traffic is at least as adverse as three hand-placed legal Class A positions
@pytest.mark.parametrize("adverse", [BIGGER_IS_WORSE, SMALLER_IS_WORSE])
def test_searched_critical_position_beats_hand_placed_class_a(results, adverse):
    model = build_bridge_model(BRACE_BRIDGE)
    critical = results.criticals[(*CHECKED_BRACE, adverse)]
    surface = results.surfaces[CHECKED_BRACE]

    analyze_load_case(model, live_load(model, critical, surface))
    replayed_kn = brace_forces(model)[CHECKED_BRACE]
    assert replayed_kn == pytest.approx(critical.response, rel=RECIPROCITY_REL_TOLERANCE, abs=LIVE_REPLAY_ABS_TOLERANCE_KN)

    for placements in HAND_PLACED_CLASS_A:
        hand_case = live_load(model, _hand_placed_class_a(placements, adverse), surface)
        analyze_load_case(model, hand_case)
        hand_kn = brace_forces(model)[CHECKED_BRACE]
        assert adverse_sign(adverse) * critical.response >= adverse_sign(adverse) * hand_kn


# every governing brace value equals the sum of its factored group shares and matches its named combination
def test_every_governing_value_equals_the_sum_of_its_shares(results):
    expected_limit_states = {BASIC, SEISMIC_COMBINATION, RARE, FREQUENT, QUASI_PERMANENT}
    for member, by_limit in results.members.items():
        assert set(by_limit) >= expected_limit_states
        for by_direction in by_limit.values():
            assert set(by_direction) == {BIGGER_IS_WORSE, SMALLER_IS_WORSE}
            for adverse, governing in by_direction.items():
                assert governing.value == pytest.approx(sum(governing.shares.values()))
                selected = results.combinations[member][governing.combination][adverse]
                assert selected.to_dict() == governing.to_dict()
        for by_direction in results.combinations[member].values():
            for value in by_direction.values():
                assert value.value == pytest.approx(sum(value.shares.values()))


# mirror-image braces on a symmetric bridge get equal governing design values
def test_symmetric_bridge_gives_mirror_braces_equal_governing_values(results):
    last_pair = BRACE_BRIDGE.girders.count - 2
    for (pair, station, role), by_limit in results.members.items():
        mirror = (last_pair - pair, station, MIRROR_ROLE[role])
        for limit_state, by_direction in by_limit.items():
            # Transverse traffic positions are sampled on a grid that is not mirror-symmetric across the carriageway.
            rel_tolerance = RECIPROCITY_REL_TOLERANCE if limit_state == QUASI_PERMANENT else TRAFFIC_SEARCH_REL_TOLERANCE
            for adverse, governing in by_direction.items():
                mirror_governing = results.members[mirror][limit_state][adverse]
                assert governing.value == pytest.approx(mirror_governing.value, rel=rel_tolerance, abs=ZERO_FORCE_ABS_TOLERANCE_KN)


# member keys match brace_forces keys and criticals cover both directions of every member
def test_brace_design_values_keys_match_brace_forces_keys(results):
    model = build_bridge_model(BRACE_BRIDGE)
    load_case = LoadCase("unit point", nodal_loads=[(model.deck_nodes[0, 0], 0.0, -1.0, 0.0, 0.0, 0.0, 0.0)])
    analyze_load_case(model, load_case)
    direct_keys = set(brace_forces(model).keys())

    assert set(results.members.keys()) == direct_keys
    assert set(results.criticals.keys()) == {(*key, adverse) for key in direct_keys for adverse in (BIGGER_IS_WORSE, SMALLER_IS_WORSE)}
