"""A 35 m composite plate girder bridge, from input to critical vehicle position.

Run it::

    python examples/plate_girder_35m.py

It builds the bridge, solves one influence surface for the middle girder's
midspan moment, finds the worst legal IRC:6 traffic that moment has to carry,
and then checks the bridge stands up under its own weight.

The order matters. An influence surface is read off the deflected shape under
one imaginary load, so it has to be solved on a model nothing else is loading -
which is why the dead load goes on last. setu checks this rather than trusting
it, because a dead load left switched on makes every surface quietly wrong.
"""

from __future__ import annotations

import openseespy.opensees as ops

from setu import DeckCrossSection, InfluenceSolver, enable_reports, find_critical_position
from setu.bridge_model import (
    Bracing,
    BridgeInput,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
    apply_dead_loads,
    build_bridge_model,
)

# ---------------------------------------------------------------------------
# The bridge
# ---------------------------------------------------------------------------

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
    mesh=MeshSettings(panels_between_braces=25, target_size_across_width_m=0.25),
)


def check_it_stands_up(applied_kn: float) -> None:
    """Solves the dead load case and checks the supports carry what was applied."""
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")
    ops.analyze(1)
    ops.reactions()

    vertical_kn = sum(ops.nodeReaction(node, 2) for node in ops.getNodeTags())
    sideways_kn = sum(ops.nodeReaction(node, 3) for node in ops.getNodeTags())
    out_of_balance = abs(vertical_kn - applied_kn) / applied_kn * 100

    print()
    print("=" * 72)
    print("STATICS CHECK")
    print("=" * 72)
    print(f"  Dead load applied      = {applied_kn:12.3f} kN")
    print(f"  Vertical reactions     = {vertical_kn:12.3f} kN")
    print(f"  Sideways reactions     = {sideways_kn:12.3f} kN")
    print(f"  Out of balance         = {out_of_balance:12.4f} %")


def main() -> None:
    enable_reports()

    model = build_bridge_model(BRIDGE)

    middle_girder = BRIDGE.girders.count // 2
    influence = InfluenceSolver(model.as_deck_model())
    surface = influence.for_girder_moment(
        "middle girder, midspan moment", model.midspan_element_of_girder(middle_girder)
    )

    for adverse in ("maximum", "minimum"):
        worst = find_critical_position(
            surface,
            CROSS_SECTION,
            span_m=BRIDGE.span_m,
            adverse=adverse,
            wearing_course_thickness_m=BRIDGE.deck.wearing_course_thickness_m,
        )
        print()
        print(worst.describe())

    dead_load = apply_dead_loads(model)
    check_it_stands_up(dead_load.total_kn)


if __name__ == "__main__":
    main()
