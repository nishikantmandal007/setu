from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class FEBackend(Protocol):
    # solve_with_loads must be safe to call again and again: setu solves once per response
    # quantity off the same model, so state leaking between solves corrupts every answer.
    def solve_with_loads(
        self, loads: Sequence[tuple[int, Sequence[float]]], pattern: int | None = None
    ) -> None: ...

    def node_displacement(self, node: int, dof: int) -> float: ...

    def element_nodes(self, element: int) -> tuple[int, int]: ...

    def node_coordinates(self, node: int) -> Sequence[float]: ...

    def clear_loads(self) -> None: ...
