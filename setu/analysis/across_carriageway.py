import itertools
import numpy as np
from setu.errors import NoAdmissibleArrangementError
from setu.helpers import adverse_sign, index_of_worst, is_worst_first
from setu.irc6.lanes import (
    fit_blocks_between,
    lane_reduction_factor,
    list_admissible_arrangements,
    needs_residual_udl,
    response_to_area_load,
    strips_beside_class_a,
    where_vehicle_sits_in_block,
)
from setu.analysis.along_span import best_so_far, positions_inside_zone, read_curve
from setu.irc6.irc_constants import RESIDUAL_UDL_KPA
from setu.utils.constants import CLASS_A_LANE, ROUND_TO_DECIMALS, TOLERANCE_M

class BlockEnvelope:
    # worst response of any allowed vehicle at each position across, and who gave it
    def __init__(self, z_positions_m, response, winner):
        self.z_positions_m = z_positions_m
        self.response = response
        self.winner = winner

    # envelope read at z
    def __call__(self, z_m):
        return np.interp(z_m, self.z_positions_m, self.response)

    # vehicle that governs nearest to z
    def winner_at(self, z_m):
        distance_away_m = np.abs(self.z_positions_m - float(z_m))
        nearest = int(distance_away_m.argmin())
        return self.winner[nearest]

# envelope for Class A lanes and 70R zones on one carriageway
def envelope_every_block(responses, permitted, z_positions_m, adverse, carriageway, surface, sampling):
    envelopes = {}
    for block, choices in permitted.items():
        response, winner = worst_of_the_permitted_vehicles(responses, choices, z_positions_m, adverse)
        if carries_a_residual_udl(block, carriageway):
            response = response + residual_udl_curve(surface, z_positions_m, carriageway, adverse, sampling)
        envelopes[block] = BlockEnvelope(z_positions_m=z_positions_m, response=response, winner=winner)
    return envelopes

# worst allowed vehicle at every position across
def worst_of_the_permitted_vehicles(responses, choices, z_positions_m, adverse):
    curves = [responses.for_vehicle(vehicle, z_positions_m, adverse) for vehicle in choices]
    one_row_per_vehicle = np.vstack([curve.response for curve in curves])
    worst_vehicle = index_of_worst(one_row_per_vehicle, adverse, axis=0)
    every_position = np.arange(len(z_positions_m))
    response = one_row_per_vehicle[worst_vehicle, every_position]
    winner = [choices[which].name for which in worst_vehicle]
    return (response, winner)

# a Class A lane on a narrow carriageway gets the residual UDL
def carries_a_residual_udl(block, carriageway):
    return block == CLASS_A_LANE and needs_residual_udl(carriageway.width_m())

# residual UDL response beside a Class A lane at each position
def residual_udl_curve(surface, z_positions_m, carriageway, adverse, sampling):
    added_at_each_position = [response_to_area_load(surface, strips_beside_class_a(float(z_m), carriageway.left_m, carriageway.right_m), adverse, RESIDUAL_UDL_KPA, sampling) for z_m in z_positions_m]
    return np.array(added_at_each_position)


# best offset for each block left to right, by dynamic programming
def place_vehicles(block_curves, adverse):
    worse_is_positive = adverse_sign(adverse)
    signed_best_total = worse_is_positive * np.asarray(block_curves[0], float)
    offset_of_the_block_to_the_left = []
    for curve in block_curves[1:]:
        best_to_the_left, where_that_best_sat = best_so_far(signed_best_total)
        signed_best_total = worse_is_positive * np.asarray(curve, float) + best_to_the_left
        offset_of_the_block_to_the_left.append(where_that_best_sat)
    chosen_offsets = walk_back_through_the_blocks(signed_best_total, offset_of_the_block_to_the_left)
    worst_total = sum((float(np.asarray(curve)[offset]) for curve, offset in zip(block_curves, chosen_offsets, strict=True)))
    return (worst_total, chosen_offsets)

