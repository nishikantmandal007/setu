# The OpenSeesPy backend - the only module in setu that imports openseespy. The import
# happens inside the functions rather than at the top, so `import setu` works and stays
# fast on a machine without openseespy. Everything except the actual solving can then be
# used, and tested, with no solver installed at all.

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..errors import BackendError

# Load pattern tag setu reserves for its own solves.
ADJOINT_PATTERN = 7

# Time series tag setu reserves for its own solves. setu creates this itself rather than
# borrowing whichever series the caller happened to define, so an influence surface can be
# solved on a model that has had no loads applied to it at all.
ADJOINT_TIME_SERIES = 7

# Global Y, the vertical direction.
VERTICAL_DOF = 2


def import_opensees() -> Any:
    try:
        import openseespy.opensees as ops
    except ImportError as missing:
        raise BackendError(
            "openseespy is not installed, so setu cannot solve. "
            "Install it with `pip install setu[fe]`."
        ) from missing
    return ops


class OpenSeesBackend:
    # Drives the OpenSeesPy model that is currently built.

    def __init__(self, reuse_analysis: bool = False) -> None:
        # Keep the solver objects alive between solves and only swap the load. Identical
        # results, about 15 per cent faster per solve. Only safe when nothing else
        # reconfigures the analysis between calls, so it is off by default.
        self.reuse_analysis = reuse_analysis
        self._analysis_is_configured = False

    def solve_with_loads(
        self, loads: Sequence[tuple[int, Sequence[float]]], pattern: int | None = None
    ) -> None:
        ops = import_opensees()
        pattern = ADJOINT_PATTERN if pattern is None else pattern

        # Cleared and remade every time, so that solving twice on the same model behaves
        # exactly like solving once on a fresh one.
        ops.remove("loadPattern", pattern)
        ops.remove("timeSeries", ADJOINT_TIME_SERIES)
        ops.timeSeries("Linear", ADJOINT_TIME_SERIES)
        ops.pattern("Plain", pattern, ADJOINT_TIME_SERIES)
        for node, components in loads:
            ops.load(node, *[float(component) for component in components])

        # Every one of remove, pattern, reset, wipeAnalysis and setTime is needed. Without
        # reset() the displacements committed by the previous solve are still there, and
        # this solve silently returns the sum of both.
        ops.reset()

        if not (self.reuse_analysis and self._analysis_is_configured):
            self.configure_analysis(ops)

        ops.setTime(0.0)
        ops.analyze(1)

    def configure_analysis(self, ops: Any) -> None:
        ops.wipeAnalysis()
        ops.system("UmfPack")
        ops.numberer("RCM")
        ops.constraints("Transformation")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")
        self._analysis_is_configured = True

    def node_displacement(self, node: int, dof: int) -> float:
        return import_opensees().nodeDisp(node, dof)

    def element_nodes(self, element: int) -> tuple[int, int]:
        node_i, node_j = import_opensees().eleNodes(element)
        return node_i, node_j

    def node_coordinates(self, node: int) -> Sequence[float]:
        return import_opensees().nodeCoord(node)

    # Removes setu's load pattern. Displacements already solved are kept.
    def clear_loads(self) -> None:
        import_opensees().remove("loadPattern", ADJOINT_PATTERN)
