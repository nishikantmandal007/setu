# Expected runtime: ~6 s (one shared bridge run with wind and seismic, then every governing combination solved along the girders).
import pytest

from setu import bridge_design_values
from setu.utils.constants import BEARING_REACTION, MAX_MOMENT, SUPPORT_SHEAR

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")

from test_brace_design_values import BRACE_BRIDGE, LIVE_REPLAY_ABS_TOLERANCE_KN, RECIPROCITY_REL_TOLERANCE  # noqa: E402
from test_seismic import SITE as SEISMIC_SITE  # noqa: E402
from test_wind import SITE as WIND_SITE  # noqa: E402

LIVE_MOMENT_REPLAY_ABS_TOLERANCE_KN_M = 0.01  # a footway patch solved as nodal loads and integrated off the surface differ by a few N·m


# one shared run with every load group active
@pytest.fixture(scope="module")
def values():
    return bridge_design_values(BRACE_BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE)


# the response a design value reads, off one girder's solved forces at one station
def response_at(forces, response, station):
    if response == MAX_MOMENT:
        return forces.composite_moment_kn_m[station]
    if response == SUPPORT_SHEAR:
        return forces.shear_kn[station]
    return forces.reaction_kn if station == 0 else forces.end_reaction_kn


# every governing girder value, solved as real loads along the span, gives back its design value where it governs
def test_every_governing_diagram_reproduces_its_design_value(values):
    governing = values.diagrams.governing
    assert {key[:2] for key in governing} == {(girder, response) for girder in range(BRACE_BRIDGE.girders.count)
                                              for response in (MAX_MOMENT, SUPPORT_SHEAR, BEARING_REACTION)}
    for (girder, response, limit_state, adverse), diagram in governing.items():
        assert diagram.governing is values.girders.girders[girder][response][limit_state][adverse]
        forces = diagram.forces[girder]
        station = list(forces.stations_m).index(diagram.governing.at_m)
        assert response_at(forces, response, station) == pytest.approx(
            diagram.governing.value, rel=RECIPROCITY_REL_TOLERANCE, abs=LIVE_REPLAY_ABS_TOLERANCE_KN)


# each critical live arrangement solved along the span gives back the live response it was found for
def test_every_live_arrangement_reproduces_its_critical_response(values):
    for (girder, response, adverse), forces in values.diagrams.live.items():
        if response not in (MAX_MOMENT, SUPPORT_SHEAR):
            continue
        station = values.girders.stations[girder, response, adverse]
        critical = values.girders.criticals[girder, response, adverse]
        assert response_at(forces[girder], response, station) == pytest.approx(
            critical.response, rel=RECIPROCITY_REL_TOLERANCE, abs=LIVE_MOMENT_REPLAY_ABS_TOLERANCE_KN_M)


# the plan positions follow the girder lines and deck edges station by station
def test_plan_positions_follow_the_mesh(values):
    diagrams = values.diagrams
    stations = len(values.girders.dead.stages["steel self weight"][0].stations_m)
    assert sorted(diagrams.girder_positions_m) == list(range(BRACE_BRIDGE.girders.count))
    across = [positions[0][1] for positions in (diagrams.edge_positions_m["left"], *diagrams.girder_positions_m.values(),
                                                 diagrams.edge_positions_m["right"])]
    assert across == sorted(across) and across[0] == 0.0 and across[-1] == pytest.approx(BRACE_BRIDGE.width_m())
    assert all(len(positions) == stations for positions in (*diagrams.girder_positions_m.values(), *diagrams.edge_positions_m.values()))
