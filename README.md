<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
    <img src="docs/assets/logo.svg" alt="Setu" width="260">
  </picture>
</p>

Bridge analysis library for IRC:6 plate girder design. Uses influence surfaces
and the adjoint method to find the worst legal vehicle position without brute-force
FEA — one solve gives the response everywhere on the deck.

Built as the analysis backend for [OsdagBridge](https://github.com/osdag-admin/OsdagBridge).

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```python
from setu import (
    AddedDeadLoads, Bracing, BridgeInput, Concrete, CustomLoad, DeckCrossSection, DeckSlab, Girders,
    MeshSettings, PlateGirderSection, SeismicSite, Steel, TemperatureSite, WindSite,
    custom_combination, girder_design_values,
)
from setu.utils.constants import (
    BASIC, BEARING_REACTION, BIGGER_IS_WORSE, MAX_MOMENT, RARE, SEISMIC_COMBINATION, SMALLER_IS_WORSE, SUPPORT_SHEAR,
)

# the bridge: every input is required, units are in the names (m, MPa, kN/m3, kPa, kN/m)
bridge = BridgeInput(
    span_m=35.0,
    skew=0.0,
    cross_section=DeckCrossSection.from_widths({
        "footpath_left": 1.5, "kerb_left": 0.45, "carriageway_1": 4.5, "median": 0.6,
        "carriageway_2": 4.5, "kerb_right": 0.45, "footpath_right": 1.5,
    }),
    deck=DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.075),
    girders=Girders(count=5, section=PlateGirderSection(
        top_flange_width_m=0.55, top_flange_thickness_m=0.025,
        bottom_flange_width_m=0.65, bottom_flange_thickness_m=0.04,
        web_height_m=2.1, web_thickness_m=0.014,
    )),
    bracing=Bracing(arrangement="XT", station_count=7, area_m2=0.01),
    mesh=MeshSettings(panels_between_braces=16, target_size_across_width_m=0.15),
    steel=Steel(elastic_modulus_mpa=200000, poissons_ratio=0.3, unit_weight_kn_m3=78.5),
    concrete=Concrete(elastic_modulus_mpa=32000, poissons_ratio=0.2, unit_weight_kn_m3=25.0),
    wearing_course_unit_weight_kn_m3=22.0,
    added_dead_loads=AddedDeadLoads(footpath_kpa=3.6, kerb_kn_per_m=3.24, median_kn_per_m=3.6,
                                    crash_barrier_kn_per_m=0.0, railing_kn_per_m=0.0),
)

results = girder_design_values(
    bridge,
    # IRC:6 cl. 209
    wind=WindSite(basic_wind_speed_mps=39.0, terrain="plain", height_m=12.0,
                  funnelling=False, solid_barrier_height_m=1.1),
    # IRC:SP:114
    seismic=SeismicSite(zone="IV", soil="II", importance_factor=1.2, period_s=0.5, response_reduction=1.0),
    # IRC:6 cl. 215
    temperature=TemperatureSite(shade_max_c=45.0, shade_min_c=2.0),
    # your own loads: point (kN), line (kN/m) or area (kPa), filed under an IRC group or a name of your own
    custom_loads=[
        CustomLoad(group="SIDL", shape="line", magnitude=2.5, x_from_bearing_m=0.0, z_from_left_edge_m=0.2,
                   x_end_m=35.0, z_end_m=0.2),
        CustomLoad(group="utility duct", shape="area", magnitude=1.2, x_from_bearing_m=0.0, z_from_left_edge_m=11.0,
                   x_end_m=35.0, z_end_m=12.0),
    ],
    # a combination that picks up your own group
    custom_combinations=[custom_combination("duct check", {"dead": 1.35, "surfacing": 1.75, "utility duct": 1.5})],
)

# design values: girder, response, limit state, direction
for girder, by_response in results.girders.items():
    moment = by_response[MAX_MOMENT][BASIC][BIGGER_IS_WORSE]
    shear = by_response[SUPPORT_SHEAR][BASIC][SMALLER_IS_WORSE]
    reaction = by_response[BEARING_REACTION][BASIC][BIGGER_IS_WORSE]
    print(f"girder {girder}: M {moment.value:,.0f} kN·m ({moment.combination}), "
          f"V {shear.value:,.0f} kN, R {reaction.value:,.0f} kN")
    print("   shares:", {group: round(share) for group, share in moment.shares.items()})

girder, seismic = results.governing(MAX_MOMENT, SEISMIC_COMBINATION, BIGGER_IS_WORSE)
print(f"seismic case: {seismic.value:,.0f} kN·m in girder {girder}")
girder, service = results.governing(MAX_MOMENT, RARE, BIGGER_IS_WORSE)
print(f"SLS rare: {service.value:,.0f} kN·m in girder {girder}")

# where the trucks stand for girder 0's largest moment
critical = results.criticals[0, MAX_MOMENT, BIGGER_IS_WORSE]
for vehicle in critical.vehicles:
    print(vehicle.vehicle_name, "centre z", vehicle.z_centre_m, "front x", vehicle.train_x_front_m, "impact", vehicle.impact_factor)

# IRC:22 deflections, IRC:6 cl. 204.6 fatigue, IRC:6 cl. 215 temperature
print(results.deflections[0])                      # live_m, dead_m by stage, total_m
print(results.fatigue[0][MAX_MOMENT].range)        # moment range of one fatigue truck passage
print(results.thermal["free bearing movement m"])  # temperature gives no girder force on a free bearing
for kind, stresses in results.thermal["girders"][0].items():
    print(kind, stresses.slab_top_kpa, stresses.steel_bottom_kpa)
```

Or in a local web app:

```bash
uv run python web/main.py            # then open http://localhost:5000
```

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/diagrams/flow-dark.svg">
  <img src="docs/assets/diagrams/flow.svg" alt="How Setu works: bridge input, model, dead load in stages, influence surfaces, worst traffic, design values">
</picture>

## Structure

```text
setu/
├── models/       bridge inputs: geometry, materials, sections
├── irc6/         IRC:6 rules: vehicles, impact, lanes, combinations
├── builder/      mesh and OpenSees model
├── loads/        dead, live and other load cases
├── solver/       OpenSees backend
├── analysis/     influence surfaces and critical position search
├── postprocess/  girder response and design values
└── utils/        shared constants
web/
├── main.py       the Flask app
├── routes.py     URLs to controllers
├── controller.py request handling
├── model/        inputs, analysis, report, drawings, critical-loads export
├── views/        the page
└── static/       its script and styles
docs/
├── javascripts/animations/  one file per animation; core.js holds the shared helpers, start.js draws them
├── javascripts/vehicles.js  the IRC vehicle drawings, shared with the web app
└── assets/                  logo and diagrams
```

## Tests

```bash
uv run pytest
```
