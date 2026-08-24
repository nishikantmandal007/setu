"""Building the bridge in the solver.

A composite deck on plate girders, laid out the way it is actually built:

    a concrete slab, modelled as shell elements on the deck grid,
    steel girders running along the span below it,
    rigid links tying the slab down onto the girders,
    cross bracing between the girders at each bracing station,
    and a pinned support at one end with a roller at the other.

The girder is the master of every rigid link, so the slab is carried by the
girders rather than the other way round.

Elevations are measured from the middle of the slab, which sits at y = 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..deck_model import DeckModel
from ..reporting import log, report
from .deck_mesh import DeckMesh, build_mesh
from .girder_sections import GirderProperties, properties_of
from .inputs import BridgeInput

DECK_NODE_BASE = 1000
DECK_ELEMENT_BASE = 1000
DECK_SECTION = 1
GIRDER_TRANSFORM = 1
BRACE_MATERIAL = 10

GIRDER_LOCAL_AXIS = (0.0, 0.0, 1.0)
"""Puts the girder's local y axis on global Y, so vertical bending is resisted by
the strong axis. It was once (0, 1, 0), which quietly handed vertical bending to
the weak axis instead - a stiffness 42 times too small."""


@dataclass(frozen=True, eq=False)
class BridgeModel:
    """A bridge that has been built in the solver and is ready to be loaded."""

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
        """Returns this bridge in the form the influence solver needs."""
        return DeckModel(
            length_mesh_m=self.mesh.length_mesh_m,
            width_mesh_m=self.mesh.width_mesh_m,
            deck_nodes=self.deck_nodes,
            girder_section=self.girder.for_solver(self.bridge.steel),
            girder_local_axis=GIRDER_LOCAL_AXIS,
            girder_elements=self.girder_elements,
        )

    def midspan_element_of_girder(self, girder: int) -> int:
        """Returns the girder element nearest the middle of the span."""
        return self.girder_elements[(girder, self.mesh.stations_along_span // 2)]


def build_bridge_model(bridge: BridgeInput, ops=None) -> BridgeModel:
    """Builds the whole bridge in the solver and returns what was built."""
    ops = _opensees() if ops is None else ops
    mesh = build_mesh(bridge)
    girder = properties_of(bridge.girders.section)

    _report_layout(bridge, mesh)

    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    deck_nodes = _place_deck_nodes(ops, mesh)
    girder_nodes = _place_girder_nodes(ops, bridge, mesh, girder)
    bottom_brace_nodes, top_brace_nodes = _place_brace_nodes(ops, bridge, mesh, girder)
    k_brace_nodes = _place_k_brace_nodes(ops, bridge, mesh, girder)

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

    model.deck_elements.update(_build_deck(ops, bridge, mesh, deck_nodes))
    model.girder_elements.update(_build_girders(ops, bridge, mesh, girder, girder_nodes))
    _tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes)
    _tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes)
    model.brace_elements.update(_build_bracing(ops, bridge, mesh, model))
    _support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes)

    _report_what_was_built(model)
    return model


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _place_deck_nodes(ops, mesh: DeckMesh) -> dict[tuple[int, int], int]:
    """A node wherever a station along the span crosses a station across the width."""
    deck_level_m = 0.0
    nodes = {}

    for i, x_m in enumerate(mesh.length_mesh_m):
        for j, z_m in enumerate(mesh.width_mesh_m):
            tag = DECK_NODE_BASE + i * mesh.stations_across_width + j
            ops.node(tag, float(x_m), deck_level_m, float(z_m))
            nodes[(i, j)] = tag

    return nodes


def _place_girder_nodes(
    ops, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties
) -> dict[tuple[int, int], int]:
    """A node on every girder at every station along the span."""
    base = DECK_NODE_BASE + mesh.stations_along_span * mesh.stations_across_width
    level_m = _girder_centroid_level_m(bridge, girder)

    nodes = {}
    for k, z_m in enumerate(mesh.girder_lines_m):
        for i, x_m in enumerate(mesh.length_mesh_m):
            tag = base + k * mesh.stations_along_span + i
            ops.node(tag, float(x_m), level_m, float(z_m))
            nodes[(k, i)] = tag

    return nodes


def _place_brace_nodes(
    ops, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties
) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
    """A node at the top and bottom of every girder, at every bracing station."""
    girders = bridge.girders.count
    stations = bridge.bracing.station_count

    bottom_base = (
        DECK_NODE_BASE
        + mesh.stations_along_span * mesh.stations_across_width
        + girders * mesh.stations_along_span
    )
    top_base = bottom_base + girders * stations

    centroid_m = _girder_centroid_level_m(bridge, girder)
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


def _place_k_brace_nodes(
    ops, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties
) -> dict[tuple[int, int], int]:
    """K bracing meets at a point midway between two girders, so that point needs a node."""
    if not bridge.bracing.is_k_braced:
        return {}

    girders = bridge.girders.count
    stations = bridge.bracing.station_count
    base = (
        DECK_NODE_BASE
        + mesh.stations_along_span * mesh.stations_across_width
        + girders * mesh.stations_along_span
        + 2 * girders * stations
    )
    level_m = _girder_centroid_level_m(bridge, girder) - girder.neutral_axis_from_bottom_m

    nodes = {}
    for n, x_m in enumerate(mesh.brace_lines_m):
        for k in range(girders - 1):
            between_girders_m = 0.5 * (mesh.girder_lines_m[k] + mesh.girder_lines_m[k + 1])
            tag = base + n * (girders - 1) + k
            ops.node(tag, float(x_m), level_m, float(between_girders_m))
            nodes[(k, n)] = tag

    return nodes


def _girder_centroid_level_m(bridge: BridgeInput, girder: GirderProperties) -> float:
    """How far the girder's centroid sits below the middle of the slab."""
    top_of_girder_to_centroid_m = girder.depth_m - girder.neutral_axis_from_bottom_m
    return -(top_of_girder_to_centroid_m + bridge.deck.thickness_m / 2)


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------


