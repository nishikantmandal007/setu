from __future__ import annotations

from .bridge_input import BridgeInput
from .deck_mesh import DeckMesh, station_at
from .model_tags import SolverCommands

# Which of the six degrees of freedom are held: x, y, z, then the three rotations.
PINNED = (1, 1, 1, 0, 0, 0)
ROLLER = (0, 1, 1, 0, 0, 0)
FREE_TO_MOVE_WITH_THE_DECK = (1, 0, 0, 1, 1, 1)


def tie_deck_to_girders(
    ops: SolverCommands, mesh: DeckMesh, deck_nodes: dict, girder_nodes: dict
) -> None:
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
    near_end = 0
    far_end = mesh.stations_along_span - 1

    for k in range(bridge.girders.count):
        ops.fix(girder_nodes[(k, near_end)], *PINNED)
        ops.fix(girder_nodes[(k, far_end)], *ROLLER)

    for tag in k_brace_nodes.values():
        ops.fix(tag, *FREE_TO_MOVE_WITH_THE_DECK)
