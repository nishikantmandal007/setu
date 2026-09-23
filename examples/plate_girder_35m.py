"""A 35 m composite plate girder bridge, from input to IRC:6 design values for every girder.

Run it::

    python examples/plate_girder_35m.py

One call does it all: dead load in its IRC:22 construction stages, the worst legal
IRC:6 traffic for each girder (with braking), wind (209), seismic (IRC:SP:114-2018),
temperature (215) and a user load, combined per IRC:6 Annex B. It then checks the
bridge stands up under its own weight.
"""


import openseespy.opensees as ops

from setu import (
    Bracing,
    BridgeInput,
    DeckCrossSection,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
    apply_dead_loads,
    build_bridge_model,
)
from setu.helpers import enable_reports
from setu.models.site import SeismicSite, TemperatureSite, WindSite
from setu.postprocess.design_values import girder_design_values
from setu.utils.constants import (
    BASIC,
    BIGGER_IS_WORSE,
    MIDSPAN_MOMENT,
    PLAIN_TERRAIN,
    RARE,
    SEISMIC_COMBINATION,
    SMALLER_IS_WORSE,
    SUPPORT_SHEAR,
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


WIND = WindSite(basic_wind_speed_mps=39.0, terrain=PLAIN_TERRAIN, height_m=12.0, solid_barrier_height_m=1.1)
SEISMIC = SeismicSite(zone="IV", soil="II", importance="important")
TEMPERATURE = TemperatureSite(shade_max_c=45.0, shade_min_c=2.0)
COLUMNS = (
    ("ULS sagging", MIDSPAN_MOMENT, BASIC, BIGGER_IS_WORSE),
    ("ULS seismic", MIDSPAN_MOMENT, SEISMIC_COMBINATION, BIGGER_IS_WORSE),
    ("SLS rare", MIDSPAN_MOMENT, RARE, BIGGER_IS_WORSE),
    ("ULS shear", SUPPORT_SHEAR, BASIC, SMALLER_IS_WORSE),
)


def print_design_values(results) -> None:
    print()
    print("=" * 72)
    print("IRC:6 ANNEX B DESIGN VALUES, EVERY GIRDER  (moments kNm, shear kN)")
    print("=" * 72)
    print(f"  {'girder':<8}" + "".join(f"{title:>15}" for title, *_ in COLUMNS))
    for girder, by_response in results.girders.items():
        print(f"  {girder:<8}" + "".join(f"{by_response[response][limit_state][adverse].value:15.1f}" for _, response, limit_state, adverse in COLUMNS))
    for title, response, limit_state, adverse in COLUMNS:
        girder, governing = results.governing(response, limit_state, adverse)
        print(f"  Governing {title}: girder {girder}, {governing.value:.1f} ({governing.combination})")
    thermal = results.thermal
    positive = thermal["positive difference"]
    print(f"  Temperature: no girder force (free bearing); slab top {positive.slab_top_kpa / 1000:.2f} MPa, "
          f"steel bottom {positive.steel_bottom_kpa / 1000:.2f} MPa; bearing movement {thermal['free bearing movement m'] * 1000:.1f} mm")


def main() -> None:
    enable_reports()

    results = girder_design_values(BRIDGE, wind=WIND, seismic=SEISMIC, temperature=TEMPERATURE)
    print_design_values(results)

    model = build_bridge_model(BRIDGE)
    dead_load = apply_dead_loads(model)
    check_it_stands_up(dead_load.total_kn)


if __name__ == "__main__":
    main()