# read the chosen offsets back from the rightmost block
def walk_back_through_the_blocks(signed_best_total, offset_of_the_block_to_the_left):
    offset = int(np.argmax(signed_best_total))
    chosen_offsets = [offset]
    for where_the_block_to_the_left_sat in reversed(offset_of_the_block_to_the_left):
        offset = int(where_the_block_to_the_left_sat[offset])
        chosen_offsets.append(offset)
    chosen_offsets.reverse()
    return chosen_offsets



class CarriagewayCase:
    # one lane pattern on one carriageway with its vehicle centres and response
    def __init__(self, lane_pattern, design_lanes, sliding_room_m, vehicle_centres_m, response_before_reduction, response, lane_reduction):
        self.lane_pattern = lane_pattern
        self.design_lanes = design_lanes
        self.sliding_room_m = sliding_room_m
        self.vehicle_centres_m = vehicle_centres_m
        self.response_before_reduction = response_before_reduction
        self.response = response
        self.lane_reduction = lane_reduction

class TransversePlacement:
    # one case per carriageway put together, with the lane reduction
    def __init__(self, response, response_before_reduction, lane_reduction, design_lanes, per_carriageway):
        self.response = response
        self.response_before_reduction = response_before_reduction
        self.lane_reduction = lane_reduction
        self.design_lanes = design_lanes
        self.per_carriageway = per_carriageway

class TransverseSearch:
    # settings for the search across the deck
    def __init__(self, adverse, sampling, curve_breakpoints_m, lane_reduction=True):
        self.adverse = adverse
        self.sampling = sampling
        self.curve_breakpoints_m = curve_breakpoints_m
        self.lane_reduction = lane_reduction

    # Table 8 factor for this many design lanes, or 1 where the reduction does not apply
    def reduction_for(self, design_lanes):
        return lane_reduction_factor(design_lanes) if self.lane_reduction else 1.0

# every legal lane layout across all carriageways, worst first
def find_worst_placement(carriageways, response_curves, adverse, curve_breakpoints_m, sampling, lane_reduction=True):
    check_one_set_of_curves_per_carriageway(carriageways, response_curves)
    search = TransverseSearch(adverse=adverse, sampling=sampling, curve_breakpoints_m=curve_breakpoints_m, lane_reduction=lane_reduction)
    cases_per_carriageway = [cases_for_one_carriageway(carriageway, curves, search) for carriageway, curves in zip(carriageways, response_curves, strict=True)]
    if any((not cases for cases in cases_per_carriageway)):
        widths_m = [round(carriageway.width_m(), 3) for carriageway in carriageways]
        raise NoAdmissibleArrangementError(f'no IRC:6 lane arrangement fits this cross-section; carriageway widths are {widths_m} m')
    return combine_across_carriageways(cases_per_carriageway, search)

# best placement of every allowed lane pattern on one carriageway
def cases_for_one_carriageway(carriageway, curves, search):
    cases = []
    for arrangement in list_admissible_arrangements(carriageway.width_m()):
        layout = fit_blocks_between(arrangement.lane_pattern, carriageway.left_m, carriageway.right_m)
        if layout is None:
            continue
        offsets_m = sliding_offsets(arrangement, layout, search)
        contributions = []
        centres_m = []
        for block, width_m, packed_left_m in walk_the_blocks(arrangement, layout):
            values, positions = block_contribution(block, width_m, packed_left_m, offsets_m, curves, search)
            contributions.append(values)
            centres_m.append(positions)
        response, chosen = place_vehicles(contributions, search.adverse)
        reduction = search.reduction_for(arrangement.design_lanes)
        cases.append(CarriagewayCase(lane_pattern=list(arrangement.lane_pattern), design_lanes=arrangement.design_lanes, sliding_room_m=layout.sliding_room_m, vehicle_centres_m=[float(centre_m[offset]) for centre_m, offset in zip(centres_m, chosen, strict=True)], response_before_reduction=response, lane_reduction=reduction, response=response * reduction))
    return cases

