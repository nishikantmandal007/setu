from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..deck_cross_section import DeckCrossSection
from .bridge_input import BridgeInput

# Not the same as irc_code_rules.code_tables.ROUND_TO_DECIMALS (9): the two round different
# things for different reasons, and changing either changes results.
COORDINATE_DECIMALS = 5

# Deliberately looser than the tolerance station_at uses, so do not unify the two.
GIRDER_LANDS_ON_A_STATION_M = 1e-4


@dataclass(frozen=True, eq=False)
class DeckMesh:
    length_mesh_m: np.ndarray
    width_mesh_m: np.ndarray
    girder_lines_m: np.ndarray
    brace_lines_m: np.ndarray

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
        girder_line_m = self.girder_lines_m[girder]
        on_this_station = np.where(
            np.isclose(self.width_mesh_m, girder_line_m, atol=GIRDER_LANDS_ON_A_STATION_M)
        )[0]

        if len(on_this_station) == 0:
            raise ValueError(
                f"girder {girder} at z = {girder_line_m:.4f} m does not land "
                "on a width mesh station, so the deck cannot be tied to it"
            )
        return int(on_this_station[0])


def station_at(stations_m: np.ndarray, position_m: float) -> int:
    found = np.where(np.isclose(stations_m, position_m))[0]
    if len(found) == 0:
        raise ValueError(f"no mesh station at {position_m:.5f} m")
    return int(found[0])


def build_mesh(bridge: BridgeInput) -> DeckMesh:
    girder_lines_m = rounded(
        np.linspace(
            bridge.deck.overhang_m,
            bridge.width_m - bridge.deck.overhang_m,
            bridge.girders.count,
        )
    )
    brace_lines_m = rounded(np.linspace(0, bridge.span_m, bridge.bracing.station_count))

    return DeckMesh(
        length_mesh_m=stations_along_span(brace_lines_m, bridge.mesh.panels_between_braces),
        width_mesh_m=stations_across_width(
            bridge.cross_section, girder_lines_m, bridge.mesh.target_size_across_width_m
        ),
        girder_lines_m=girder_lines_m,
        brace_lines_m=brace_lines_m,
    )


def stations_along_span(brace_lines_m: np.ndarray, panels_between_braces: int) -> np.ndarray:
    # A station at every bracing point, so a brace always lands on a node.
    stations_m: list[float] = []

    for panel_start_m, panel_end_m in zip(brace_lines_m, brace_lines_m[1:], strict=False):
        within_panel_m = np.linspace(panel_start_m, panel_end_m, panels_between_braces + 1)
        stations_m.extend(within_panel_m[:-1])

    stations_m.append(float(brace_lines_m[-1]))
    return rounded(np.array(stations_m))


def lines_that_matter_across_width(
    cross_section: DeckCrossSection, girder_lines_m: np.ndarray
) -> np.ndarray:
    keep_these_m = [strip.z_from_m for strip in cross_section.strips]
    keep_these_m.append(cross_section.total_width_m)
    keep_these_m.extend(float(line) for line in girder_lines_m)

    return np.unique(rounded(np.array(keep_these_m)))


def stations_across_width(
    cross_section: DeckCrossSection, girder_lines_m: np.ndarray, target_size_m: float
) -> np.ndarray:
    # Every girder line and cross-section boundary is kept, so neither can fall in the
    # middle of an element where the model could not represent it.
    lines_m = lines_that_matter_across_width(cross_section, girder_lines_m)

    stations_m: list[float] = []
    for panel_start_m, panel_end_m in zip(lines_m, lines_m[1:], strict=False):
        panel_width_m = panel_end_m - panel_start_m
        elements = max(1, int(np.ceil(panel_width_m / target_size_m)))

        within_panel_m = np.linspace(panel_start_m, panel_end_m, elements + 1)
        stations_m.extend(within_panel_m[:-1])

    stations_m.append(float(lines_m[-1]))
    return np.unique(rounded(np.array(stations_m)))


def rounded(values: np.ndarray) -> np.ndarray:
    return np.round(values, COORDINATE_DECIMALS)
