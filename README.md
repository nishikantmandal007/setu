# Setu

Bridge analysis library for IRC:6 plate girder design. Uses influence surfaces
and the adjoint method to find the worst legal vehicle position without brute-force
FEA — one solve gives the response everywhere on the deck.

Built as the analysis backend for [Osdag](https://osdag.fossee.in/) Bridge.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```python
from setu import (
    BridgeInput, DeckCrossSection, DeckSlab, Girders, Bracing,
    MeshSettings, PlateGirderSection,
    build_bridge_model, apply_dead_loads,
    InfluenceSolver, find_critical_position,
)

bridge = BridgeInput(
    span_m=35.0,
    cross_section=DeckCrossSection.from_widths({
        "footpath_left": 1.5,
        "carriageway": 7.5,
        "footpath_right": 1.5,
    }),
    deck=DeckSlab(thickness_m=0.23, overhang_m=1.25),
    girders=Girders(count=4, section=PlateGirderSection(
        top_flange_width_m=0.55, top_flange_thickness_m=0.025,
        bottom_flange_width_m=0.65, bottom_flange_thickness_m=0.04,
        web_height_m=2.1, web_thickness_m=0.014,
    )),
    bracing=Bracing(station_count=7, area_m2=0.01, arrangement="XT"),
    mesh=MeshSettings(panels_between_braces=4, target_size_across_width_m=0.6),
)

model = build_bridge_model(bridge)
apply_dead_loads(model)

surface = InfluenceSolver(model.as_deck_model()).for_girder_moment(
    "midspan moment",
    model.midspan_element_of_girder(bridge.girders.count // 2),
)

worst = find_critical_position(surface, bridge.cross_section, span_m=bridge.span_m)
print(worst.describe())
```

## Structure

```text
setu/
├── models/       bridge geometry, materials, sections, vehicles, results
├── irc6/         IRC:6 impact, lane rules, wheel loads, load combinations
├── solver/       OpenSees FE backend and stiffness matrices
├── builder/      mesh generation, model assembly, dead loads
├── analysis/     influence surfaces, vehicle placement, critical position search
└── postprocess/  girder response, envelopes, load cases, plots
```

## Tests

```bash
uv run pytest
```
