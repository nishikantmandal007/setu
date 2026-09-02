"""The documented, function-first public API remains importable."""
from src.models.bridge import BridgeInput
from src.rules.irc6 import impact_factor
from src.services.bridge_geometry import build_mesh
from src.services.critical_position import find_critical_position, rank_all_positions
from src.services.drawing import draw_cross_section, draw_everything
from src.services.influence_surface import InfluenceSurface
from src.services.opensees import OpenSeesBackend
from src.services.vehicle_placement import find_worst_train


def test_documented_public_api_imports():
    assert BridgeInput is not None
    assert callable(build_mesh)
    assert callable(draw_cross_section)
    assert callable(draw_everything)
    assert callable(find_critical_position)
    assert callable(find_worst_train)
    assert callable(impact_factor)
    assert InfluenceSurface is not None
    assert OpenSeesBackend is not None
    assert callable(rank_all_positions)