# each block with its width and packed left edge
def walk_the_blocks(arrangement, layout):
    return list(zip(arrangement.lane_pattern, layout.block_widths_m, layout.packed_left_edges_m, strict=True))

# how far to slide the blocks right: an even spread plus the curve's kinks
def sliding_offsets(arrangement, layout, search):
    room_m = layout.sliding_room_m
    has_nowhere_to_slide = room_m < TOLERANCE_M
    steps = 1 if has_nowhere_to_slide else search.sampling.sliding_offsets_to_try
    worth_trying = [np.linspace(0.0, room_m, steps)]
    if not has_nowhere_to_slide:
        breakpoints_m = np.asarray(search.curve_breakpoints_m, float)
        for block, width_m, packed_left_m in walk_the_blocks(arrangement, layout):
            for where_in_block_m in set(where_vehicle_sits_in_block(block, width_m)):
                lands_on_a_bend = breakpoints_m - packed_left_m - where_in_block_m
                is_within_the_sliding_room = (lands_on_a_bend >= -TOLERANCE_M) & (lands_on_a_bend <= room_m + TOLERANCE_M)
                worth_trying.append(lands_on_a_bend[is_within_the_sliding_room])
    return np.unique(np.round(np.concatenate(worth_trying), ROUND_TO_DECIMALS))

# one block's response at each offset, and where its vehicle sits
def block_contribution(block, block_width_m, packed_left_m, offsets_m, curves, search):
    nearest_m, furthest_m = where_vehicle_sits_in_block(block, block_width_m)
    is_pinned_to_the_middle_of_its_lane = nearest_m == furthest_m
    if is_pinned_to_the_middle_of_its_lane:
        centres_m = packed_left_m + offsets_m + nearest_m
        return (read_curve(curves[block], centres_m), centres_m)
    return worst_spot_inside_the_zone(block, packed_left_m, nearest_m, furthest_m, offsets_m, curves, search)

# the worse of two (signed value, position) candidates, element by element: bigger signed value, then the smaller position
def better(value_a, position_a, value_b, position_b):
    takes_b = (value_b > value_a) | ((value_b == value_a) & (position_b < position_a))
    return np.where(takes_b, value_b, value_a), np.where(takes_b, position_b, position_a)


# sparse table over the sorted kinks: level j holds the worst of each run of 2**j kinks
def kink_table(signed, positions):
    levels = [(signed, positions)]
    width = 1
    while 2 * width <= len(signed):
        value, position = levels[-1]
        levels.append(better(value[:-width], position[:-width], value[width:], position[width:]))
        width *= 2
    return levels


# the sparse table of one envelope's kinks, built once per search: within a search the kinks and each envelope are fixed, and every
# zone placement on that envelope reads the same values
def kink_table_of(curve, sign, kinks_m, search):
    tables = getattr(search, "kink_tables", None)
    if tables is None:
        tables = search.kink_tables = {}
    key = (id(curve), sign)
    if key not in tables:
        rounded_m = np.round(kinks_m, ROUND_TO_DECIMALS)
        tables[key] = (curve, kink_table(sign * read_curve(curve, rounded_m), rounded_m))  # the curve is kept so its id stays its own
    return tables[key][1]


