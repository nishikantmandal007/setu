from setu.models.bridge import BridgeInput
from setu.rules.irc6 import impact_factor
from setu.builder.mesh import build_mesh
from setu.services.critical_position import find_critical_position, rank_all_positions
from setu.services.influence_surface import InfluenceSurface
from setu.services.opensees import OpenSeesBackend
from setu.services.vehicle_placement import find_worst_train
from setu.services.girder_response import GirderForces, GirderDeflections
from setu.services.load_cases import LoadCase
from setu.services.envelope import Envelope
from setu.services.load_builders import pressure_load, line_load, point_load


def test_documented_public_api_imports():
    assert BridgeInput is not None
    assert callable(build_mesh)
    assert callable(find_critical_position)
    assert callable(find_worst_train)
    assert callable(impact_factor)
    assert InfluenceSurface is not None
    assert OpenSeesBackend is not None
    assert callable(rank_all_positions)
    assert GirderForces is not None
    assert GirderDeflections is not None
    assert LoadCase is not None
    assert Envelope is not None
    assert callable(pressure_load)
    assert callable(line_load)
    assert callable(point_load)
