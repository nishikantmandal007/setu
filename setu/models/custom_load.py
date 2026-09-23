from setu.utils.constants import CUSTOM_LOAD_GROUPS

POINT = "point"
LINE = "line"
AREA = "area"


class CustomLoad:
    def __init__(self, group, shape, magnitude, x_from_bearing_m, z_from_left_edge_m, x_end_m=None, z_end_m=None, name=None, **kwargs):
        self.group = CUSTOM_LOAD_GROUPS.get(group, group)
        self.shape = shape
        self.magnitude = magnitude
        self.x_from_bearing_m = x_from_bearing_m
        self.z_from_left_edge_m = z_from_left_edge_m
        self.x_end_m = x_end_m
        self.z_end_m = z_end_m
        self.name = name or f"{group} {shape}"

    def to_dict(self):
        return self.__dict__
