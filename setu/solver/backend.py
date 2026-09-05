from setu.errors import BackendError


class FEBackend:

    def solve_with_loads(self, loads, pattern=None):
        raise NotImplementedError

    def node_displacement(self, node, dof):
        raise NotImplementedError

    def element_nodes(self, element):
        raise NotImplementedError

    def node_coordinates(self, node):
        raise NotImplementedError

    def clear_loads(self):
        raise NotImplementedError

class OpenSeesBackend(FEBackend):

    ADJOINT_PATTERN = 7
    ADJOINT_TIME_SERIES = 7

    def __init__(self):
        self.ops = import_opensees()
        self._analysis_configured = False

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
            self.ops.wipeAnalysis()
            self.ops.system("UmfPack")
            self.ops.numberer("RCM")
            self.ops.constraints("Transformation")
            self.ops.integrator("LoadControl", 1.0)
            self.ops.algorithm("Linear")
            self.ops.analysis("Static")
            self._analysis_configured = True
        self.ops.setTime(0.0)
        self.ops.analyze(1)

    def node_displacement(self, node, dof):
        return self.ops.nodeDisp(node, dof)

    def element_nodes(self, element):
        return tuple(self.ops.eleNodes(element))

    def node_coordinates(self, node):
        return self.ops.nodeCoord(node)

    def element_forces(self, element):
        return self.ops.eleResponse(element, "localForce")

    def node_reaction(self, node):
        return self.ops.nodeReaction(node)

    def clear_loads(self):
        self.ops.remove("loadPattern", self.ADJOINT_PATTERN)

def import_opensees():
    try:
        import openseespy.opensees as ops
        return ops
    except ImportError as e:
        raise BackendError("openseespy is not installed") from e
