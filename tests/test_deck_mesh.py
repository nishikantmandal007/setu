"""The deck mesh must keep every line that matters."""


from types import SimpleNamespace

import numpy as np
import pytest

from src.models.deck import DeckCrossSection
from src.models.bridge import (
    Bracing,
    BridgeInput,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
)
from src.services.bridge_geometry import build_mesh

CROSS_SECTION = DeckCrossSection.from_widths(
    {
        "footpath_left": 1.50,
        "kerb_left": 0.45,
        "carriageway_1": 4.50,
        "median": 0.60,
        "carriageway_2": 4.50,
        "kerb_right": 0.45,
        "footpath_right": 1.50,
    }
)

BRIDGE = BridgeInput(
    span_m=35.0,
    cross_section=CROSS_SECTION,
    deck=DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.075),
    girders=Girders(
        count=5,
        section=PlateGirderSection(
            top_flange_width_m=0.550,
            top_flange_thickness_m=0.025,
            bottom_flange_width_m=0.650,
            bottom_flange_thickness_m=0.040,
            web_thickness_m=0.014,
            web_height_m=2.100,
        ),
    ),
    bracing=Bracing(station_count=7, area_m2=0.01, arrangement="XT"),
    mesh=MeshSettings(panels_between_braces=4, target_size_across_width_m=0.6),
)


def test_the_mesh_spans_the_bridge():
    mesh = build_mesh(BRIDGE)

    assert mesh.length_mesh_m[0] == pytest.approx(0.0)
    assert mesh.length_mesh_m[-1] == pytest.approx(BRIDGE.span_m)
    assert mesh.width_mesh_m[0] == pytest.approx(0.0)
    assert mesh.width_mesh_m[-1] == pytest.approx(BRIDGE.width_m())


def test_stations_increase():
    mesh = build_mesh(BRIDGE)

    assert (np.diff(mesh.length_mesh_m) > 0).all()
    assert (np.diff(mesh.width_mesh_m) > 0).all()


def test_every_bracing_station_lands_on_a_mesh_station():
    """A brace has to be tied to a node, so its line has to be in the mesh."""
    mesh = build_mesh(BRIDGE)

    for brace_m in mesh.brace_lines_m:
        assert np.isclose(mesh.length_mesh_m, brace_m).any()


def test_every_girder_lands_on_a_mesh_station():
    """Otherwise the deck cannot be tied down onto it."""
    mesh = build_mesh(BRIDGE)

    for girder in range(BRIDGE.girders.count):
        assert mesh.width_mesh_m[mesh.width_station_of_girder(girder)] == pytest.approx(
            mesh.girder_lines_m[girder]
        )


def test_every_cross_section_boundary_lands_on_a_mesh_station():
    """So a kerb line never falls inside an element, where it cannot be represented."""
    mesh = build_mesh(BRIDGE)

    for strip in CROSS_SECTION.strips:
        assert np.isclose(mesh.width_mesh_m, strip.z_from_m).any()
        assert np.isclose(mesh.width_mesh_m, strip.z_to_m).any()


def test_elements_are_no_larger_than_asked_for():
    mesh = build_mesh(BRIDGE)
    assert np.max(np.diff(mesh.width_mesh_m)) <= BRIDGE.mesh.target_size_across_width_m + 1e-9


def test_the_girders_are_evenly_spaced_between_the_overhangs():
    mesh = build_mesh(BRIDGE)

    assert mesh.girder_lines_m[0] == pytest.approx(BRIDGE.deck.overhang_m)
    assert mesh.girder_lines_m[-1] == pytest.approx(BRIDGE.width_m() - BRIDGE.deck.overhang_m)
    assert np.diff(mesh.girder_lines_m) == pytest.approx(mesh.girder_spacing_m)


def test_a_crash_barrier_strip_carries_its_own_dead_load():
    # It used to match none of the named prefixes and fall through to zero, so a deck with
    # crash barriers silently lost their weight. OsdagBridge names strips this way.
    from src.services.bridge_geometry import surfacing_pressure_at

    with_barriers = BridgeInput(**{**BRIDGE.__dict__, "cross_section": DeckCrossSection.from_widths({"crash_barrier_left": 0.45, "carriageway": 7.5, "crash_barrier_right": 0.45})})
    model = SimpleNamespace(bridge=with_barriers)

    on_the_barrier = surfacing_pressure_at(model, 0.2)

    assert on_the_barrier == with_barriers.added_dead_loads.crash_barrier.pressure_kpa
    assert on_the_barrier > 0.0