def _build_deck(
    ops, bridge: BridgeInput, mesh: DeckMesh, deck_nodes: dict
) -> dict[tuple[int, int], int]:
    """A shell element in every square of the deck grid."""
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


def _build_girders(
    ops, bridge: BridgeInput, mesh: DeckMesh, girder: GirderProperties, girder_nodes: dict
) -> dict[tuple[int, int], int]:
    """A beam element between every pair of stations, on every girder."""
    ops.geomTransf("Linear", GIRDER_TRANSFORM, *GIRDER_LOCAL_AXIS)

    base = DECK_ELEMENT_BASE + (mesh.stations_along_span - 1) * (mesh.stations_across_width - 1)
    elements = {}
    tag = base

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


def _tie_deck_to_girders(ops, mesh: DeckMesh, deck_nodes: dict, girder_nodes: dict) -> None:
    """Rigid links carrying the slab on the girders, girder as master."""
    for k in range(len(mesh.girder_lines_m)):
        j = mesh.width_station_of_girder(k)
        for i in range(mesh.stations_along_span):
            ops.rigidLink("beam", girder_nodes[(k, i)], deck_nodes[(i, j)])


def _tie_braces_to_girders(
    ops,
    bridge: BridgeInput,
    mesh: DeckMesh,
    girder_nodes: dict,
    bottom_brace_nodes: dict,
    top_brace_nodes: dict,
) -> None:
    """Rigid links from each girder out to its own brace nodes above and below."""
    for k in range(bridge.girders.count):
        for n, x_m in enumerate(mesh.brace_lines_m):
            i = _station_at(mesh.length_mesh_m, x_m)
            ops.rigidLink("beam", girder_nodes[(k, i)], bottom_brace_nodes[(k, n)])
            ops.rigidLink("beam", girder_nodes[(k, i)], top_brace_nodes[(k, n)])


def _build_bracing(
    ops, bridge: BridgeInput, mesh: DeckMesh, model: BridgeModel
) -> dict[tuple[int, int, str], int]:
    """Truss members between neighbouring girders at each bracing station."""
    ops.uniaxialMaterial("Elastic", BRACE_MATERIAL, bridge.steel.elastic_modulus_kpa)

    base = (
        DECK_ELEMENT_BASE
        + (mesh.stations_along_span - 1) * (mesh.stations_across_width - 1)
        + bridge.girders.count * (mesh.stations_along_span - 1)
    )
    elements: dict[tuple[int, int, str], int] = {}
    tag = base

    for n in range(bridge.bracing.station_count):
        for k in range(bridge.girders.count - 1):
            corners = _brace_panel_corners(model, k, n)
            for role, (start, end) in _brace_members(bridge, model, corners, k, n):
                ops.element(
                    "corotTruss", tag, start, end, bridge.bracing.area_m2, BRACE_MATERIAL
                )
                elements[(k, n, role)] = tag
                tag += 1

    return elements


def _brace_panel_corners(model: BridgeModel, k: int, n: int) -> dict[str, int]:
    return {
        "top_left": model.top_brace_nodes[(k, n)],
        "top_right": model.top_brace_nodes[(k + 1, n)],
        "bottom_left": model.bottom_brace_nodes[(k, n)],
        "bottom_right": model.bottom_brace_nodes[(k + 1, n)],
    }


def _brace_members(
    bridge: BridgeInput, model: BridgeModel, corners: dict[str, int], k: int, n: int
) -> list[tuple[str, tuple[int, int]]]:
    """Returns which members make up one bracing panel, and what to call each."""
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


def _support_the_girders(
    ops, bridge: BridgeInput, mesh: DeckMesh, girder_nodes: dict, k_brace_nodes: dict
) -> None:
    """Pinned at the near end of every girder, roller at the far end."""
    last = mesh.stations_along_span - 1

    for k in range(bridge.girders.count):
        ops.fix(girder_nodes[(k, 0)], 1, 1, 1, 0, 0, 0)
        ops.fix(girder_nodes[(k, last)], 0, 1, 1, 0, 0, 0)

    # A K bracing meeting point is held against everything except moving with the
    # deck sideways and vertically; it is a joint, not a support.
    for tag in k_brace_nodes.values():
        ops.fix(tag, 1, 0, 0, 1, 1, 1)


def _station_at(stations_m: np.ndarray, position_m: float) -> int:
    """Returns which station sits at this position."""
    found = np.where(np.isclose(stations_m, position_m))[0]
    if len(found) == 0:
        raise ValueError(f"no mesh station at {position_m:.5f} m")
    return int(found[0])


def _report_layout(bridge: BridgeInput, mesh: DeckMesh) -> None:
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


def _report_what_was_built(model: BridgeModel) -> None:
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


def _opensees():
    from ..influence_surfaces.opensees_backend import _opensees as load

    return load()
