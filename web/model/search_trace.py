"""Record setu's own traffic-search intermediates while it runs; never recompute them."""

from contextlib import contextmanager
from functools import wraps

import numpy as np

from setu.analysis import across_carriageway, critical_position
from setu.analysis.along_span import VehicleResponses
from setu.irc6.impact import impact_factor
from setu.irc6.vehicles import class_of, pitch_between_vehicles_m
from setu.utils.constants import BIGGER_IS_WORSE

from model import drawing, progress

_trace = None


# one analysis owns the recorder under jobs._one_at_a_time
@contextmanager
def recording():
    global _trace
    _trace = {"vehicles": [], "envelopes": [], "carriageways": [], "residuals": {},
              "arrangements": [], "cases": []}
    try:
        yield _trace
    finally:
        _trace = None


# observe the returned value at the module where setu looks up its callee
def observe(module, name, capture):
    original = getattr(module, name)

    # return the original result unchanged, recording only during a traffic search
    @wraps(original)
    def wrapped(*args, **kwargs):
        value = original(*args, **kwargs)
        if _trace is not None:
            capture(_trace, args, value)
        return value
    setattr(module, name, wrapped)


# retain the exact transverse grid used by all vehicle curves
def grid(trace, args, value):
    trace["z_m"] = value


# retain each carriageway's envelope and the residual curve evaluated inside it
def envelope(trace, args, value):
    carriageway = args[4]
    trace["carriageways"].append(carriageway)
    trace["envelopes"].append(value)


# residual UDL belongs to this carriageway, rather than to every Class A envelope
def residual(trace, args, value):
    trace["residuals"][id(args[2])] = value


# retain placement objects so each chosen case can be matched by identity
def placements(trace, args, value):
    trace["placements"] = value


# retain the footway response evaluated by setu
def footway(trace, args, value):
    trace["footway"] = value


# start the arrangement when setu has found a layout that fits
def offsets(trace, args, value):
    trace["arrangements"][-1].append({"offsets_m": value, "blocks": []})


# each block's response and vehicle centres at every tested offset
def block(trace, args, value):
    trace["arrangements"][-1][-1]["blocks"].append(
        {"block": args[0], "values": value[0], "centres_m": value[1]})


# retain the dynamic program's chosen offset for each block
def chosen(trace, args, value):
    trace["arrangements"][-1][-1].update(response_before_reduction=value[0], chosen=value[1])


_cases = across_carriageway.cases_for_one_carriageway


# the returned cases map one to one to arrangements recorded inside this call
def cases_for_one_carriageway(*args, **kwargs):
    trace = _trace
    if trace is None:
        return _cases(*args, **kwargs)
    trace["arrangements"].append([])
    value = _cases(*args, **kwargs)
    trace["cases"].append(value)
    for arrangement, case in zip(trace["arrangements"][-1], value, strict=True):
        arrangement.update(lane_pattern=case.lane_pattern, design_lanes=case.design_lanes,
                           lane_reduction=case.lane_reduction)
    return value


# pick original indices for display, keeping all train positions and exact extrema
def train(trace, args, worst):
    self, vehicle, responses, x_m, _ = args
    if responses.shape[1] <= 1:
        return
    along = np.unique(np.linspace(0, len(x_m)-1, min(120, len(x_m))).round().astype(int))
    across = np.unique(np.linspace(0, responses.shape[1]-1, min(60, responses.shape[1])).round().astype(int))
    ordinates = []
    for j, positions in enumerate(worst.train_x_front_m):
        indices = np.searchsorted(x_m, positions)
        assert np.array_equal(x_m[indices], positions)
        ordinates.append(responses[indices, j])
    factor = impact_factor(class_of(vehicle), self.span_m)
    trace["vehicles"].append({"key": vehicle.name, "name": vehicle.name.removesuffix("_reversed").replace("_", " "),
                               "heading": drawing.heading_of(vehicle.name), "impact_factor": float(factor),
                               "pitch_m": float(pitch_between_vehicles_m(vehicle)),
                               "x_m": x_m[along], "x_index": along, "z_index": across,
                               "values": responses[np.ix_(along, across)], "full_shape": list(responses.shape),
                               "minimum": float(responses.min()), "maximum": float(responses.max()),
                               "train": {"response": factor * worst.response,
                                         "x_front_m": worst.train_x_front_m, "ordinates": ordinates}})


