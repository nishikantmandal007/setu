from setu.errors import VehicleDefinitionError, VehicleNotFoundError

REVERSED_SUFFIX = "_reversed"

# n axles need n - 1 spacings
def check_axle_and_spacing_counts_match(vehicle):
    axles = len(vehicle.axle_loads_t)
    spacings = len(vehicle.axle_spacing_m)
    if axles != spacings + 1:
        raise VehicleDefinitionError(f"{vehicle.name}: {axles} axle loads need {axles - 1} spacings between them, but {spacings} were given")

# every size and load of the vehicle, named, for checking
def every_measurement_of(vehicle):
    measurements = [
        ("transverse_gauge_m", vehicle.transverse_gauge_m),
        ("min_nose_to_tail_m", vehicle.min_nose_to_tail_m),
    ]
    if isinstance(vehicle, AxleVehicle):
        for index, axle_load_t in enumerate(vehicle.axle_loads_t):
            measurements.append((f"axle_loads_t[{index}]", axle_load_t))
        for index, spacing_m in enumerate(vehicle.axle_spacing_m):
            measurements.append((f"axle_spacing_m[{index}]", spacing_m))
    else:
        measurements.append(("load_per_track_t", vehicle.load_per_track_t))
        measurements.append(("track_length_m", vehicle.track_length_m))
        measurements.append(("track_width_m", vehicle.track_width_m))
    return measurements

# refuse a vehicle with a zero or negative size or load
def check_all_measurements_positive(vehicle):
    for description, value in every_measurement_of(vehicle):
        if value <= 0:
            raise VehicleDefinitionError(f"{vehicle.name}: {description} must be greater than zero, got {value}")


class AxleVehicle:
    # a wheeled vehicle: axle loads, spacings, gauge and clearances
    def __init__(self, name, axle_loads_t, axle_spacing_m, transverse_gauge_m, lead_clearance_m, trail_clearance_m, min_nose_to_tail_m):
        self.name = name
        self.axle_loads_t = axle_loads_t
        self.axle_spacing_m = axle_spacing_m
        self.transverse_gauge_m = transverse_gauge_m
        self.lead_clearance_m = lead_clearance_m
        self.trail_clearance_m = trail_clearance_m
        self.min_nose_to_tail_m = min_nose_to_tail_m
        check_axle_and_spacing_counts_match(self)
        check_all_measurements_positive(self)

    # nose to tail length
    def length_m(self):
        return self.lead_clearance_m + sum(self.axle_spacing_m) + self.trail_clearance_m

    # each axle's distance behind the first one
    def axle_positions_m(self):
        behind_the_first_axle_m = [0.0]
        for spacing_m in self.axle_spacing_m:
            behind_the_first_axle_m.append(behind_the_first_axle_m[-1] + spacing_m)
        return tuple(behind_the_first_axle_m)

    # all the axles added up
    def total_load_t(self):
        return sum(self.axle_loads_t)

class TrackedVehicle:
    # a tracked vehicle: load per track and the track size
    def __init__(self, name, load_per_track_t, track_length_m, track_width_m, transverse_gauge_m, min_nose_to_tail_m, lead_clearance_m=0.0, trail_clearance_m=0.0):
        self.name = name
        self.load_per_track_t = load_per_track_t
        self.track_length_m = track_length_m
        self.track_width_m = track_width_m
        self.transverse_gauge_m = transverse_gauge_m
        self.min_nose_to_tail_m = min_nose_to_tail_m
        self.lead_clearance_m = lead_clearance_m
        self.trail_clearance_m = trail_clearance_m
        check_all_measurements_positive(self)

    # track length
    def length_m(self):
        return self.track_length_m

    # both tracks
    def total_load_t(self):
        return 2.0 * self.load_per_track_t

