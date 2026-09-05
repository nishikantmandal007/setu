from setu.models.bridge import BridgeInput, DeckSlab, Girders, Bracing, MeshSettings
from setu.models.deck import DeckCrossSection
from setu.models.materials import Steel, Concrete, SurfacingLayer
from setu.models.sections import PlateGirderSection, GirderSection, girder_properties

from setu.builder.mesh import build_mesh, DeckModel
from setu.builder.assembly import build_bridge_model, BridgeModel
from setu.builder.dead_loads import apply_dead_loads

from setu.analysis.influence_surface import InfluenceSolver, InfluenceSurface
from setu.analysis.critical_position import CriticalPositionService, find_critical_position, rank_all_positions
from setu.analysis.vehicle_placement import find_worst_train

from setu.solver.backend import OpenSeesBackend

from setu.irc6.impact import impact_factor
from setu.irc6.combinations import irc6_uls_recipes, irc6_sls_recipes, irc6_fatigue_recipe, irc6_construction_recipe

from setu.postprocess.girder_response import GirderForces, GirderDeflections, girder_forces, girder_deflections
from setu.postprocess.envelope import Envelope, envelope, envelope_with_deflections
from setu.postprocess.load_cases import LoadCase, apply_load_case, combine
from setu.postprocess.load_builders import pressure_load, line_load, point_load, braking_load, seismic_load, wind_load, temperature_gradient, fatigue_moving_load


def build_result_dataset(*args, **kwargs):
    from setu.postprocess.result_dataset import build_result_dataset as _build
    return _build(*args, **kwargs)