# worst spot for a 70R vehicle inside its zone at every offset at once: the zone's ends, an even spread and the kinks inside it,
# the same candidates as before, the worst signed value and the smallest position on a tie
def worst_spot_inside_the_zone(block, packed_left_m, nearest_m, furthest_m, offsets_m, curves, search):
    curve = curves[block]
    sign = adverse_sign(search.adverse)
    offsets_m = np.asarray(offsets_m, float)
    zone_from_m = packed_left_m + offsets_m + nearest_m
    zone_to_m = packed_left_m + offsets_m + furthest_m
    # each zone's worst spot depends only on its two ends, the envelope and the kinks, fixed within a search; zones come back across
    # lane layouts, so each is worked out once per search and envelope
    memos = getattr(search, "zone_memos", None)
    if memos is None:
        memos = search.zone_memos = {}
    curve_memo = memos.setdefault((id(curve), sign), (curve, {}))[1]  # the curve is kept so its id stays its own
    ends = list(zip(zone_from_m.tolist(), zone_to_m.tolist()))
    new_ends = [end for end in dict.fromkeys(ends) if end not in curve_memo]
    if new_ends:
        new_from_m, new_to_m = (np.array(column, float) for column in zip(*new_ends))
        values, positions = zone_worst_spots(curve, sign, new_from_m, new_to_m, search)
        curve_memo.update(zip(new_ends, zip(values.tolist(), positions.tolist())))
    found = [curve_memo[end] for end in ends]
    return np.array([value for value, _ in found], float), np.array([position for _, position in found], float)


# the worst spot inside each zone given by its ends: the zone ends, an even spread and the kinks inside it, the worst signed value
# and the smallest position on a tie; every zone row is worked out on its own
def zone_worst_spots(curve, sign, zone_from_m, zone_to_m, search):
    spread_m = np.linspace(zone_from_m, zone_to_m, search.sampling.positions_inside_a_70r_zone_to_try, axis=1)
    fixed_m = np.round(np.concatenate([zone_from_m[:, None], zone_to_m[:, None], spread_m], axis=1), ROUND_TO_DECIMALS)
    fixed_signed = sign * read_curve(curve, fixed_m.ravel()).reshape(fixed_m.shape)
    worst = fixed_signed.max(axis=1, keepdims=True)
    position = np.where(fixed_signed == worst, fixed_m, np.inf).min(axis=1)
    value = worst[:, 0]
    kinks_m = np.asarray(search.curve_breakpoints_m, float)
    if len(kinks_m):
        levels = kink_table_of(curve, sign, kinks_m, search)
        first = np.searchsorted(kinks_m, zone_from_m - TOLERANCE_M, side="left")
        last = np.searchsorted(kinks_m, zone_to_m + TOLERANCE_M, side="right")
        has_kinks = last > first
        span = np.where(has_kinks, last - first, 1)
        level = np.floor(np.log2(span)).astype(int)
        left_value = np.full(len(first), -np.inf); left_position = np.full(len(first), np.inf)
        right_value = left_value.copy(); right_position = left_position.copy()
        for j in np.unique(level[has_kinks]):
            rows = has_kinks & (level == j)
            table_value, table_position = levels[j]
            left_value[rows], left_position[rows] = table_value[first[rows]], table_position[first[rows]]
            right_value[rows], right_position[rows] = table_value[last[rows] - 2 ** j], table_position[last[rows] - 2 ** j]
        kink_value, kink_position = better(left_value, left_position, right_value, right_position)
        value, position = better(value, position, kink_value, kink_position)
    return sign * value, position

# every mix of one case per carriageway, with the lane reduction for the total
def combine_across_carriageways(cases_per_carriageway, search):
    combinations = []
    for chosen in itertools.product(*cases_per_carriageway):
        design_lanes = sum((case.design_lanes for case in chosen))
        before_reduction = sum((case.response_before_reduction for case in chosen))
        reduction = search.reduction_for(design_lanes)
        combinations.append(TransversePlacement(response=before_reduction * reduction, response_before_reduction=before_reduction, lane_reduction=reduction, design_lanes=design_lanes, per_carriageway=list(chosen)))
    combinations.sort(key=lambda placement: placement.response, reverse=is_worst_first(search.adverse))
    return combinations

# one set of response curves per carriageway, or an error
def check_one_set_of_curves_per_carriageway(carriageways, response_curves):
    if len(response_curves) != len(carriageways):
        raise ValueError(f'there are {len(carriageways)} carriageways but {len(response_curves)} sets of response curves; a narrow carriageway carries its own residual UDL, so each one needs its own curves')