CLASS_70R_WHEELED = AxleVehicle(
    name="Class_70R_Wheeled",
    axle_loads_t=(8, 12, 12, 17, 17, 17, 17),
    axle_spacing_m=(3.96, 1.52, 2.13, 1.37, 3.05, 1.37),
    transverse_gauge_m=2.06,
    lead_clearance_m=0.81,
    trail_clearance_m=0.91,
    min_nose_to_tail_m=28.28,
)
CLASS_70R_TRACKED = TrackedVehicle(
    name="Class_70R_Tracked",
    load_per_track_t=35.0,
    track_length_m=4.57,
    track_width_m=0.84,
    transverse_gauge_m=2.06,
    min_nose_to_tail_m=90.0,
)
CLASS_A = AxleVehicle(
    name="Class_A",
    axle_loads_t=(2.7, 2.7, 11.4, 11.4, 6.8, 6.8, 6.8, 6.8),
    axle_spacing_m=(1.1, 3.2, 1.2, 4.3, 3.0, 3.0, 3.0),
    transverse_gauge_m=1.8,
    lead_clearance_m=0.6,
    trail_clearance_m=0.9,
    min_nose_to_tail_m=18.5,
)
IRC_VEHICLES = {
    vehicle.name: vehicle for vehicle in (CLASS_70R_WHEELED, CLASS_70R_TRACKED, CLASS_A)
}
VEHICLES_ALLOWED_IN_BLOCK = {
    "class_a": ("Class_A",),
    "zone_70r": ("Class_70R_Wheeled", "Class_70R_Tracked"),
}

# vehicle name without the reversed suffix
def class_of(vehicle):
    return vehicle.name.removesuffix(REVERSED_SUFFIX)

# vehicle by name, or an error listing the known ones
def find_vehicle(name):
    if name not in IRC_VEHICLES:
        raise VehicleNotFoundError(f"no vehicle named {name!r}; known vehicles are {sorted(IRC_VEHICLES)}")
    return IRC_VEHICLES[name]

# the same vehicle driven the other way; a track is the same both ways
def facing_backwards(vehicle):
    if isinstance(vehicle, TrackedVehicle):
        return vehicle
    return AxleVehicle(
        name=f"{vehicle.name}{REVERSED_SUFFIX}",
        axle_loads_t=tuple(reversed(vehicle.axle_loads_t)),
        axle_spacing_m=tuple(reversed(vehicle.axle_spacing_m)),
        transverse_gauge_m=vehicle.transverse_gauge_m,
        lead_clearance_m=vehicle.trail_clearance_m,
        trail_clearance_m=vehicle.lead_clearance_m,
        min_nose_to_tail_m=vehicle.min_nose_to_tail_m,
    )

# vehicle by name, reversed ones included
def find_vehicle_or_its_reverse(name):
    if name in IRC_VEHICLES:
        return IRC_VEHICLES[name]
    facing_forwards = name.removesuffix(REVERSED_SUFFIX)
    if facing_forwards in IRC_VEHICLES:
        return facing_backwards(IRC_VEHICLES[facing_forwards])
    return find_vehicle(name)

# the vehicle, and its reverse when that is different
def both_directions_of(vehicle):
    reversed_vehicle = facing_backwards(vehicle)
    if reversed_vehicle is vehicle:
        return [vehicle]
    return [vehicle, reversed_vehicle]

# which vehicles may go in a Class A lane and in a 70R zone
def vehicles_allowed_in_each_block():
    return {block: [both_ways for name in names for both_ways in both_directions_of(find_vehicle(name))] for block, names in VEHICLES_ALLOWED_IN_BLOCK.items()}

# front to front distance of two vehicles in a train
def pitch_between_vehicles_m(vehicle):
    return vehicle.length_m() + vehicle.min_nose_to_tail_m

# most vehicles of a train that fit between from and to
def most_vehicles_that_fit(vehicle, from_m, to_m):
    pitch_m = pitch_between_vehicles_m(vehicle)
    return max(1, int((to_m - from_m) // pitch_m) + 1)
