from setu.utils.constants import LOAD_CASE_PATTERN_BASE


class LoadCase:

    # a named set of nodal and element loads
    def __init__(self, name, nodal_loads=None, element_loads=None):
        self.name = name
        self.nodal_loads = nodal_loads or []
        self.element_loads = element_loads or []


# put a load case on the model as one pattern
def apply_load_case(load_case, ops, pattern_tag=None):
    tag = pattern_tag if pattern_tag is not None else LOAD_CASE_PATTERN_BASE
    ops.timeSeries("Constant", tag)
    ops.pattern("Plain", tag, tag)
    for node, fx, fy, fz, mx, my, mz in load_case.nodal_loads:
        ops.load(node, fx, fy, fz, mx, my, mz)
    for element, load_type, parameters in load_case.element_loads:
        ops.eleLoad("-ele", element, "-type", load_type, *parameters)


