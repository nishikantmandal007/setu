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
    irc6_combinations,
    live_load,
)
from setu.helpers import enable_reports
from setu.utils.constants import BASIC, DEAD, LIVE, SURFACING
from setu.postprocess.girder_response import analyze_load_case, dead_load_forces

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


SUPPORT = 0
RESPONSES = ("midspan composite moment", "support shear")


def worst_live_load_on_every_girder(model, dead: dict) -> dict:
    """One influence surface and one search per girder and per response.

    The search looks for the live load that adds to the dead load, so it takes
    the dead load's sign as the adverse direction. Every surface is solved before
    any other load goes on the model.
    """
    influence = InfluenceSolver(model.as_deck_model())
    midspan = model.mesh.stations_along_span // 2
    worst = {}
    for girder in range(BRIDGE.girders.count):
        surfaces = {
            "midspan composite moment": (
                influence.for_girder_composite_moment(f"girder {girder}, midspan composite moment", model.midspan_element_of_girder(girder)),
                dead[girder].composite_moment_kn_m[midspan],
            ),
            "support shear": (
                influence.for_girder_shear(f"girder {girder}, support shear", model.element_of_girder_at(girder, SUPPORT)),
                dead[girder].shear_kn[SUPPORT],
            ),
        }
        for response, (surface, dead_value) in surfaces.items():
            critical = find_critical_position(
                surface,
                CROSS_SECTION,
                span_m=BRIDGE.span_m,
                adverse="maximum" if dead_value >= 0 else "minimum",
                wearing_course_thickness_m=BRIDGE.deck.wearing_course_thickness_m,
            )
            worst[girder, response] = (surface, critical)
    return worst


def print_uls_design_values(factored_dead: dict, worst: dict, midspan: int) -> tuple:
    """IRC:6-2017 Table B.2, ULS-1: 1.35 dead + 1.75 surfacing + 1.5 live."""
    live_factor = uls_live_leading().factors[LIVE][0]
    print()
    print("=" * 72)
    print("ULS-1 DESIGN VALUES, EVERY GIRDER  (1.35 dead + 1.75 surfacing + 1.5 live)")
    print("=" * 72)
    print(f"  {'girder':<7} {'response':<26} {'dead':>11} {'live':>11} {'ULS':>11}")
    design = {}
    for (girder, response), (_, critical) in worst.items():
        if response == "midspan composite moment":
            dead_value = factored_dead[girder].composite_moment_kn_m[midspan]
        else:
            dead_value = factored_dead[girder].shear_kn[SUPPORT]
        design[girder, response] = dead_value + live_factor * critical.response
        print(f"  {girder:<7} {response:<26} {dead_value:11.1f} {critical.response:11.1f} {design[girder, response]:11.1f}")
    governing = {response: max((key for key in design if key[1] == response), key=lambda key: abs(design[key])) for response in RESPONSES}
    for response, key in governing.items():
        print(f"  Governing {response}: girder {key[0]}, {design[key]:.1f}")
    return governing


def check_the_live_load_reproduces_the_search(model, worst: dict, key: tuple) -> None:
    """Put the governing live load on the real model and read the girder back."""
    girder, _ = key
    surface, critical = worst[key]
    midspan = model.mesh.stations_along_span // 2
    forces = analyze_load_case(model, live_load(model, critical, surface), ops)
    directly = forces[girder].composite_moment_kn_m[midspan]
    print()
    print(worst[key][1].describe())
    print(f"  Applied as a load case in OpenSees = {directly:14.3f}   (search said {critical.response:.3f})")


def uls_live_leading():
    return next(c for c in irc6_combinations() if c.limit_state == BASIC and c.leading == LIVE)


def main() -> None:
    enable_reports()

    dead = dead_load_forces(BRIDGE)
    uls = uls_live_leading()
    factored_dead = dead.factored({DEAD: uls.factors[DEAD][0], SURFACING: uls.factors[SURFACING][0]})

    model = build_bridge_model(BRIDGE)
    midspan = model.mesh.stations_along_span // 2
    worst = worst_live_load_on_every_girder(model, dead.total)
    governing = print_uls_design_values(factored_dead, worst, midspan)
    check_the_live_load_reproduces_the_search(model, worst, governing["midspan composite moment"])

    dead_load = apply_dead_loads(model)
    check_it_stands_up(dead_load.total_kn)


if __name__ == "__main__":
    main()
