from setu.helpers import import_opensees


class OpenSeesBackend:

    ADJOINT_PATTERN = 7
    ADJOINT_TIME_SERIES = 7

    # the backend on top of openseespy
    def __init__(self):
        self.ops = import_opensees()
        self._analysis_configured = False

    # put the loads on one pattern and solve once
    def solve_with_loads(self, loads, pattern=None):
        tag = pattern if pattern is not None else self.ADJOINT_PATTERN
        ts = self.ADJOINT_TIME_SERIES
        self.ops.remove("loadPattern", tag)
        self.ops.remove("timeSeries", ts)
        self.ops.timeSeries("Linear", ts)
        self.ops.pattern("Plain", tag, ts)
        for node, forces in loads:
            self.ops.load(node, *forces)
        self.ops.reset()
        if not self._analysis_configured:
            configure_linear_static(self.ops)
            self._analysis_configured = True
        self.ops.setTime(0.0)
        self.ops.analyze(1)

    # displacement of one node in one dof
    def node_displacement(self, node, dof):
        return self.ops.nodeDisp(node, dof)

    # the nodes of an element
    def element_nodes(self, element):
        return tuple(self.ops.eleNodes(element))

    # where a node is
    def node_coordinates(self, node):
        return self.ops.nodeCoord(node)

    # displacements of every node
    def every_node_displacement(self):
        return {node: self.ops.nodeDisp(node) for node in self.ops.getNodeTags()}

    # remove the load pattern and reset
    def clear_loads(self):
        self.ops.remove("loadPattern", self.ADJOINT_PATTERN)
        self.ops.remove("timeSeries", self.ADJOINT_TIME_SERIES)
        self.ops.reset()
        self.ops.setTime(0.0)

# one linear static step, stiffness factored once
def configure_linear_static(ops):
    ops.wipeAnalysis()
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear", "-factorOnce")
    ops.analysis("Static")
