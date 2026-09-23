# Setu

Bridge analysis library for IRC:6 plate girder design. Uses influence surfaces
and the adjoint method to find the worst legal vehicle position without brute-force
FEA — one solve gives the response everywhere on the deck.

Built as the analysis backend for [OsdagBridge](https://github.com/osdag-admin/OsdagBridge)

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
    build_bridge_model, InfluenceSolver, find_critical_position,
    irc6_combinations,
)
from setu.utils.constants import BASIC, DEAD, LIVE, SURFACING
from setu.postprocess.girder_response import dead_load_forces

bridge = BridgeInput(
    span_m=35.0,
    cross_section=DeckCrossSection.from_widths({
        "footpath_left": 1.5,
        "carriageway": 7.5,
        "footpath_right": 1.5,
    }),
    deck=DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.075),
    girders=Girders(count=4, section=PlateGirderSection(
        top_flange_width_m=0.55, top_flange_thickness_m=0.025,
        bottom_flange_width_m=0.65, bottom_flange_thickness_m=0.04,
        web_height_m=2.1, web_thickness_m=0.014,
    )),
    bracing=Bracing(station_count=7, area_m2=0.01, arrangement="XT"),
    mesh=MeshSettings(panels_between_braces=4, target_size_across_width_m=0.6),
)  # un-propped construction by default; pass construction="propped" to change it

uls = next(c for c in irc6_combinations() if c.limit_state == BASIC and c.leading == LIVE)
dead = dead_load_forces(bridge).factored({DEAD: uls.factors[DEAD][0], SURFACING: uls.factors[SURFACING][0]})

model = build_bridge_model(bridge)  # short-term composite, for live load
midspan = model.mesh.stations_along_span // 2
solver = InfluenceSolver(model.as_deck_model())
for girder in range(bridge.girders.count):
    surface = solver.for_girder_composite_moment(
        f"girder {girder}, midspan", model.midspan_element_of_girder(girder)
    )
    live = find_critical_position(surface, bridge.cross_section, span_m=bridge.span_m,
                                  wearing_course_thickness_m=bridge.deck.wearing_course_thickness_m)
    design = dead[girder].composite_moment_kn_m[midspan] + uls.factors[LIVE][0] * live.response
    print(f"girder {girder}: ULS-1 midspan moment = {design:.1f} kNm")
```

## Structure

Each folder is one layer. A layer only imports from the layers above it.

```text
setu/
├── models/       bridge inputs: geometry, deck, materials, sections
├── irc6/         IRC:6 rules: vehicles, impact, lanes, wheel loads, combinations; irc_constants.py holds the clause values
├── builder/      mesh generation and OpenSees model assembly
├── loads/        dead loads in construction stages, live load, load cases
├── solver/       OpenSees FE backend and stiffness matrices
├── analysis/     influence surfaces, along-span and across-carriageway search, critical position
├── postprocess/  girder response, dead load by stage, envelopes, result datasets, plots
└── utils/        constants.py: constants more than one module uses
```

## Flow

![setu end-to-end flow](docs/flow.svg)

- **Dead load** is solved in the IRC:22 construction stages: bare steel for the wet slab when un-propped, then the long-term composite deck (m ≥ 15) for everything laid on it. Surfacing is kept apart because IRC:6 Table B.2 factors it at 1.75, not 1.35.
- **Live load** uses the short-term composite deck (m ≥ 7.5). Each girder gets its own influence surfaces: composite moment (steel moment + steel axial force × lever arm to the slab) and shear. Each surface gets its own critical-position search, including the residual UDL and the clause 206.3 footway load.
- `live_load(model, critical, surface)` turns a critical position into the `"live"` load case. Solved in OpenSees, it gives back the same response the search reported.
- Every force is an internal force, sagging positive. `examples/plate_girder_35m.py` runs the whole loop and prints the governing girder.

## Tests

```bash
uv run pytest
```
