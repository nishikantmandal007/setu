# Building the bridge in the solver.
#
# A composite deck on plate girders, laid out the way it is actually built:
#
#     a concrete slab, modelled as shell elements on the deck grid,
#     steel girders running along the span below it,
#     rigid links tying the slab down onto the girders,
#     cross bracing between the girders at each bracing station,
#     and a pinned support at one end with a roller at the other.
#
# The girder is the master of every rigid link, so the slab is carried by the girders
# rather than the other way round.
#
# Elevations are measured from the middle of the slab, which sits at y = 0.

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
from .model_tags import GIRDER_LOCAL_AXIS, SolverCommands
from .nodes import place_brace_nodes, place_deck_nodes, place_girder_nodes, place_k_brace_nodes


@dataclass(frozen=True, eq=False)
class BridgeModel:
    # A bridge that has been built in the solver and is ready to be loaded.
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
        # Returns this bridge in the form the influence solver needs.
        return DeckModel(
            length_mesh_m=self.mesh.length_mesh_m,
            width_mesh_m=self.mesh.width_mesh_m,
            deck_nodes=self.deck_nodes,
            girder_section=self.girder.for_solver(self.bridge.steel),
            girder_local_axis=GIRDER_LOCAL_AXIS,
            girder_elements=self.girder_elements,
        )

    def midspan_element_of_girder(self, girder: int) -> int:
        # Returns the girder element nearest the middle of the span.
        return self.girder_elements[(girder, self.mesh.stations_along_span // 2)]


def build_bridge_model(bridge: BridgeInput, ops: SolverCommands | None = None) -> BridgeModel:
    # Builds the whole bridge in the solver and returns what was built.

    # 1. Load the solver, unless the caller has already handed one in.
    ops = load_opensees() if ops is None else ops

    # 2. Work out the mesh and the girder section before anything is built.
    mesh = build_mesh(bridge)
    girder = girder_properties(bridge.girders.section)
    report_layout(bridge, mesh)

    # 3. Start a fresh model.
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    # 4. Place every node: the deck grid, the girders, and the brace nodes above, below,
    # and - for K bracing - between them.
    deck_nodes = place_deck_nodes(ops, mesh)
    girder_nodes = place_girder_nodes(ops, bridge, mesh, girder)
    bottom_brace_nodes, top_brace_nodes = place_brace_nodes(ops, bridge, mesh, girder)
    k_brace_nodes = place_k_brace_nodes(ops, bridge, mesh, girder)

    # 5. Collect what has been built so far - building the bracing needs to look brace
    # nodes up by name, which it does through this model.
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

    # 6. Build the deck shells and the girder beams.
    model.deck_elements.update(build_deck_shells(ops, bridge, mesh, deck_nodes))
    model.girder_elements.update(build_girder_beams(ops, bridge, mesh, girder, girder_nodes))

    # 7. Tie the deck to the girders, and the girders to their own bracing.
    tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes)
    tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes)

    # 8. Build the bracing members themselves.
    model.brace_elements.update(build_bracing(ops, bridge, mesh, model))

    # 9. Support the girders: pinned at one end, roller at the other.
    support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes)

    report_what_was_built(model)
    return model


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Looking A Station Up By Position
# ---------------------------------------------------------------------------


def load_opensees() -> SolverCommands:
    from ..influence_surfaces.opensees_backend import import_opensees as load

    return load()
