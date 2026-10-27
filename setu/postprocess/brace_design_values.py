from setu.analysis.critical_position import find_critical_position
from setu.analysis.influence_surface import response_to_load_case
from setu.loads.load_cases import LoadCase
from setu.postprocess.design_values import BOTH_DIRECTIONS, girder_values, governing_by_limit_state, load_effects
from setu.postprocess.parallel import analysis_for
from setu.postprocess.governing_diagrams import bridge_diagrams


# axial design forces for every brace member and limit state, with the surfaces and critical positions behind them
class BraceDesignValues:
    # store the governing member forces, the surfaces, the critical positions and every combination's value
    def __init__(self, members, surfaces, criticals, combinations):
        self.members = members
        self.surfaces = surfaces
        self.criticals = criticals
        self.combinations = combinations


class BridgeDesignValues:
    # girder and brace design values from one shared analysis, and the forces along the girders behind them
    def __init__(self, girders, braces, diagrams):
        self.girders = girders
        self.braces = braces
        self.diagrams = diagrams


# every load on every brace member, combined per IRC:6 Annex B, tension positive in kN
def brace_design_values(bridge, wind=None, seismic=None, *, braking_height_above_deck_m=None, custom_loads=(), custom_combinations=(), workers=None):
    with analysis_for(bridge, wind, custom_loads, custom_combinations, workers, braces=True) as analysis:
        return brace_values(analysis, bridge, seismic, braking_height_above_deck_m)


# girder and brace design values sharing one set of dead load stages, one model and one solver, with every governing
# girder value replayed as forces along the girders
def bridge_design_values(bridge, wind=None, seismic=None, temperature=None, custom_loads=(), custom_combinations=(),
                         *, braking_height_above_deck_m=None, workers=None):
    with analysis_for(bridge, wind, custom_loads, custom_combinations, workers, girders=True, braces=True) as analysis:
        girders = girder_values(analysis, bridge, seismic, temperature, braking_height_above_deck_m)
        braces = brace_values(analysis, bridge, seismic, braking_height_above_deck_m)
        return BridgeDesignValues(girders, braces, bridge_diagrams(analysis, girders, seismic, braking_height_above_deck_m))


# brace design values from an analysis already set up; the dead forces are the brace forces its dead stages recorded
def brace_values(analysis, bridge, seismic, braking_height_above_deck_m):
    model = analysis.model
    work = analysis.work
    surfaces = brace_surfaces(analysis.solver, model) if work is None else {member: work.braces[member].result()[0] for member in model.brace_elements}
    criticals = brace_live_positions(surfaces, bridge) if work is None else {(*member, adverse): work.braces[member].result()[1][adverse] for member in surfaces for adverse in BOTH_DIRECTIONS}
    read = brace_reader(surfaces)
    members, combinations_by_member, braking = {}, {}, {}
    for member in model.brace_elements:
        live = {adverse: criticals[(*member, adverse)] for adverse in BOTH_DIRECTIONS}
        effects = load_effects(analysis, analysis.dead.brace_stages, live, read, (member, None), member, seismic, braking_height_above_deck_m, braking)
        at_m = model.mesh.brace_lines_m[member[1]]
        members[member], combinations_by_member[member] = governing_by_limit_state(
            effects, analysis.combinations, analysis.wind_forces, read, member, None, at_m)
    return BraceDesignValues(members, surfaces, criticals, combinations_by_member)


# axial force influence surface for every brace member in the model
def brace_surfaces(solver, model):
    surfaces = {}
    for member in model.brace_elements:
        surfaces[member] = brace_surface(solver, model, member)
    return surfaces


# axial surface of one brace member
def brace_surface(solver, model, member):
    pair, station, role = member
    name = f"brace ({pair}, {station}, {role}) at {model.mesh.brace_lines_m[station]:.3f} m"
    return solver.for_brace_axial(name, model.brace_elements[member])


# worst legal traffic on the bridge for each brace member and adverse direction
def brace_live_positions(surfaces, bridge):
    return {(*member, adverse): find_critical_position(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m)
            for member, surface in surfaces.items() for adverse in BOTH_DIRECTIONS}


# a function that reads one brace member off a load case (by reciprocity) or off solved brace forces
def brace_reader(surfaces):

    # axial force in this brace member, tension positive
    def read(forces, member, _=None):
        if isinstance(forces, LoadCase):
            return response_to_load_case(surfaces[member], forces)
        return float(forces[member])
    return read
