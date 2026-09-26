import numpy as np

from setu import applied_live_loads, build_mesh, rank_all_positions
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.impact import impact_factor
from setu.irc6.irc_constants import CLASS_A_KERB_CLEARANCE_M, CLASS_A_LANE_WIDTH_M, VEHICLE_70R_CLEARANCE_M, VEHICLE_70R_WIDTH_M, ZONE_70R_ALONE_M
from setu.irc6.vehicles import CLASS_70R_TRACKED, CLASS_70R_WHEELED, CLASS_A, TrackedVehicle, both_directions_of, find_vehicle_or_its_reverse
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.utils.constants import BEARING_REACTION, BIGGER_IS_WORSE, MAX_MOMENT, MIDSPAN_DEFLECTION, SMALLER_IS_WORSE, SUPPORT_SHEAR

ROLL_STEPS = 90
ARRANGEMENTS_REPLAYED = 6
# the design places shown in the web app: key, (response, adverse), label, unit, and the scale from setu's units to the unit shown
PLACES = {
    "moment": ((MAX_MOMENT, BIGGER_IS_WORSE), "Moment near midspan", "kN·m", 1.0),
    "shear": ((SUPPORT_SHEAR, SMALLER_IS_WORSE), "Shear at the support", "kN", 1.0),
    "reaction": ((BEARING_REACTION, BIGGER_IS_WORSE), "Reaction at the bearing", "kN", 1.0),
    "deflection": ((MIDSPAN_DEFLECTION, BIGGER_IS_WORSE), "Midspan deflection", "mm", 1000.0),
}
CRITICAL_LABEL = {(MAX_MOMENT, BIGGER_IS_WORSE): "largest moment", (MAX_MOMENT, SMALLER_IS_WORSE): "smallest moment",
                  (SUPPORT_SHEAR, BIGGER_IS_WORSE): "largest + shear", (SUPPORT_SHEAR, SMALLER_IS_WORSE): "largest − shear",
                  (BEARING_REACTION, BIGGER_IS_WORSE): "largest reaction", (BEARING_REACTION, SMALLER_IS_WORSE): "smallest reaction",
                  (MIDSPAN_DEFLECTION, BIGGER_IS_WORSE): "largest deflection"}


# the loads of one girder's critical position for a response, as Setu applies them
def loads_at(bridge, results, girder, response=MAX_MOMENT, adverse=BIGGER_IS_WORSE):
    key = (girder, response, adverse)
    critical = results.criticals[key]
    wheels, patches = applied_live_loads(bridge, critical, results.surfaces[key])
    return critical, float(results.dead.total[girder].stations_m[results.stations[key]]), wheels, patches


# a vehicle on the deck for drawing: its front axle at x, centre line at z, body and axles measured from the front axle
def body_of(name, x_front_m, z_m, impact):
    vehicle = find_vehicle_or_its_reverse(name)
    tracked = isinstance(vehicle, TrackedVehicle)
    body_m = (0.0, vehicle.length_m()) if tracked else (-vehicle.lead_clearance_m, sum(vehicle.axle_spacing_m) + vehicle.trail_clearance_m)
    heading = heading_of(name)
    return {"name": name.removesuffix("_reversed").replace("_", " "), "x_m": float(x_front_m), "z_m": float(z_m), "body_m": body_m,
            "from_m": float(x_front_m + body_m[0]), "to_m": float(x_front_m + body_m[1]), "heading": heading, "impact_factor": impact, "tracked": tracked,
            "width_m": CLASS_A_LANE_WIDTH_M if name.startswith("Class_A") else VEHICLE_70R_WIDTH_M, "gauge_m": vehicle.transverse_gauge_m,
            "axles_m": [] if tracked else list(vehicle.axle_positions_m()), "track_m": [vehicle.track_length_m, vehicle.track_width_m] if tracked else None,
            "axle_loads_t": [2 * vehicle.load_per_track_t] if tracked else list(vehicle.axle_loads_t)}


