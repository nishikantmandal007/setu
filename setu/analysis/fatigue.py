import numpy as np

from setu.analysis.along_span import along_the_mesh, bending_positions_across_width, positions_along_span, response_to_one_vehicle_everywhere
from setu.irc6.fatigue import centreline_band_m, fatigue_impact_factor, fatigue_train_offsets, light_trucks_that_fit
from setu.utils.constants import ROUND_TO_DECIMALS


class FatigueRange:
    # the worst range one pass of the fatigue truck causes, with impact, and where the truck ran and stood
    def __init__(self, range_value, largest, smallest, z_centre_m, x_front_at_largest_m, x_front_at_smallest_m, impact_factor, trucks_ahead=0, trucks_behind=0):
        self.range = range_value
        self.largest = largest
        self.smallest = smallest
        self.z_centre_m = z_centre_m
        self.x_front_at_largest_m = x_front_at_largest_m
        self.x_front_at_smallest_m = x_front_at_smallest_m
        self.impact_factor = impact_factor
        # 120 kN trucks of the Fig. 7A train ahead of and behind the 400 kN truck; x_front is the leading truck's front axle
        self.trucks_ahead = trucks_ahead
        self.trucks_behind = trucks_behind
        self.at_m = None

    # record the station of the design section this range was found for
    def located_at(self, at_m):
        self.at_m = at_m
        return self


# clause 204.6 with the Amendment 8 Fig. 7A train: the 400 kN truck with 0 to n 120 kN trucks ahead and behind at the 20 m minimum gap,
# run along every line it may take on each carriageway; the range of one pass (0 when it is off the bridge included) is the largest
# minus the smallest response; keep the train and line that make it worst
def fatigue_range(surface, cross_section, span_m, sampling):
    on_the_mesh = surface.along_the_mesh()
    most = light_trucks_that_fit(span_m)
    worst = None
    for ahead in range(most + 1):
        for behind in range(most + 1):
            found = fatigue_range_of_one_train(on_the_mesh, surface.skew, cross_section, span_m, sampling, ahead, behind)
            if found is not None and (worst is None or found.range > worst.range):
                worst = found
    if worst is None:
        raise ValueError("no carriageway is wide enough for the clause 204.6 fatigue truck and its 150 mm kerb clearances")
    return worst


# the worst single-passage range of one train configuration over every line on each carriageway
def fatigue_range_of_one_train(on_the_mesh, skew, cross_section, span_m, sampling, ahead, behind):
    offsets = fatigue_train_offsets(ahead, behind)
    sheared = along_the_mesh(offsets, skew)
    x_front_m = positions_along_span(on_the_mesh, sheared)
    factor = fatigue_impact_factor(span_m)
    worst = None
    for carriageway in cross_section.carriageways():
        z_from_m, z_to_m = centreline_band_m(carriageway)
        if z_to_m < z_from_m:
            continue
        z_centre_m = np.unique(np.round(np.concatenate([np.linspace(z_from_m, z_to_m, sampling.positions_across_the_deck_to_try),
                                                         bending_positions_across_width(on_the_mesh, offsets, z_from_m, z_to_m)]), ROUND_TO_DECIMALS))
        responses = factor * response_to_one_vehicle_everywhere(on_the_mesh, sheared, x_front_m, z_centre_m, sampling)
        largest = np.maximum(responses.max(axis=0), 0.0)
        smallest = np.minimum(responses.min(axis=0), 0.0)
        best = int(np.argmax(largest - smallest))
        if worst is None or largest[best] - smallest[best] > worst.range:
            shift_m = skew * z_centre_m[best]
            worst = FatigueRange(float(largest[best] - smallest[best]), float(largest[best]), float(smallest[best]), float(z_centre_m[best]),
                                 float(x_front_m[responses[:, best].argmax()] + shift_m), float(x_front_m[responses[:, best].argmin()] + shift_m), factor,
                                 ahead, behind)
    return worst
