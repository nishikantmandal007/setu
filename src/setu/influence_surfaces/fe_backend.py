"""The four things setu needs from a finite element solver.

This is the seam. Everything above it works in node tags and numbers, so
swapping OpenSeesPy for another solver means writing one class that answers
these four questions - and changing nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class FEBackend(Protocol):
    """A solver setu can drive."""

    def solve_with_loads(
        self, loads: Sequence[tuple[int, Sequence[float]]], pattern: int | None = None
    ) -> None:
        """Applies one load case and solves it statically.

        `loads` is (node tag, six force and moment components) per loaded node.

        This has to be safe to call again and again. setu solves once per
        response quantity and reads the answer off the same model each time, so
        a backend that lets state leak from one solve into the next gives wrong
        answers everywhere downstream, silently.
        """
        ...

    def node_displacement(self, node: int, dof: int) -> float:
        """Returns one degree of freedom of one node, from the last solve."""
        ...

    def element_nodes(self, element: int) -> tuple[int, int]:
        """Returns the two end nodes of an element."""
        ...

    def node_coordinates(self, node: int) -> Sequence[float]:
        """Returns the position of a node."""
        ...

    def clear_loads(self) -> None:
        """Removes the loads setu applied, leaving the model as it was found.

        Called once the answer has been read, so that whatever the caller does
        with the model next is not quietly carrying setu's imaginary load.
        """
        ...
