# Tying the deck to the girders, the girders to their own bracing, and then supporting
# the whole thing.

from __future__ import annotations

from .bridge_input import BridgeInput
from .deck_mesh import DeckMesh, station_at
from .model_tags import SolverCommands


def tie_deck_to_girders(
    ops: SolverCommands, mesh: DeckMesh, deck_nodes: dict, girder_nodes: dict
) -> None:
    # Rigid links carrying the slab on the girders, girder as master - so the slab is
    # carried by the girders rather than the other way round.
    for k in range(len(mesh.girder_lines_m)):
        j = mesh.width_station_of_girder(k)
        for i in range(mesh.stations_along_span):
            ops.rigidLink("beam", girder_nodes[(k, i)], deck_nodes[(i, j)])


def tie_braces_to_girders(
    ops: SolverCommands,
    bridge: BridgeInput,
    mesh: DeckMesh,
    girder_nodes: dict,
    bottom_brace_nodes: dict,
    top_brace_nodes: dict,
) -> None:
    # Rigid links from each girder out to its own brace nodes above and below.

    for k in range(bridge.girders.count):
        for n, x_m in enumerate(mesh.brace_lines_m):
            i = station_at(mesh.length_mesh_m, x_m)
            ops.rigidLink("beam", girder_nodes[(k, i)], bottom_brace_nodes[(k, n)])
            ops.rigidLink("beam", girder_nodes[(k, i)], top_brace_nodes[(k, n)])


def support_the_girders(
    ops: SolverCommands,
    bridge: BridgeInput,
    mesh: DeckMesh,
    girder_nodes: dict,
    k_brace_nodes: dict,
) -> None:
    # Pinned at the near end of every girder, roller at the far end.
    last = mesh.stations_along_span - 1

    for k in range(bridge.girders.count):
        ops.fix(girder_nodes[(k, 0)], 1, 1, 1, 0, 0, 0)
        ops.fix(girder_nodes[(k, last)], 0, 1, 1, 0, 0, 0)

    # A K bracing meeting point is held against everything except moving with the deck
    # sideways and vertically; it is a joint, not a support.
    for tag in k_brace_nodes.values():
        ops.fix(tag, 1, 0, 0, 1, 1, 1)