observe(critical_position, "positions_across_width", grid)
observe(critical_position, "envelope_every_block", envelope)
observe(critical_position, "find_worst_placement", placements)
observe(critical_position, "footway_response", footway)
observe(across_carriageway, "residual_udl_curve", residual)
across_carriageway.cases_for_one_carriageway = cases_for_one_carriageway
observe(across_carriageway, "sliding_offsets", offsets)
observe(across_carriageway, "block_contribution", block)
observe(across_carriageway, "place_vehicles", chosen)
observe(VehicleResponses, "worst_train_at_each_position", train)


# convert recorded arrays to JSON numbers, scaling responses but never coordinates
def as_json(record, ranked_critical_positions, scale):
    vehicles = []
    for vehicle in record["vehicles"]:
        vehicles.append({**vehicle, "x_m": vehicle["x_m"].tolist(), "x_index": vehicle["x_index"].tolist(),
                         "z_index": vehicle["z_index"].tolist(), "values": (scale * vehicle["values"]).tolist(),
                         "minimum": scale * vehicle["minimum"], "maximum": scale * vehicle["maximum"],
                         "train": {"response": (scale * vehicle["train"]["response"]).tolist(),
                                   "x_front_m": [list(xs) for xs in vehicle["train"]["x_front_m"]],
                                   "ordinates": [(scale * row).tolist() for row in vehicle["train"]["ordinates"]]}})
    envelopes = []
    for carriageway, curves in zip(record["carriageways"], record["envelopes"], strict=True):
        envelopes.append({block: {"response": (scale * curve.response).tolist(), "winner": list(curve.winner),
                                  "residual_udl": (scale * record["residuals"][id(carriageway)]).tolist()
                                  if across_carriageway.carries_a_residual_udl(block, carriageway) else None}
                          for block, curve in curves.items()})
    arrangements = [[{**arrangement, "offsets_m": arrangement["offsets_m"].tolist(),
                      "response_before_reduction": float(scale * arrangement["response_before_reduction"]),
                      "chosen": [int(i) for i in arrangement["chosen"]],
                      "blocks": [{"block": b["block"], "values": (scale * b["values"]).tolist(),
                                  "centres_m": b["centres_m"].tolist()} for b in arrangement["blocks"]]}
                     for arrangement in carriageway] for carriageway in record["arrangements"]]
    indices = [{id(case): i for i, case in enumerate(cases)} for cases in record["cases"]]
    ranking = [{"rank": rank, "cases": [indices[c][id(case)] for c, case in enumerate(placement.per_carriageway)],
                "lane_pattern": critical.lane_pattern,
                "vehicles_and_udl": float(scale * (critical.response_before_reduction - critical.footway_response)),
                "lane_reduction": float(critical.lane_reduction), "footway": float(scale * critical.footway_response),
                "response": float(scale * critical.response), "vehicles": progress.vehicles(critical) if rank <= 10 else []}
               for rank, (critical, placement) in enumerate(zip(ranked_critical_positions, record["placements"], strict=True), 1)]
    return {"z_m": record["z_m"].tolist(),
            "carriageways": [{"from_m": float(c.left_m), "to_m": float(c.right_m)} for c in record["carriageways"]],
            "vehicles": vehicles, "envelopes": envelopes, "arrangements": arrangements,
            "footway": float(scale * record["footway"]), "ranking": ranking}


# a completed traffic search, with the leading layouts and every envelope
def preview(record, ranked, target, unit, adverse, searched, of):
    view = as_json({**record, "vehicles": []}, ranked, 1.0)  # the live view never draws the vehicle fields
    ranking = [{**row, "vehicles": row["vehicles"] if row["rank"] == 1 else []} for row in view["ranking"][:8]]
    return {"kind": "search", "target": target, "unit": unit, "worse_is_larger": adverse == BIGGER_IS_WORSE,
            "z_m": view["z_m"], "carriageways": view["carriageways"], "envelopes": view["envelopes"],
            "ranking": ranking, "searched": searched, "of": of}

