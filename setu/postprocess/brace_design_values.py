from collections import deque

from setu.analysis.along_span import vehicle_responses
from setu.analysis.critical_position import find_critical_position
from setu.analysis.influence_surface import response_to_load_case
from setu.loads.load_cases import LoadCase
from setu.postprocess.design_values import BOTH_DIRECTIONS, girder_values, governing_by_limit_state, load_effects, settle_braking
from setu.postprocess.parallel import analysis_for
from setu.postprocess.governing_diagrams import bridge_diagrams


# axial design forces for every brace member and limit state, with the surfaces and critical positions behind them
MEMBERS_QUEUED = 4


class BraceDesignValues:
    # store the governing member forces, the surfaces, the critical positions and every combination's value
    def __init__(self, members, surfaces, criticals, combinations):
        self.members = members
        self.surfaces = surfaces
        self.criticals = criticals
        self.combinations = combinations


class BridgeDesignValues:
    # girder and brace design values from one shared analysis, and the forces along the girders behind them
    def __init__(self, girders, braces, diagrams, special_vehicle=None, construction=None):
        self.girders = girders
        self.braces = braces
        self.diagrams = diagrams
        # Class SV (cl. 204.5) and construction-stage (cl. 218, Table B.2) values when asked for, else None
        self.special_vehicle = special_vehicle
        self.construction = construction


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
def brace_values(analysis, bridge, seismic, braking_height_above_deck_m, *, keep_surfaces=True, search_pool=None):
    surfaces, criticals = {}, {}
    members, combinations_by_member = {}, {}
    work = analysis.work
    if hasattr(work, "members"):
        # Forked workers finish each member themselves: only its values come back.
        for member, found, governing, combinations in work.members(analysis.model):
            criticals.update({(*member, adverse): found[adverse] for adverse in BOTH_DIRECTIONS})
            members[member], combinations_by_member[member] = governing, combinations
        return BraceDesignValues(members, surfaces, criticals, combinations_by_member)
    for member, surface, found in solved_members(analysis, bridge, search_pool):
        members[member], combinations_by_member[member] = member_values(analysis, seismic, braking_height_above_deck_m, member, surface, found)
        criticals.update({(*member, adverse): found[adverse] for adverse in BOTH_DIRECTIONS})
        # A member's surface is finished with here: on a wide deck hundreds of them are gigabytes.
        if keep_surfaces:
            surfaces[member] = surface
        else:
            analysis.solver.surfaces.pop(surface.name, None)
    return BraceDesignValues(members, surfaces, criticals, combinations_by_member)


# one member's governing values from its surface and worst traffic
def member_values(analysis, seismic, braking_height_above_deck_m, member, surface, found):
    read = brace_reader({member: surface})
    found.update(settle_braking(analysis.model, found, read, (member, None), braking_height_above_deck_m))
    effects = load_effects(analysis, analysis.dead.brace_stages, found, read, (member, None), member, seismic, braking_height_above_deck_m, {})
    at_m = analysis.model.mesh.brace_lines_m[member[1]]
    return governing_by_limit_state(effects, analysis.combinations, analysis.wind_forces, read, member, None, at_m)


# worst traffic for one member in both directions; a surface holding only deck ordinates is all a search worker needs
# Brace members are cross girders / diaphragms: IRC:6 Amendment 10 Table 8 note 3 excludes them from the lane reduction.
def search_member(surface, cross_section, span_m, wearing_course_thickness_m):
    found = {adverse: find_critical_position(surface, cross_section, span_m, adverse, wearing_course_thickness_m, lane_reduction=False) for adverse in BOTH_DIRECTIONS}
    vehicle_responses.cache_clear()  # both directions are done, and no other member shares these grids
    return found


# each brace member in model order with its surface and worst traffic: this process solves, light workers search
def solved_members(analysis, bridge, search_pool):
    model, solver, work = analysis.model, analysis.solver, analysis.work
    search = (bridge.cross_section, bridge.span_m, bridge.wearing_course_thickness_m)
    if work is not None:
        for member in model.brace_elements:
            yield (member, *work.braces[member].result())
    elif search_pool is None:
        for member in model.brace_elements:
            surface = brace_surface(solver, model, member)
            yield member, surface, search_member(surface, *search)
    else:
        waiting = deque()
        for member in model.brace_elements:
            surface = brace_surface(solver, model, member)
            waiting.append((member, surface, search_pool.submit(search_member, surface.deck_only(), *search)))
            # A short queue keeps only a few members' full surfaces in memory at once.
            if len(waiting) >= MEMBERS_QUEUED:
                done, held, found = waiting.popleft()
                yield done, held, found.result()
        while waiting:
            done, held, found = waiting.popleft()
            yield done, held, found.result()


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
    return {(*member, adverse): find_critical_position(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m, lane_reduction=False)
            for member, surface in surfaces.items() for adverse in BOTH_DIRECTIONS}


# a function that reads one brace member off a load case (by reciprocity) or off solved brace forces
def brace_reader(surfaces):

    # axial force in this brace member, tension positive
    def read(forces, member, _=None):
        if isinstance(forces, LoadCase):
            return response_to_load_case(surfaces[member], forces)
        return float(forces[member])
    return read
