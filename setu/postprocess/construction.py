import copy
import math

from setu.builder.assembly import build_bridge_model, girder_centroid_level_m
from setu.builder.mesh import tributary_length_m
from setu.helpers import adverse_sign
from setu.irc6.combinations import Combination, design_value
from setu.irc6.irc_constants import (
    CONSTRUCTION_DEAD_FACTORS,
    CONSTRUCTION_IMPORTANCE_FACTOR,
    CONSTRUCTION_LIVE_LOAD_FACTOR_BASIC,
    CONSTRUCTION_LIVE_LOAD_FACTOR_SEISMIC,
    CONSTRUCTION_RETURN_PERIOD_YEARS,
    CONSTRUCTION_TEMPORARY_DEAD_FACTOR_BASIC,
    CONSTRUCTION_TEMPORARY_DEAD_FACTOR_SEISMIC,
    CONSTRUCTION_WIND_FACTORS,
    SEISMIC_DURING_CONSTRUCTION_FACTOR,
)
from setu.irc6.seismic import combine_directions, horizontal_seismic_coefficient, vertical_seismic_coefficient
from setu.irc6.wind import check_scope, construction_drag_coefficient, design_wind_speed_mps, wind_pressure_pa
from setu.loads.dead_loads import bare_steel_area_load, bracing_weight_at_its_ends, steel_self_weight_load, wet_slab_load
from setu.loads.load_cases import LoadCase
from setu.loads.seismic_loads import inertia
from setu.postprocess.design_values import BOTH_DIRECTIONS, GoverningValue, places_to_design, reader
from setu.postprocess.girder_response import analyze_load_case, brace_forces
from setu.utils.constants import DEAD, KPA_PER_PA, RESPONSES, SEISMIC, WIND

CONSTRUCTION_LIVE = "construction live load"
TEMPORARY_DEAD = "shuttering"
ULS_CONSTRUCTION = "ultimate, construction"
ULS_SEISMIC_DURING_CONSTRUCTION = "ultimate, seismic during construction"
NOT_WHEN_RELIEVING = 0.0
WIND_FROM = {"from the left": 1.0, "from the right": -1.0}


class ConstructionLoads:
    # the project's construction loads on the bare steel while the slab is cast (IRC:6 cl. 218, IRC:22 cl. 604.1.1): IRC gives no values,
    # so both are required inputs in kN/m2 over the deck width (0 when the construction programme has none)
    def __init__(self, shuttering_kpa, construction_live_load_kpa):
        for name, value in (("shuttering_kpa", shuttering_kpa), ("construction_live_load_kpa", construction_live_load_kpa)):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative (from the construction programme, IRC:6 cl. 218), got {value}")
        self.shuttering_kpa = shuttering_kpa
        self.construction_live_load_kpa = construction_live_load_kpa


class ConstructionValues:
    # governing construction-stage design values: girders by girder, response and limit state; braces by member and limit state
    def __init__(self, girders, braces, combinations):
        self.girders = girders
        self.braces = braces
        self.combinations = combinations


