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
    AddedDeadLoads, BridgeInput, Concrete, DeckCrossSection, DeckSlab, Girders, Bracing,
    MeshSettings, PlateGirderSection, Steel,
)
from setu.models.site import SeismicSite, TemperatureSite, WindSite
from setu.postprocess.design_values import girder_design_values
from setu.utils.constants import BASIC, BIGGER_IS_WORSE, MAX_MOMENT, PLAIN_TERRAIN

bridge = BridgeInput(
    span_m=35.0,
    skew=0.0,
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
    steel=Steel(elastic_modulus_mpa=200000.0, poissons_ratio=0.3, unit_weight_kn_m3=78.5),
    concrete=Concrete(elastic_modulus_mpa=32000.0, poissons_ratio=0.2, unit_weight_kn_m3=25.0),
    wearing_course_unit_weight_kn_m3=22.0,
    added_dead_loads=AddedDeadLoads(footpath_kpa=3.6, kerb_kn_per_m=3.24, median_kn_per_m=3.6, crash_barrier_kn_per_m=0.0, railing_kn_per_m=0.0),
)  # every input is required: nothing is assumed, a missing one raises

results = girder_design_values(
    bridge,
    wind=WindSite(basic_wind_speed_mps=39.0, terrain=PLAIN_TERRAIN, height_m=12.0, funnelling=False, solid_barrier_height_m=1.1),
    seismic=SeismicSite(zone="IV", soil="II", importance_factor=1.2, period_s=0.5, response_reduction=1.0),
    temperature=TemperatureSite(shade_max_c=45.0, shade_min_c=2.0),
)
for girder, by_response in results.girders.items():
    governing = by_response[MAX_MOMENT][BASIC][BIGGER_IS_WORSE]
    print(f"girder {girder}: {governing.value:.1f} kNm ({governing.combination})")
```

## Units

Every input name carries its unit: `_m` metres, `_mpa` N/mm² (elastic moduli, as OsdagBridge gives them), `_kn_m3` kN/m³, `_kpa` kN/m², `_mps` m/s, `_c` °C. `skew` is the tan of the skew angle. Inside, the solver works in kN and m; E is turned from MPa to kN/m² in one place (`Steel` / `Concrete.elastic_modulus_kpa`).

## Command line

One command runs the whole analysis on a bridge file and writes everything to `analysis_results/`:

```bash
uv run python cli.py examples/bridge.toml          # add --plot to pop up the plots
```

- `analysis_results/result.json` contains:
  - every critical position (each girder; maximum composite moment, support shear and bearing reaction in both directions; midspan deflection), each with:
    - the vehicles (name, centre z, front x of each in the train, impact), the lane pattern and reduction, the residual UDL and footway strips;
    - the same load solved in OpenSees as a check;
  - the design values for every girder and limit state (moment, shear, bearing reaction), with the station each governs at, plus the governing ones;
  - the dead load by construction stage: midspan moment, support shear, bearing reaction and midspan deflection;
  - the IRC:22 deflections (live load with impact, each dead stage, total) and their L/800 and L/600 limits;
  - the clause 204.6 fatigue moment and shear ranges, with the truck line and impact, and the live-load shear range;
  - the wind, seismic and temperature numbers (heating and cooling primary stresses in every girder on its IRC:22 effective width).
- `analysis_results/critical_positions.csv` lists where every vehicle stands for each girder's maximum bending moment: vehicle, facing, centre z, front x of each vehicle in the train, impact, lane reduction and the live moment.
- `analysis_results/girder_results.nc` holds the girder element forces (`Vx_i … Mz_j`) and node displacements of every dead load stage and every critical live load, as an xarray Dataset in OsdagBridge's layout (`forces(Loadcase, Element, Component)`, `displacements(Loadcase, Node, Component)`), in kN, kN·m and m.
- `analysis_results/plots/` holds the design dashboard and the critical position of every girder.
- To write the bridge file, open `examples/form.html` in a browser: fill it in, download `bridge.toml`. The TOML format is shown in `examples/bridge.toml`.

The CLI only calls setu's public API. OsdagBridge uses setu as a library: `girder_design_values`, `applied_live_loads` and `dead_load_forces(...).dataset` / `result_dataset` are the calls it needs.

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
├── postprocess/  girder response, dead load by stage, design values, the xarray result dataset
└── utils/        constants.py: constants more than one module uses, one section per topic
```

## Flow

![setu end-to-end flow](docs/flow.svg)

- **Dead load** is solved in the IRC:22 un-propped construction stages (the only method OsdagBridge uses): girder and bracing self weight, then the wet slab, on the bare steel; then SIDL and surfacing on the long-term composite deck (m ≥ 15). SIDL takes the footpath as an area load (kN/m²) and kerb, median, crash barrier and railing as line loads (kN/m) along each strip. Surfacing is kept apart, because IRC:6 Table B.2 factors it at 1.75 rather than 1.35.
- **Live load** uses the short-term composite deck (m ≥ 7.5). Each girder gets its own influence surfaces and its own critical-position search, including the residual UDL and the clause 206.3 footway load; braking (211) goes with the traffic it comes from. The composite moment is read at midspan and at 0.02L, 0.04L and 0.06L towards the bearing (the maximum live moment stands a little off midspan), shear at the bearing, and the bearing reaction. Each bearing is a 10¹⁰ kN/m vertical spring, rigid for design, which makes the reaction an element force with an exact influence surface.
- **Deflection** follows IRC:22: live load with impact but without the footway load, each dead load stage (steel stages on the bare steel), and the total.
- **Fatigue** follows IRC:6 clause 204.6: one 40 t truck (dual tyres) in a single passage along the line that is worst, outer tyre 150 mm off the kerb, with 50 % of the clause 208 impact; the range counts the unloaded state.
- **Wind** follows IRC:6 clause 209: Table 12 pressure, F_T at the centroid of its area, F_L, F_V, and wind on the live load.
- **Seismic** follows IRC:SP:114-2018, which replaced IRC:6 clause 218: Ah = (Z/2)(I/R)(Sa/g) with the Table 5.2 minimum, 20 % live load, and the 100/30/30 combination. I, T and R come from the input.
- **Temperature** (215) gives no girder force on a simply supported span with a free bearing. It is reported as the Fig. 17b / Table 15B heating and cooling primary stresses (h1 = 0.6h, h2 = 0.4 m; ΔT1 read by slab depth and surfacing, 50–100 mm) on each girder's IRC:22 cl. 603.2.1 effective slab width, and the bearing movement.
- **Custom loads**: point, line or area loads filed under DL / SIDL / DW / LL / EL / WL / TL, or a group of your own that only a custom combination picks up.
- **Combinations** follow IRC:6 Annex B. One variable load leads at a time; a variable load that relieves the effect is left out; permanent loads take their adding or relieving factor; no live load in winds over 36 m/s.
- Every force is an internal force, sagging positive.
- **Mesh:** see [docs/mesh_convergence.md](docs/mesh_convergence.md) for how fine the mesh needs to be.

## Tests

```bash
uv run pytest
```