# what the deck view needs: strips, girder lines and each girder's critical trucks, wheels and patches for every design place
def deck_drawing(bridge, results):
    places = {}
    for key, ((response, adverse), _, _, scale) in PLACES.items():
        places[key] = {}
        for girder in range(bridge.girders.count):
            critical, at_m, wheels, patches = loads_at(bridge, results, girder, response, adverse)
            places[key][girder] = {"at_m": at_m, "value": scale * critical.response, "lane_reduction": critical.lane_reduction, "lane_pattern": critical.lane_pattern,
                                   "vehicles": [body_of(placed.vehicle_name, x_m, placed.z_centre_m, placed.impact_factor) for placed in critical.vehicles for x_m in placed.train_x_front_m],
                                   "wheels": [[w["x_m"], w["z_m"], w["applied_kn"]] for w in wheels if w["on_span"]],
                                   "patches": [{"kind": p["kind"], "kpa": p["pressure_kpa"], "corners": p["corners_x_z_m"]} for p in patches]}
    girders = places["moment"]
    dead = results.dead.total
    return {"span_m": bridge.span_m, "width_m": bridge.width_m(), "skew": bridge.skew, "girder_lines_m": [float(z) for z in build_mesh(bridge).girder_lines_m],
            "strips": [{"name": s.name, "from_m": s.z_from_m, "to_m": s.z_to_m} for s in bridge.cross_section.strips], "max_moment": girders, "places": places,
            "dead_moment": {girder: {"x_m": [float(x) for x in dead[girder].stations_m], "kn_m": [float(m) for m in dead[girder].composite_moment_kn_m]}
                            for girder in range(bridge.girders.count)}}


# one load case's forces along every girder, rounded for the page
def along_girders(forces):
    return {girder: {"m": np.round(f.composite_moment_kn_m, 2).tolist(), "v": np.round(f.shear_kn, 2).tolist(),
                     "d": np.round(1000 * f.deflection_m, 3).tolist(), "r": round(f.reaction_kn, 2)} for girder, f in forces.items()}


# moment, shear and deflection along every girder for each dead stage and each critical live load (the live ones solved in OpenSees)
def diagrams(results, live_forces):
    cases = {f"Dead · {stage}": along_girders(forces) for stage, forces in results.dead.stages.items()}
    cases["Dead · all stages"] = along_girders(results.dead.total)
    for (girder, response, adverse), forces in zip(results.criticals, live_forces, strict=True):
        cases[f"Live · {CRITICAL_LABEL[response, adverse]} in G{girder}"] = along_girders(forces)
    return {"x_m": results.dead.total[0].stations_m.tolist(), "cases": cases}


# the deck mesh, girder lines, brace lines and girder depth for the 3D view
def mesh_of(bridge):
    mesh = build_mesh(bridge)
    section = bridge.girders.section
    return {"x_m": mesh.length_mesh_m.tolist(), "z_m": mesh.width_mesh_m.tolist(), "girder_lines_m": mesh.girder_lines_m.tolist(),
            "brace_lines_m": mesh.brace_lines_m.tolist(), "skew": bridge.skew, "slab_m": bridge.deck.thickness_m,
            "depth_m": section.web_height_m + section.top_flange_thickness_m + section.bottom_flange_thickness_m}


# a layout of vehicles driven across the span, each the way it faces, passing their given place at travel 0; the effect at every travel distance
def rolling(bridge, surface, layout, lane_reduction):
    points = np.array([(x_m + dx, z_m + dz, load * impact * lane_reduction, heading_of(name)) for name, x_m, z_m, impact in layout
                       for dx, dz, load in wheel_load_offsets(find_vehicle_or_its_reverse(name), bridge.wearing_course_thickness_m, DEFAULT_SAMPLING)])
    margin_m = 2.0 + abs(bridge.skew) * bridge.width_m()
    off_both_ends_m = max(np.max(bridge.span_m + margin_m - points[:, 0]), np.max(points[:, 0] + margin_m))
    travel_m = np.union1d(np.linspace(-off_both_ends_m, off_both_ends_m, ROLL_STEPS), [0.0])
    wheel_x_m = points[None, :, 0] + travel_m[:, None] * points[None, :, 3]
    moments = (points[:, 2] * surface.influence_at(wheel_x_m, points[None, :, 1])).sum(axis=1)
    return travel_m, moments


