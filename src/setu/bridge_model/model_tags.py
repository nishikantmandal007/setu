from __future__ import annotations

from typing import Any

from .bridge_input import BridgeInput
from .deck_mesh import DeckMesh

# The openseespy module, passed in rather than imported so the solver stays swappable.
SolverCommands = Any

DECK_NODE_BASE = 1000
DECK_ELEMENT_BASE = 1000
DECK_SECTION = 1
GIRDER_TRANSFORM = 1
BRACE_MATERIAL = 10

DIMENSIONS = 3
DEGREES_OF_FREEDOM_PER_NODE = 6

# Puts the girder's local y axis on global Y, so vertical bending is resisted by the
# strong axis.
GIRDER_LOCAL_AXIS = (0.0, 0.0, 1.0)


def deck_node_count(mesh: DeckMesh) -> int:
    return mesh.stations_along_span * mesh.stations_across_width


def girder_node_count(bridge: BridgeInput, mesh: DeckMesh) -> int:
    return bridge.girders.count * mesh.stations_along_span


def brace_node_count(bridge: BridgeInput) -> int:
    return bridge.girders.count * bridge.bracing.station_count


def first_girder_node_tag(mesh: DeckMesh) -> int:
    return DECK_NODE_BASE + deck_node_count(mesh)


def first_bottom_brace_node_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    return first_girder_node_tag(mesh) + girder_node_count(bridge, mesh)


def first_top_brace_node_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    return first_bottom_brace_node_tag(bridge, mesh) + brace_node_count(bridge)


def first_k_brace_node_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    return first_top_brace_node_tag(bridge, mesh) + brace_node_count(bridge)


def deck_panel_count(mesh: DeckMesh) -> int:
    return (mesh.stations_along_span - 1) * (mesh.stations_across_width - 1)


def first_girder_element_tag(mesh: DeckMesh) -> int:
    return DECK_ELEMENT_BASE + deck_panel_count(mesh)


def first_brace_element_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    beams_per_girder = mesh.stations_along_span - 1
    return first_girder_element_tag(mesh) + bridge.girders.count * beams_per_girder
