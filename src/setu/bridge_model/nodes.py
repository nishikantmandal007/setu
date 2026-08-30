from __future__ import annotations

from .bridge_input import BridgeInput
from .deck_mesh import DeckMesh
from .girder_sections import GirderProperties
from .model_tags import (
    DECK_NODE_BASE,
    SolverCommands,
    first_bottom_brace_node_tag,
    first_girder_node_tag,
    first_k_brace_node_tag,
    first_top_brace_node_tag,
)


def place_deck_nodes(ops: SolverCommands, mesh: DeckMesh) -> dict[tuple[int, int], int]:
    deck_level_m = 0.0
    nodes = {}

    for i, x_m in enumerate(mesh.length_mesh_m):
        for j, z_m in enumerate(mesh.width_mesh_m):
            tag = DECK_NODE_BASE + i * mesh.stations_across_width + j
            ops.node(tag, float(x_m), deck_level_m, float(z_m))
            nodes[(i, j)] = tag

    return nodes


def place_girder_nodes(
    ops: SolverCommands, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties
) -> dict[tuple[int, int], int]:
    base = first_girder_node_tag(mesh)
    level_m = girder_centroid_level_m(bridge, girder)

    nodes = {}
    for k, z_m in enumerate(mesh.girder_lines_m):
        for i, x_m in enumerate(mesh.length_mesh_m):
            tag = base + k * mesh.stations_along_span + i
            ops.node(tag, float(x_m), level_m, float(z_m))
            nodes[(k, i)] = tag

    return nodes


def place_brace_nodes(
    ops: SolverCommands, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties
) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
    stations = bridge.bracing.station_count

    bottom_base = first_bottom_brace_node_tag(bridge, mesh)
    top_base = first_top_brace_node_tag(bridge, mesh)

    centroid_m = girder_centroid_level_m(bridge, girder)
    bottom_m = centroid_m - girder.neutral_axis_from_bottom_m
    top_m = centroid_m + (girder.depth_m - girder.neutral_axis_from_bottom_m)

    bottom_nodes, top_nodes = {}, {}
    for k, z_m in enumerate(mesh.girder_lines_m):
        for n, x_m in enumerate(mesh.brace_lines_m):
            bottom_tag = bottom_base + k * stations + n
            ops.node(bottom_tag, float(x_m), bottom_m, float(z_m))
            bottom_nodes[(k, n)] = bottom_tag

            top_tag = top_base + k * stations + n
            ops.node(top_tag, float(x_m), top_m, float(z_m))
            top_nodes[(k, n)] = top_tag

    return bottom_nodes, top_nodes


def place_k_brace_nodes(
    ops: SolverCommands, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties
) -> dict[tuple[int, int], int]:
    if not bridge.bracing.is_k_braced:
        return {}

    girders = bridge.girders.count
    base = first_k_brace_node_tag(bridge, mesh)
    level_m = girder_centroid_level_m(bridge, girder) - girder.neutral_axis_from_bottom_m

    nodes = {}
    for n, x_m in enumerate(mesh.brace_lines_m):
        for k in range(girders - 1):
            between_girders_m = 0.5 * (mesh.girder_lines_m[k] + mesh.girder_lines_m[k + 1])
            tag = base + n * (girders - 1) + k
            ops.node(tag, float(x_m), level_m, float(between_girders_m))
            nodes[(k, n)] = tag

    return nodes


def girder_centroid_level_m(bridge: BridgeInput, girder: GirderProperties) -> float:
    top_of_girder_to_centroid_m = girder.depth_m - girder.neutral_axis_from_bottom_m
    return -(top_of_girder_to_centroid_m + bridge.deck.thickness_m / 2)