# which way a vehicle drives: its axles lie behind the front one in +x, so it drives towards -x; turned round, towards +x
def heading_of(name):
    return 1 if name.endswith("_reversed") else -1


# one rolled layout for the replay, signed and scaled so the adverse direction plots upward (a support shear is negative, a deflection is shown in mm)
def trial(bridge, surface, label, kind, layout, lane_reduction, total=None, shown_as=1.0):
    shifts, moments = rolling(bridge, surface, layout, lane_reduction)
    moments = shown_as * moments
    peak = int(np.argmax(moments))
    return {"label": label, "kind": kind, "vehicles": [body_of(*vehicle) for vehicle in layout], "shifts": np.round(shifts, 3).tolist(),
            "moments": np.round(moments, 1).tolist(), "peak": float(moments[peak]), "peak_at": peak,
            "total": float(moments[peak]) if total is None else total}


# the search replayed for one girder and one design place: each vehicle alone rolled along each lane, then setu's best lane arrangements
def replay(bridge, results, girder, place):
    (response, adverse), _, _, scale = PLACES[place]
    key = (girder, response, adverse)
    surface = results.surfaces[key]
    shown_as = scale * (1.0 if adverse == BIGGER_IS_WORSE else -1.0)
    trials = []
    for lane, carriageway in enumerate(bridge.cross_section.carriageways(), start=1):
        kinds = [(CLASS_A, CLASS_A_LANE_WIDTH_M / 2 + CLASS_A_KERB_CLEARANCE_M)]
        if carriageway.width_m() >= ZONE_70R_ALONE_M:
            kinds += [(vehicle, VEHICLE_70R_WIDTH_M / 2 + VEHICLE_70R_CLEARANCE_M) for vehicle in (CLASS_70R_WHEELED, CLASS_70R_TRACKED)]
        for vehicle, from_edge_m in kinds:
            nearest, furthest = carriageway.left_m + from_edge_m, carriageway.right_m - from_edge_m
            for z_m in sorted({round(nearest, 3), round((nearest + furthest) / 2, 3), round(furthest, 3)}):
                both = [trial(bridge, surface, f"{way.name.replace('Class_', '').replace('_', ' ').replace(' reversed', ' ↺')} alone · c/w {lane} · z {z_m:.2f} m",
                              "single", [(way.name, bridge.span_m / 2, z_m, impact_factor(way.name, bridge.span_m))], 1.0, shown_as=shown_as) for way in both_directions_of(vehicle)]
                trials.append(max(both, key=lambda t: t["peak"]))
    ranked = rank_all_positions(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m)
    # IRC:22 live deflection leaves the footway load out, so its arrangements are compared without it
    without_footway = response == MIDSPAN_DEFLECTION
    arrangements = []
    for rank in reversed(range(min(ARRANGEMENTS_REPLAYED, len(ranked)))):
        case = ranked[rank]
        layout = [(placed.vehicle_name, x_m, placed.z_centre_m, placed.impact_factor) for placed in case.vehicles for x_m in placed.train_x_front_m]
        value = case.response - (case.footway_response * case.lane_reduction if without_footway else 0.0)
        found = trial(bridge, surface, f"Arrangement #{rank + 1}: {case.lane_pattern.replace('_', ' ').replace('class', 'Class').replace('70r', '70R').replace('Class a', 'Class A')}", "arrangement",
                      layout, case.lane_reduction, total=shown_as * value, shown_as=shown_as)
        found["lane_reduction"] = case.lane_reduction
        arrangements.append(found)
    winner = max(arrangements, key=lambda found: found["total"])
    for found in arrangements:
        found["winner"] = found is winner
        if found is winner:
            found["label"] = "Critical: " + found["label"].split(": ", 1)[1]
    trials += arrangements
    return {"at_m": float(results.dead.total[girder].stations_m[results.stations[key]]), "trials": trials}
