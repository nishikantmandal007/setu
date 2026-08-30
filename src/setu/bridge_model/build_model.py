from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..deck_model import DeckModel
from ..reporting import log, report
from .bridge_input import BridgeInput
from .connections import support_the_girders, tie_braces_to_girders, tie_deck_to_girders
from .deck_mesh import DeckMesh, build_mesh
from .elements import build_bracing, build_deck_shells, build_girder_beams
from .girder_sections import GirderProperties, girder_properties
from .model_tags import (
    DEGREES_OF_FREEDOM_PER_NODE,
    DIMENSIONS,
    GIRDER_LOCAL_AXIS,
    SolverCommands,
)
from .nodes import place_brace_nodes, place_deck_nodes, place_girder_nodes, place_k_brace_nodes


@dataclass(frozen=True, eq=False)
class BridgeModel:
    bridge: BridgeInput
    mesh: DeckMesh
    girder: GirderProperties

    deck_nodes: dict[tuple[int, int], int]
    girder_nodes: dict[tuple[int, int], int]
    bottom_brace_nodes: dict[tuple[int, int], int]
    top_brace_nodes: dict[tuple[int, int], int]
    k_brace_nodes: dict[tuple[int, int], int] = field(default_factory=dict)

    deck_elements: dict[tuple[int, int], int] = field(default_factory=dict)
    girder_elements: dict[tuple[int, int], int] = field(default_factory=dict)
    brace_elements: dict[tuple[int, int, str], int] = field(default_factory=dict)

    def as_deck_model(self) -> DeckModel:
        return DeckModel(
            length_mesh_m=self.mesh.length_mesh_m,
            width_mesh_m=self.mesh.width_mesh_m,
            deck_nodes=self.deck_nodes,
            girder_section=self.girder.for_solver(self.bridge.steel),
            girder_local_axis=GIRDER_LOCAL_AXIS,
            girder_elements=self.girder_elements,
        )

    def midspan_element_of_girder(self, girder: int) -> int:
        return self.girder_elements[(girder, self.mesh.stations_along_span // 2)]


def build_bridge_model(bridge: BridgeInput, ops: SolverCommands | None = None) -> BridgeModel:
    ops = load_opensees() if ops is None else ops

    mesh = build_mesh(bridge)
    girder = girder_properties(bridge.girders.section)
    report_layout(bridge, mesh)

    ops.wipe()
    ops.model("basic", "-ndm", DIMENSIONS, "-ndf", DEGREES_OF_FREEDOM_PER_NODE)

    deck_nodes = place_deck_nodes(ops, mesh)
    girder_nodes = place_girder_nodes(ops, bridge, mesh, girder)
    bottom_brace_nodes, top_brace_nodes = place_brace_nodes(ops, bridge, mesh, girder)
    k_brace_nodes = place_k_brace_nodes(ops, bridge, mesh, girder)

    model = BridgeModel(
        bridge=bridge,
        mesh=mesh,
        girder=girder,
        deck_nodes=deck_nodes,
        girder_nodes=girder_nodes,
        bottom_brace_nodes=bottom_brace_nodes,
        top_brace_nodes=top_brace_nodes,
        k_brace_nodes=k_brace_nodes,
    )

    model.deck_elements.update(build_deck_shells(ops, bridge, mesh, deck_nodes))
    model.girder_elements.update(build_girder_beams(ops, bridge, mesh, girder, girder_nodes))

    tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes)
    tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes)

    model.brace_elements.update(build_bracing(ops, bridge, mesh, model))

    support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes)

    report_what_was_built(model)
    return model


def report_layout(bridge: BridgeInput, mesh: DeckMesh) -> None:
    report(
        "BRIDGE LAYOUT",
        {
            "Span": f"{bridge.span_m:.3f} m",
            "Deck width": f"{bridge.width_m:.3f} m",
            "Girders": f"{bridge.girders.count} at {mesh.girder_spacing_m:.3f} m centres",
            "Bracing": f"{bridge.bracing.station_count} stations, {bridge.bracing.arrangement}",
            "Stations along span": f"{mesh.stations_along_span}",
            "Stations across width": f"{mesh.stations_across_width}",
            "Mesh size along span": f"{np.min(np.diff(mesh.length_mesh_m)):.3f} to "
            f"{np.max(np.diff(mesh.length_mesh_m)):.3f} m",
            "Mesh size across width": f"{np.min(np.diff(mesh.width_mesh_m)):.3f} to "
            f"{np.max(np.diff(mesh.width_mesh_m)):.3f} m",
        },
    )


def report_what_was_built(model: BridgeModel) -> None:
    brace_nodes = (
        len(model.bottom_brace_nodes) + len(model.top_brace_nodes) + len(model.k_brace_nodes)
    )
    report(
        "MODEL BUILT",
        {
            "Deck nodes": f"{len(model.deck_nodes)}",
            "Girder nodes": f"{len(model.girder_nodes)}",
            "Brace nodes": f"{brace_nodes}",
            "Deck shell elements": f"{len(model.deck_elements)}",
            "Girder elements": f"{len(model.girder_elements)}",
            "Brace elements": f"{len(model.brace_elements)}",
        },
    )
    log.info("")


def load_opensees() -> SolverCommands:
    from ..influence_surfaces.opensees_backend import import_opensees as load

    return load()
