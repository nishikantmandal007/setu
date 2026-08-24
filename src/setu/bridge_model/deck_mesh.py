"""Dividing the deck into a grid of elements.

Along the span, a station at every bracing point with an even number of elements
between them, so a brace always lands on a node.

Across the width, a station at every line that matters - each girder, and every
boundary in the cross-section - with the gaps between filled to roughly the
requested size. That way a kerb line or a girder never falls in the middle of an
element, where the model could not represent it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..deck_cross_section import DeckCrossSection
from .inputs import BridgeInput

COORDINATE_DECIMALS = 5
"""Coordinates are rounded here so that a girder line and a mesh station that
should be the same place compare as the same place."""


@dataclass(frozen=True, eq=False)
class DeckMesh:
    """Where every line of the deck grid runs."""

    length_mesh_m: np.ndarray
    """Stations along the span."""

    width_mesh_m: np.ndarray
    """Stations across the width."""

    girder_lines_m: np.ndarray
    """Where each girder runs, across the width."""

    brace_lines_m: np.ndarray
    """Where each bracing station is, along the span."""

    @property
    def stations_along_span(self) -> int:
        return len(self.length_mesh_m)

    @property
    def stations_across_width(self) -> int:
        return len(self.width_mesh_m)

    @property
    def girder_spacing_m(self) -> float:
        return float(self.girder_lines_m[1] - self.girder_lines_m[0])

    def width_station_of_girder(self, girder: int) -> int:
        """Returns which width station a girder sits on.

        Every girder line is put into the mesh, so one always does.
        """
        on_this_station = np.where(
            np.isclose(self.width_mesh_m, self.girder_lines_m[girder], atol=1e-4)
        )[0]
        if len(on_this_station) == 0:
            raise ValueError(
                f"girder {girder} at z = {self.girder_lines_m[girder]:.4f} m does not land "
                "on a width mesh station, so the deck cannot be tied to it"
            )
        return int(on_this_station[0])


def build_mesh(bridge: BridgeInput) -> DeckMesh:
    """Returns the grid of stations the deck will be modelled on."""
    girder_lines_m = _round(
        np.linspace(
            bridge.deck.overhang_m,
            bridge.width_m - bridge.deck.overhang_m,
            bridge.girders.count,
        )
    )
    brace_lines_m = _round(np.linspace(0, bridge.span_m, bridge.bracing.station_count))

    return DeckMesh(
        length_mesh_m=_stations_along_span(brace_lines_m, bridge.mesh.panels_between_braces),
        width_mesh_m=_stations_across_width(
            bridge.cross_section, girder_lines_m, bridge.mesh.target_size_across_width_m
        ),
        girder_lines_m=girder_lines_m,
        brace_lines_m=brace_lines_m,
    )


def _stations_along_span(brace_lines_m: np.ndarray, panels_between_braces: int) -> np.ndarray:
    """Returns the mesh stations along the span, evenly filling each bracing panel."""
    stations_m: list[float] = []

    for panel_start_m, panel_end_m in zip(brace_lines_m, brace_lines_m[1:], strict=False):
        within_panel_m = np.linspace(panel_start_m, panel_end_m, panels_between_braces + 1)
        stations_m.extend(within_panel_m[:-1])

    stations_m.append(float(brace_lines_m[-1]))
    return _round(np.array(stations_m))


def _stations_across_width(
    cross_section: DeckCrossSection, girder_lines_m: np.ndarray, target_size_m: float
) -> np.ndarray:
    """Returns the mesh stations across the width, keeping every line that matters."""
    keep_these_m = [strip.z_from_m for strip in cross_section.strips]
    keep_these_m.append(cross_section.total_width_m)
    keep_these_m.extend(float(line) for line in girder_lines_m)
    lines_that_matter_m = np.unique(_round(np.array(keep_these_m)))

    stations_m: list[float] = []
    for panel_start_m, panel_end_m in zip(
        lines_that_matter_m, lines_that_matter_m[1:], strict=False
    ):
        elements = max(1, int(np.ceil((panel_end_m - panel_start_m) / target_size_m)))
        within_panel_m = np.linspace(panel_start_m, panel_end_m, elements + 1)
        stations_m.extend(within_panel_m[:-1])

    stations_m.append(float(lines_that_matter_m[-1]))
    return np.unique(_round(np.array(stations_m)))


def _round(values: np.ndarray) -> np.ndarray:
    return np.round(values, COORDINATE_DECIMALS)