# Table B.2 construction combinations: wind leading or accompanying the construction live load, and seismic during construction
def construction_combinations(with_wind, with_seismic):
    dead = {DEAD: CONSTRUCTION_DEAD_FACTORS, TEMPORARY_DEAD: (CONSTRUCTION_TEMPORARY_DEAD_FACTOR_BASIC, CONSTRUCTION_TEMPORARY_DEAD_FACTOR_BASIC),
            CONSTRUCTION_LIVE: (CONSTRUCTION_LIVE_LOAD_FACTOR_BASIC, NOT_WHEN_RELIEVING)}
    combinations = [Combination(f"{ULS_CONSTRUCTION}, construction live load leading", ULS_CONSTRUCTION,
                                {**dead, **({WIND: (CONSTRUCTION_WIND_FACTORS[1], NOT_WHEN_RELIEVING)} if with_wind else {})})]
    if with_wind:
        combinations.append(Combination(f"{ULS_CONSTRUCTION}, wind leading", ULS_CONSTRUCTION, {**dead, WIND: (CONSTRUCTION_WIND_FACTORS[0], NOT_WHEN_RELIEVING)}))
    if with_seismic:
        combinations.append(Combination(ULS_SEISMIC_DURING_CONSTRUCTION, ULS_SEISMIC_DURING_CONSTRUCTION,
                                        {DEAD: CONSTRUCTION_DEAD_FACTORS,
                                         TEMPORARY_DEAD: (CONSTRUCTION_TEMPORARY_DEAD_FACTOR_SEISMIC, CONSTRUCTION_TEMPORARY_DEAD_FACTOR_SEISMIC),
                                         CONSTRUCTION_LIVE: (CONSTRUCTION_LIVE_LOAD_FACTOR_SEISMIC, NOT_WHEN_RELIEVING),
                                         SEISMIC: (SEISMIC_DURING_CONSTRUCTION_FACTOR, NOT_WHEN_RELIEVING)}))
    return combinations


# 209.5.2.2 (c) and Table 8 II(a): wind on the bare steel while the slab is cast, 10-year return period (Table 1 note 1), on the windward
# girder's unshielded solid area (girder depth plus the slab being cast) with CD = 2(1 + c / 20d) <= 4, at the area's centroid
def construction_wind_cases(model, site):
    bridge = model.bridge
    check_scope(bridge.span_m, site.pier_height_m)
    girder = model.girders[0]
    if any(other.depth_m != girder.depth_m for other in model.girders[1:]):
        raise ValueError("construction wind needs girders of one depth: Table 8 II(a) takes d as the windward girder depth")
    exposed_depth_m = girder.depth_m + bridge.deck.thickness_m
    drag = construction_drag_coefficient(bridge.girders.count, model.mesh.girder_spacing_m, girder.depth_m)
    pressure_kpa = wind_pressure_pa(design_wind_speed_mps(site, site.superstructure_top_m, CONSTRUCTION_RETURN_PERIOD_YEARS)) * KPA_PER_PA
    total_kn = pressure_kpa * bridge.span_m * exposed_depth_m * drag
    centroid_level_m = girder_centroid_level_m(bridge, girder)
    bottom_level_m = centroid_level_m - girder.neutral_axis_from_bottom_m
    arm_m = bottom_level_m + exposed_depth_m / 2 - centroid_level_m
    cases = {}
    for side, sign in WIND_FROM.items():
        windward = 0 if sign > 0 else bridge.girders.count - 1
        nodal_loads = []
        for i in range(model.mesh.stations_along_span):
            force_kn = sign * total_kn * tributary_length_m(model.mesh.length_mesh_m, i) / bridge.span_m
            nodal_loads.append((model.girder_nodes[windward, i], 0.0, 0.0, force_kn, arm_m * force_kn, 0.0, 0.0))
        cases[side] = LoadCase(name=f"construction wind, {side}", nodal_loads=nodal_loads)
    return cases, total_kn


# inertia of the construction dead weight (steel, wet slab, shuttering) on the bare steel, importance factor 1 (SP:114 cl. 4.5 note)
def construction_seismic_cases(model, site, weight_cases):
    if site.horizontal_coefficient is not None or site.vertical_coefficient is not None:
        raise ValueError("seismic during construction needs the importance factor of 1 (IRC:SP:114 cl. 4.5); "
                         "explicit seismic coefficients already include an importance factor, so supply the zone, soil, T and R instead")
    construction_site = copy.copy(site)
    construction_site.importance_factor = CONSTRUCTION_IMPORTANCE_FACTOR
    weights_kn = {}
    for case in weight_cases:
        for node, _, fy, *_ in case.nodal_loads:
            weights_kn[node] = weights_kn.get(node, 0.0) - fy
    bridge = model.bridge
    for (k, i), node in model.girder_nodes.items():
        weights_kn[node] = weights_kn.get(node, 0.0) + bridge.steel.unit_weight_kn_m3 * model.girders[k].area_m2 * tributary_length_m(model.mesh.length_mesh_m, i)
    ah = horizontal_seismic_coefficient(construction_site)
    cases = {"longitudinal": inertia(weights_kn, ah, 1, "seismic during construction, longitudinal"),
             "transverse": inertia(weights_kn, ah, 3, "seismic during construction, transverse")}
    if construction_site.include_vertical:
        cases["vertical"] = inertia(weights_kn, -vertical_seismic_coefficient(construction_site), 2, "seismic during construction, vertical")
    return cases


