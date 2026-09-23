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


import openseespy.opensees as ops

from setu import (
    Bracing,
    BridgeInput,
    DeckCrossSection,
    DeckSlab,
    Girders,
    InfluenceSolver,
    MeshSettings,
    PlateGirderSection,
    apply_dead_loads,
    build_bridge_model,
    find_critical_position,
)
from setu.helpers import enable_reports

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


def worst_for_every_girder(model) -> dict:
    """One influence surface and one search per girder and per response.

    Every surface is solved before any other load goes on the model.
    """
    influence = InfluenceSolver(model.as_deck_model())
    support = 0
    worst = {}
    for girder in range(BRIDGE.girders.count):
        responses = {
            "midspan moment": influence.for_girder_moment(
                f"girder {girder}, midspan moment", model.midspan_element_of_girder(girder)
            ),
            "support shear": influence.for_girder_shear(
                f"girder {girder}, support shear", model.element_of_girder_at(girder, support)
            ),
        }
        for response, surface in responses.items():
            for adverse in ("maximum", "minimum"):
                worst[girder, response, adverse] = find_critical_position(
                    surface,
                    CROSS_SECTION,
                    span_m=BRIDGE.span_m,
                    adverse=adverse,
                    wearing_course_thickness_m=BRIDGE.deck.wearing_course_thickness_m,
                )
    return worst


def print_the_governing_girder(worst: dict) -> None:
    print()
    print("=" * 72)
    print("WORST LIVE LOAD RESPONSE, EVERY GIRDER")
    print("=" * 72)
    print(f"  {'girder':<8} {'response':<16} {'adverse':<9} {'design value':>14}")
    for (girder, response, adverse), critical in worst.items():
        print(f"  {girder:<8} {response:<16} {adverse:<9} {critical.response:14.3f}")
    for response in ("midspan moment", "support shear"):
        governing = max(
            (key for key in worst if key[1] == response), key=lambda key: abs(worst[key].response)
        )
        print()
        print(f"Governing {response}: girder {governing[0]} ({governing[2]})")
        print(worst[governing].describe())


def main() -> None:
    enable_reports()

    model = build_bridge_model(BRIDGE)

    worst = worst_for_every_girder(model)
    print_the_governing_girder(worst)

    dead_load = apply_dead_loads(model)
    check_it_stands_up(dead_load.total_kn)


if __name__ == "__main__":
    main()
