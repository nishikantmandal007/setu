# Getting started

## Install

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nishikantmandal007/setu
cd setu
uv sync
```

## Your first bridge

Save this as `first.py` and run `uv run python first.py`. It describes a 35 m bridge with four girders and prints the design moment of each girder.

```python
from setu import (
    AddedDeadLoads, Bracing, BridgeInput, Concrete, DeckCrossSection, DeckSlab,
    Girders, MeshSettings, PlateGirderSection, Steel, girder_design_values,
)
from setu.utils.constants import BASIC, BIGGER_IS_WORSE, MAX_MOMENT

bridge = BridgeInput(
    span_m=35.0,
    skew=0.0,
    cross_section=DeckCrossSection.from_widths({
        "footpath_left": 1.5, "carriageway": 7.5, "footpath_right": 1.5,
    }),
    deck=DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.075),
    girders=Girders(count=4, section=PlateGirderSection(
        top_flange_width_m=0.55, top_flange_thickness_m=0.025,
        bottom_flange_width_m=0.65, bottom_flange_thickness_m=0.04,
        web_height_m=2.1, web_thickness_m=0.014,
    )),
    bracing=Bracing(arrangement="XT", station_count=7, area_m2=0.01),
    mesh=MeshSettings(panels_between_braces=4, target_size_across_width_m=0.6),
    steel=Steel(elastic_modulus_mpa=200000, poissons_ratio=0.3, unit_weight_kn_m3=78.5),
    concrete=Concrete(elastic_modulus_mpa=32000, poissons_ratio=0.2, unit_weight_kn_m3=25.0),
    wearing_course_unit_weight_kn_m3=22.0,
    added_dead_loads=AddedDeadLoads(footpath_kpa=3.6, kerb_kn_per_m=0.0, median_kn_per_m=0.0,
                                    crash_barrier_kn_per_m=0.0, railing_kn_per_m=0.0),
)

results = girder_design_values(bridge)

for girder, by_response in results.girders.items():
    moment = by_response[MAX_MOMENT][BASIC][BIGGER_IS_WORSE]
    print(f"girder {girder}: {moment.value:,.0f} kN·m  ({moment.combination})")
```

!!! tip "Every input is required"
    Setu never guesses a value. If something is missing, it stops and names what is missing. Units are in every name: `_m` metres, `_mpa` N/mm², `_kpa` kN/m², `_kn_m3` kN/m³.

!!! note "Mesh"
    The coarse mesh above runs in seconds. For design, use 0.10–0.15 m across the deck and 16–25 panels between braces (see [Accuracy and limits](accuracy.md)).

## Add wind, earthquake and temperature

Pass the site as extra arguments. Leave out anything that does not apply.

```python
from setu import SeismicSite, TemperatureSite, WindSite

results = girder_design_values(
    bridge,
    wind=WindSite(basic_wind_speed_mps=39.0, terrain="plain", height_m=12.0,
                  funnelling=False, solid_barrier_height_m=1.1),
    seismic=SeismicSite(zone="IV", soil="II", importance_factor=1.2,
                        period_s=0.5, response_reduction=1.0),
    temperature=TemperatureSite(shade_max_c=45.0, shade_min_c=2.0),
)
```

## No code at all

The same analysis runs in a local web page:

```bash
uv run python web/main.py              # open http://localhost:5000
```

See [Web app](guide/web-app.md).
