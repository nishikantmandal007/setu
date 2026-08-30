from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..errors import BackendError

ADJOINT_PATTERN = 7
ADJOINT_TIME_SERIES = 7

VERTICAL_DOF = 2

ONE_LOAD_STEP = 1
START_OF_THE_LOAD_STEP = 0.0
FULL_LOAD_FACTOR = 1.0


def import_opensees() -> Any:
    # Imported here, not at the top, so `import setu` works without openseespy installed.
    try:
        import openseespy.opensees as ops
    except ImportError as missing:
        raise BackendError(
            "openseespy is not installed, so setu cannot solve. "
            "Install it with `pip install setu[fe]`."
        ) from missing
    return ops


class OpenSeesBackend:
    def __init__(self, reuse_analysis: bool = False) -> None:
        self.reuse_analysis = reuse_analysis
        self._analysis_is_configured = False

    def solve_with_loads(
        self, loads: Sequence[tuple[int, Sequence[float]]], pattern: int | None = None
    ) -> None:
        ops = import_opensees()
        pattern = ADJOINT_PATTERN if pattern is None else pattern

        self.apply_loads(ops, loads, pattern)

        # Every one of remove, reset, wipeAnalysis and setTime is needed. Without reset()
        # the previous solve's displacements are still committed and this one returns both.
        ops.reset()

        if not (self.reuse_analysis and self._analysis_is_configured):
            self.configure_analysis(ops)

        ops.setTime(START_OF_THE_LOAD_STEP)
        ops.analyze(ONE_LOAD_STEP)

    def apply_loads(
        self, ops: Any, loads: Sequence[tuple[int, Sequence[float]]], pattern: int
    ) -> None:
        ops.remove("loadPattern", pattern)
        ops.remove("timeSeries", ADJOINT_TIME_SERIES)
        ops.timeSeries("Linear", ADJOINT_TIME_SERIES)
        ops.pattern("Plain", pattern, ADJOINT_TIME_SERIES)

        for node, components in loads:
            ops.load(node, *[float(component) for component in components])

    def configure_analysis(self, ops: Any) -> None:
        ops.wipeAnalysis()
        ops.system("UmfPack")
        ops.numberer("RCM")
        ops.constraints("Transformation")
        ops.integrator("LoadControl", FULL_LOAD_FACTOR)
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

    def clear_loads(self) -> None:
        import_opensees().remove("loadPattern", ADJOINT_PATTERN)
