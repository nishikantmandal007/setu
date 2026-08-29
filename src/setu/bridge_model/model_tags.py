# Where a bridge model's node and element tags come from.
#
# Every part of the model - deck, girders, brace nodes, bracing elements - occupies a
# contiguous block of solver tags, one block laid immediately after the block before it.
# Each function below returns the first tag of its own block, worked out from the size of
# every block that came before it, so the whole tag space is contiguous by construction and
# there is exactly one place that does this arithmetic, instead of it being rebuilt by hand
# wherever a block is placed.
#
# i = station along span, j = station across width, k = girder, n = bracing line

from __future__ import annotations

from typing import Any

from .bridge_input import BridgeInput
from .deck_mesh import DeckMesh

# The openseespy module itself, passed in rather than imported so the solver stays
# swappable and openseespy stays an optional dependency. Genuinely Any - it is a module of
# 27 variadic commands, and a Protocol for it would be fiction mypy cannot check.
SolverCommands = Any

DECK_NODE_BASE = 1000
DECK_ELEMENT_BASE = 1000
DECK_SECTION = 1
GIRDER_TRANSFORM = 1
BRACE_MATERIAL = 10

# Puts the girder's local y axis on global Y, so vertical bending is resisted by the strong
# axis. It was once (0, 1, 0), which quietly handed vertical bending to the girder's weak
# axis instead - a stiffness 42 times too small.
GIRDER_LOCAL_AXIS = (0.0, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Node Tag Bases
# ---------------------------------------------------------------------------


def first_girder_node_tag(mesh: DeckMesh) -> int:
    # One deck node at every (station along span, station across width), starting at
    # DECK_NODE_BASE.
    return DECK_NODE_BASE + mesh.stations_along_span * mesh.stations_across_width


def first_bottom_brace_node_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    # One girder node at every (girder, station along span), after the deck nodes.
    return first_girder_node_tag(mesh) + bridge.girders.count * mesh.stations_along_span


def first_top_brace_node_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    # One bottom brace node at every (girder, bracing station), after the girder nodes.
    nodes_per_block = bridge.girders.count * bridge.bracing.station_count
    return first_bottom_brace_node_tag(bridge, mesh) + nodes_per_block


def first_k_brace_node_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    # One top brace node at every (girder, bracing station), after the bottom brace nodes.
    nodes_per_block = bridge.girders.count * bridge.bracing.station_count
    return first_top_brace_node_tag(bridge, mesh) + nodes_per_block


# ---------------------------------------------------------------------------
# Element Tag Bases
# ---------------------------------------------------------------------------


def first_girder_element_tag(mesh: DeckMesh) -> int:
    # One deck shell in every square of the mesh grid, starting at DECK_ELEMENT_BASE.
    panels = (mesh.stations_along_span - 1) * (mesh.stations_across_width - 1)
    return DECK_ELEMENT_BASE + panels


def first_brace_element_tag(bridge: BridgeInput, mesh: DeckMesh) -> int:
    # One girder beam between every pair of stations, on every girder, after the deck shells.
    beams_per_girder = mesh.stations_along_span - 1
    return first_girder_element_tag(mesh) + bridge.girders.count * beams_per_girder