# construction-stage ULS design values for every girder place and brace member, on the bare steel
def construction_design_values(bridge, loads, wind=None, seismic=None):
    steel = build_bridge_model(bridge, composite=False)
    self_weight = steel_self_weight_load(steel)
    wet_slab = wet_slab_load(steel)
    shuttering = bare_steel_area_load(steel, loads.shuttering_kpa, "shuttering")
    construction_live = bare_steel_area_load(steel, loads.construction_live_load_kpa, "construction live load")
    named = {"steel self weight": self_weight, "wet slab": wet_slab, TEMPORARY_DEAD: shuttering, CONSTRUCTION_LIVE: construction_live}
    wind_cases = {}
    if wind is not None:
        wind_cases, _ = construction_wind_cases(steel, wind)
        named.update({f"wind {side}": case for side, case in wind_cases.items()})
    seismic_cases = construction_seismic_cases(steel, seismic, [wet_slab, shuttering, LoadCase("bracing", [(node, 0.0, -kn, 0.0, 0.0, 0.0, 0.0) for node, kn in bracing_weight_at_its_ends(steel)])]) if seismic is not None else {}
    named.update({f"seismic {name}": case for name, case in seismic_cases.items()})
    girder_forces, member_forces = {}, {}
    for name, case in named.items():
        girder_forces[name] = analyze_load_case(steel, case)
        member_forces[name] = brace_forces(steel)
    combinations = construction_combinations(bool(wind_cases), bool(seismic_cases))
    read = reader({})

    def effects_at(read_one):
        effects = {DEAD: read_one("steel self weight") + read_one("wet slab"), TEMPORARY_DEAD: read_one(TEMPORARY_DEAD), CONSTRUCTION_LIVE: read_one(CONSTRUCTION_LIVE)}
        if wind_cases:
            effects[WIND] = [read_one(f"wind {side}") for side in WIND_FROM]
        if seismic_cases:
            effects[SEISMIC] = combine_directions(*[read_one(f"seismic {name}") for name in ("longitudinal", "transverse", "vertical") if name in seismic_cases])
        return effects

    girders = {}
    for girder in range(bridge.girders.count):
        girders[girder] = {response: {} for response in RESPONSES}
        for place in places_to_design(steel):
            effects = effects_at(lambda name: read(girder_forces[name], girder, place))
            at_m = float(steel.mesh.length_mesh_m[place[1]])
            keep_worst(girders[girder][place[0]], effects, combinations, at_m)
    braces = {}
    for member in member_forces["steel self weight"]:
        braces[member] = {}
        keep_worst(braces[member], effects_at(lambda name: float(member_forces[name][member])), combinations, None)
    return ConstructionValues(girders, braces, combinations)


# the worst value of each limit state and direction over the combinations, kept if worse than what is there
def keep_worst(by_limit_state, effects, combinations, at_m):
    for combination in combinations:
        for adverse in BOTH_DIRECTIONS:
            value, shares = design_value(effects, combination, adverse)
            current = by_limit_state.setdefault(combination.limit_state, {}).get(adverse)
            if current is None or adverse_sign(adverse) * value > adverse_sign(adverse) * current.value:
                by_limit_state[combination.limit_state][adverse] = GoverningValue(value, combination.name, adverse, shares, at_m)
