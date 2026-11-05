from functools import cached_property

import numpy as np

from setu.solver import backend
from setu.utils.constants import LOAD_CASE_PATTERN_BASE


class LoadCase:

    # a named set of nodal and element loads
    def __init__(self, name, nodal_loads=None, element_loads=None):
        self.name = name
        self.nodal_loads = nodal_loads or []
        self.element_loads = element_loads or []

    # the loaded nodes and their six force terms as arrays, built once: a load case does not change after it is made
    @cached_property
    def nodal_arrays(self):
        nodes = np.array([load[0] for load in self.nodal_loads], int)
        forces = np.array([load[1:] for load in self.nodal_loads], float).reshape((-1, 6))
        return nodes, forces


# one force direction on many nodes, kept as arrays: reading it by reciprocity never builds the per-node tuples
class ArrayLoadCase(LoadCase):
    def __init__(self, name, nodes, forces):
        self.name = name
        self.nodal_arrays = (nodes, forces)
        self.element_loads = []

    # the same loads as LoadCase's list, for the solver
    @cached_property
    def nodal_loads(self):
        nodes, forces = self.nodal_arrays
        return [(node, *force) for node, force in zip(nodes.tolist(), forces.tolist())]


# put a load case on the model as one pattern
def apply_load_case(load_case, pattern_tag=None):
    tag = pattern_tag if pattern_tag is not None else LOAD_CASE_PATTERN_BASE
    backend.apply_loads(load_case.nodal_loads, load_case.element_loads, pattern=tag)
