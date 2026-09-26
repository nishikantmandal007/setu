import numpy as np
from setu.utils.constants import LOAD_CASE_PATTERN_BASE


LOAD_CASE_TIME_SERIES_BASE = 100


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


# factored sum of load cases as one load case
def combine(cases, factors):
    merged_nodal = {}
    for case, factor in zip(cases, factors):
        for node, fx, fy, fz, mx, my, mz in case.nodal_loads:
            if node not in merged_nodal:
                merged_nodal[node] = np.zeros(6)
            merged_nodal[node] += factor * np.array([fx, fy, fz, mx, my, mz])
    merged_element = {}
    for case, factor in zip(cases, factors):
        for element, load_type, parameters in case.element_loads:
            key = (element, load_type)
            if key not in merged_element:
                merged_element[key] = np.zeros(len(parameters))
            merged_element[key] += factor * np.array(parameters)
    nodal_loads = [(node, *forces) for node, forces in merged_nodal.items()]
    element_loads = [(el, lt, tuple(params)) for (el, lt), params in merged_element.items()]
    names = [c.name for c in cases]
    return LoadCase(name=" + ".join(names), nodal_loads=nodal_loads, element_loads=element_loads)
