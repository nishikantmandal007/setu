# Building every element the bridge model needs: the deck shells, the girder beams, and
# the truss members that make up the cross bracing.

from __future__ import annotations

from typing import TYPE_CHECKING

from .bridge_input import BridgeInput
from .deck_mesh import DeckMesh
from .girder_sections import GirderProperties
from .model_tags import (
    BRACE_MATERIAL,
    DECK_ELEMENT_BASE,
    DECK_SECTION,
    GIRDER_LOCAL_AXIS,
    GIRDER_TRANSFORM,
    SolverCommands,
    first_brace_element_tag,
    first_girder_element_tag,
)

if TYPE_CHECKING:
    # Only for the type hints below - importing BridgeModel at runtime would be circular,
    # since build_model.py imports build_bracing from here.
    from .build_model import BridgeModel


def build_deck_shells(
    ops: SolverCommands, bridge: BridgeInput, mesh: DeckMesh, deck_nodes: dict
) -> dict[tuple[int, int], int]:
    # A shell element in every square of the deck grid.
    ops.section(
        "ElasticMembranePlateSection",
        DECK_SECTION,
        bridge.concrete.elastic_modulus_kpa,
        bridge.concrete.poissons_ratio,
        bridge.deck.thickness_m,
    )

    elements = {}
    tag = DECK_ELEMENT_BASE
    for i in range(mesh.stations_along_span - 1):
        for j in range(mesh.stations_across_width - 1):
            ops.element(
                "ShellMITC4",
                tag,
                deck_nodes[(i, j)],
                deck_nodes[(i + 1, j)],
                deck_nodes[(i + 1, j + 1)],
                deck_nodes[(i, j + 1)],
                DECK_SECTION,
            )
            elements[(i, j)] = tag
            tag += 1

    return elements


def build_girder_beams(
    ops: SolverCommands,
    bridge: BridgeInput,
    mesh: DeckMesh,
    girder: GirderProperties,
    girder_nodes: dict,
) -> dict[tuple[int, int], int]:
    # A beam element between every pair of stations, on every girder.
    ops.geomTransf("Linear", GIRDER_TRANSFORM, *GIRDER_LOCAL_AXIS)

    tag = first_girder_element_tag(mesh)
    elements = {}

    for k in range(bridge.girders.count):
        for i in range(mesh.stations_along_span - 1):
            ops.element(
                "elasticBeamColumn",
                tag,
                girder_nodes[(k, i)],
                girder_nodes[(k, i + 1)],
                girder.area_m2,
                bridge.steel.elastic_modulus_kpa,
                bridge.steel.shear_modulus_kpa,
                girder.torsion_constant_m4,
                girder.weak_axis_inertia_m4,
                girder.strong_axis_inertia_m4,
                GIRDER_TRANSFORM,
            )
            elements[(k, i)] = tag
            tag += 1

    return elements


def build_bracing(
    ops: SolverCommands, bridge: BridgeInput, mesh: DeckMesh, model: BridgeModel
) -> dict[tuple[int, int, str], int]:
    # Truss members between neighbouring girders at each bracing station.
    ops.uniaxialMaterial("Elastic", BRACE_MATERIAL, bridge.steel.elastic_modulus_kpa)

    tag = first_brace_element_tag(bridge, mesh)
    elements: dict[tuple[int, int, str], int] = {}

    for n in range(bridge.bracing.station_count):
        for k in range(bridge.girders.count - 1):
            corners = brace_panel_corners(model, k, n)
            for role, (start, end) in brace_members(bridge, model, corners, k, n):
                ops.element(
                    "corotTruss", tag, start, end, bridge.bracing.area_m2, BRACE_MATERIAL
                )
                elements[(k, n, role)] = tag
                tag += 1

    return elements


def brace_panel_corners(model: BridgeModel, k: int, n: int) -> dict[str, int]:
    return {
        "top_left": model.top_brace_nodes[(k, n)],
        "top_right": model.top_brace_nodes[(k + 1, n)],
        "bottom_left": model.bottom_brace_nodes[(k, n)],
        "bottom_right": model.bottom_brace_nodes[(k + 1, n)],
    }


def brace_members(
    bridge: BridgeInput, model: BridgeModel, corners: dict[str, int], k: int, n: int
) -> list[tuple[str, tuple[int, int]]]:
    # Returns which members make up one bracing panel, and what to call each.
    members: list[tuple[str, tuple[int, int]]] = []

    if bridge.bracing.is_x_braced:
        members.append(("diagonal_down", (corners["top_left"], corners["bottom_right"])))
        members.append(("diagonal_up", (corners["top_right"], corners["bottom_left"])))
    elif bridge.bracing.is_k_braced:
        meeting_point = model.k_brace_nodes[(k, n)]
        members.append(("k_top_left", (corners["top_left"], meeting_point)))
        members.append(("k_top_right", (corners["top_right"], meeting_point)))
        members.append(("k_bottom_left", (corners["bottom_left"], meeting_point)))
        members.append(("k_bottom_right", (meeting_point, corners["bottom_right"])))

    if bridge.bracing.has_top_chord:
        members.append(("top_chord", (corners["top_left"], corners["top_right"])))
    if bridge.bracing.has_bottom_chord:
        members.append(("bottom_chord", (corners["bottom_left"], corners["bottom_right"])))

    return members
