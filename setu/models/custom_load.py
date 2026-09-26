from setu.utils.constants import AREA, CUSTOM_LOAD_GROUPS, LINE, POINT


class CustomLoad:
    # a user load from OsdagBridge: point (kN), line (kN/m) or area (kPa); line and area also need where they end
    def __init__(self, group, shape, magnitude, x_from_bearing_m, z_from_left_edge_m, x_end_m=None, z_end_m=None):
        if shape not in (POINT, LINE, AREA):
            raise ValueError(f"a custom load is a {POINT}, {LINE} or {AREA} load, got {shape!r}")
        if shape != POINT and (x_end_m is None or z_end_m is None):
            raise ValueError(f"a {shape} custom load in group {group!r} needs x_end_m and z_end_m")
        self.group = CUSTOM_LOAD_GROUPS.get(group, group)
        self.shape = shape
        self.magnitude = magnitude
        self.x_from_bearing_m = x_from_bearing_m
        self.z_from_left_edge_m = z_from_left_edge_m
        self.x_end_m = x_end_m
        self.z_end_m = z_end_m

