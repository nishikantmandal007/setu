from setu.analysis.critical_position import find_critical_position
from setu.analysis.special_vehicle import special_vehicle_on_each_carriageway, without_the_special_vehicle_carriageway
from setu.helpers import DEFAULT_SAMPLING, adverse_sign
from setu.irc6.combinations import Combination, design_value
from setu.irc6.irc_constants import PERMANENT_LOAD_FACTORS, SPECIAL_VEHICLE_FACTORS, VARIABLE_LOAD_FACTORS
from setu.postprocess.brace_design_values import brace_reader, brace_surface
from setu.postprocess.design_values import BOTH_DIRECTIONS, GoverningValue, live_with_braking, places_to_design, reader, surface_for
from setu.postprocess.girder_response import STAGE_IS_FACTORED_AS
from setu.postprocess.parallel import analysis_for
from setu.utils.constants import BASIC, DEAD, FREQUENT, LIVE, RARE, RESPONSES, SURFACING

SPECIAL_VEHICLE = "special vehicle"
NOT_WHEN_RELIEVING = 0.0
ACCOMPANYING = 1


class SpecialVehicleValues:
    # governing Class SV design values: girders by girder, response and limit state; braces by member and limit state; and the placements
    def __init__(self, girders, braces, placements):
        self.girders = girders
        self.braces = braces
        self.placements = placements


# cl. 204.5.4: the Class SV at 1.15 (ULS basic), 1.0 (SLS rare), 0.75 (SLS frequent) with the Annex B permanent loads; traffic on the
# other carriageways accompanies it (Tables B.2, B.3); no wind, seismic or temperature gradient
def special_vehicle_combinations():
    combinations = []
    for limit_state in (BASIC, RARE, FREQUENT):
        factors = dict(PERMANENT_LOAD_FACTORS[limit_state])
        factors[SPECIAL_VEHICLE] = (SPECIAL_VEHICLE_FACTORS[limit_state], NOT_WHEN_RELIEVING)
        factors[LIVE] = (VARIABLE_LOAD_FACTORS[limit_state][LIVE][ACCOMPANYING], NOT_WHEN_RELIEVING)
        combinations.append(Combination(f"{limit_state}, special vehicle leading", limit_state, factors, SPECIAL_VEHICLE))
    return combinations


# the worst Class SV combination at one place: each carriageway in turn carries the SV, the others their own worst traffic with braking
def special_vehicle_effects(analysis, bridge, surface, read, target, dead_stages, *, lane_reduction=True):
    effects_by_carriageway = []
    dead = sum(read(dead_stages[stage], *target) for stage in dead_stages if STAGE_IS_FACTORED_AS[stage] == DEAD)
    surfacing = sum(read(dead_stages[stage], *target) for stage in dead_stages if STAGE_IS_FACTORED_AS[stage] == SURFACING)
    on_each = {adverse: special_vehicle_on_each_carriageway(surface, bridge.cross_section, adverse, DEFAULT_SAMPLING) for adverse in BOTH_DIRECTIONS}
    for k in range(len(bridge.cross_section.carriageways())):
        others = without_the_special_vehicle_carriageway(bridge.cross_section, k)
        live = []
        for adverse in BOTH_DIRECTIONS:
            if others.carriageways():
                critical = find_critical_position(surface, others, bridge.span_m, adverse, bridge.wearing_course_thickness_m, lane_reduction=lane_reduction)
                live.append(live_with_braking(analysis.model, critical, read, *target))
        effects_by_carriageway.append(({DEAD: dead, SURFACING: surfacing, SPECIAL_VEHICLE: [on_each[adverse][k].response for adverse in BOTH_DIRECTIONS],
                                        LIVE: live or 0.0}, [on_each[adverse][k] for adverse in BOTH_DIRECTIONS]))
    return effects_by_carriageway


# the worst value of each limit state and direction over the carriageways, kept if worse than what is there
def keep_worst(by_limit_state, effects_by_carriageway, combinations, at_m):
    for effects, _ in effects_by_carriageway:
        for combination in combinations:
            for adverse in BOTH_DIRECTIONS:
                value, shares = design_value(effects, combination, adverse)
                current = by_limit_state.setdefault(combination.limit_state, {}).get(adverse)
                if current is None or adverse_sign(adverse) * value > adverse_sign(adverse) * current.value:
                    by_limit_state[combination.limit_state][adverse] = GoverningValue(value, combination.name, adverse, shares, at_m)


# Class SV design values for every girder place and brace member (cl. 204.5; required for new bridges except on rural, district
# and village roads, cl. 201.1 as amended)
def special_vehicle_design_values(bridge, *, workers=1):
    combinations = special_vehicle_combinations()
    girders, braces, placements = {}, {}, {}
    with analysis_for(bridge, None, (), (), workers, girders=True, braces=True) as analysis:
        model, solver = analysis.model, analysis.solver
        for girder in range(bridge.girders.count):
            girders[girder] = {response: {} for response in RESPONSES}
            for place in places_to_design(model):
                surface = surface_for(solver, model, girder, place)
                found = special_vehicle_effects(analysis, bridge, surface, reader({(girder, place): surface}), (girder, place), analysis.dead.stages)
                keep_worst(girders[girder][place[0]], found, combinations, float(model.mesh.length_mesh_m[place[1]]))
                placements[girder, place] = [placement for _, pair in found for placement in pair]
        for member in model.brace_elements:
            surface = brace_surface(solver, model, member)
            # braces are cross girders / diaphragms: no Table 8 reduction (note 3, Amendment 10)
            found = special_vehicle_effects(analysis, bridge, surface, brace_reader({member: surface}), (member, None), analysis.dead.brace_stages, lane_reduction=False)
            braces[member] = {}
            keep_worst(braces[member], found, combinations, None)
    return SpecialVehicleValues(girders, braces, placements)
