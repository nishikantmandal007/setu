# API reference

Everything below is importable from `setu`.

## Describe the bridge

| Name | Purpose |
|---|---|
| `BridgeInput` | The whole bridge. See [Describing a bridge](inputs.md). |
| `DeckCrossSection.from_widths(widths)` | Deck strips, left to right. |
| `DeckSlab`, `Girders`, `PlateGirderSection`, `Bracing`, `MeshSettings` | Geometry and mesh. |
| `Steel`, `Concrete`, `SurfacingLayer` | Materials. |
| `AddedDeadLoads` | Superimposed dead load. |
| `WindSite`, `SeismicSite`, `TemperatureSite`, `CustomLoad` | Site and extra loads. |
| `custom_combination(name, factors)` | Your own load combination. |

## Run everything

| Name | Purpose |
|---|---|
| `girder_design_values(bridge, wind=None, seismic=None, temperature=None, custom_loads=(), custom_combinations=(), ops=None, *, braking_height_above_deck_m=None)` | The full analysis. Returns `DesignValues`. See [Reading the results](results.md). |

## The building blocks

Use these to go deeper, one step at a time.

| Name | Purpose |
|---|---|
| `build_mesh(bridge)` | Stations along and across the deck, girder and brace lines. |
| `build_bridge_model(bridge, ops)` | The OpenSees model. |
| `dead_load_forces(bridge, ops)` | Girder forces for each construction stage, and their total. |
| `InfluenceSolver(model.as_deck_model())` | Makes influence surfaces: `for_girder_composite_moment(name, element)`, `for_girder_shear(name, element)`, `for_deflection(name, node)`, `for_bearing_reaction(name, node, stiffness)`. |
| `find_critical_position(surface, cross_section, span_m, adverse, wearing_course_thickness_m)` | The worst legal traffic for one surface. |
| `rank_all_positions(...)` | Same arguments; every lane arrangement tried, best first. |
| `live_load(model, critical, surface)` | A critical position as an ordinary load case. |
| `applied_live_loads(bridge, critical, surface)` | The same, as rows of wheel loads and area patches. |
| `analyze_load_case(model, load_case, ops)` | Solve one load case; returns the forces in every girder. |
| `result_dataset(model, ops, name)`, `merge_datasets(datasets)` | Results as an xarray dataset. |
| `bearing_reactions(model, ops)` | Upward vertical bearing reactions in kN, keyed by `(girder, station)`, including both ends. |
| `brace_forces(model, ops)` | Axial truss forces in kN, tension positive, keyed by `(pair_index, brace_station_index, role)`. Includes end-station members. |

`for_girder_composite_moment` and `for_girder_shear` accept keyword-only `end="i"` (the existing default)
or `end="j"` to read the opposite element end. Influence responses use each element's own section and lever arm.

## Errors

Setu raises a clear error instead of guessing: a missing input, a strip name it does not know, a load for a strip the deck does not have, a vehicle that does not fit, or surfacing outside the range Table 15B covers. The message names the value at fault.

A nonzero OpenSees analysis status raises `setu.errors.BackendError`. Temporary loads are removed after a
failed solve so the next case starts cleanly. Exceptions while applying or reading a case also remove its temporary loads.
