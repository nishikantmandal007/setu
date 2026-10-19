# Reading the results

`girder_design_values(bridge, ...)` returns a `DesignValues` object.

## Design values

```python
value = results.girders[girder][response][limit_state][adverse]
```

| Key | Options |
|---|---|
| `girder` | `0` … `count − 1`, left to right |
| `response` | `"maximum composite moment"`, `"support shear"`, `"bearing reaction"` |
| `limit_state` | `"ultimate, basic"`, `"ultimate, seismic"`, `"serviceability, rare"`, `"serviceability, frequent"`, `"serviceability, quasi-permanent"` |
| `adverse` | `"maximum"` (largest positive) or `"minimum"` (largest negative) |

The constants for these names are in `setu.utils.constants` (`MAX_MOMENT`, `SUPPORT_SHEAR`, `BEARING_REACTION`, `BASIC`, `RARE`, `BIGGER_IS_WORSE`, …).

Each value tells its story:

| Field | Meaning |
|---|---|
| `value` | The design value (kN·m or kN). |
| `combination` | Which combination produced it, e.g. `"ultimate, basic, live leading"`. |
| `shares` | How much each load group contributed after its factor. |
| `at_m` | Where along the girder it governs. |

`results.governing(response, limit_state, adverse)` gives the worst girder and its value.

## Everything else

| Attribute | What it holds |
|---|---|
| `criticals[girder, response, adverse]` | The critical position: vehicles (name, centre z, front x of each vehicle in the train, impact), lane pattern, lane reduction, footway and lane-load strips, and the live effect. |
| `surfaces[...]`, `stations[...]` | The influence surface and the station behind each critical position. |
| `dead` | Girder forces from each construction stage (`dead.stages`) and their total (`dead.total`). |
| `deflections[girder]` | `live_m` (traffic with impact, no footway), `dead_m` by stage, `total_m`. |
| `fatigue_stresses_mpa[girder][face]` | Nominal longitudinal steel fatigue stress `range`, `largest`, `smallest` (MPa), `at_m`, truck centre z, front x at each extreme, and impact multiplier. Faces: `"steel top"`, `"steel bottom"`. |
| `fatigue[girder][response]` | Original fatigue force ranges: moment in kN·m and shear in kN, retained for existing callers. |
| `combinations[girder][response][name][adverse]` | Each individual combination's envelope, with the same value, station and factored shares as a governing result. |
| `live_shear_range_kn[girder]` | Live shear range at the support. |
| `place_surfaces[girder, place]`, `place_criticals[girder, place, adverse]` | The influence surface and critical position at every design place `(response, station)`, not only the worst one. |
| `thermal` | Effective temperature range, bearing movement, and heating/cooling stresses per girder. |

Signs: every force is an internal force, **sagging positive**; deflection is positive downward.

For unequal girder sections, the high-level moment check includes both sets of stations near midspan,
and support shear/reaction checks include both bearing ends. The reported `at_m` records the governing station.
These are sampled design stations, not a traffic optimization at every point along the span. High-level
deflections remain midspan values; use the solved nodal curves for along-girder maxima of individual cases.

`GirderForces.reaction_kn` is the near-end reaction and `end_reaction_kn` the far-end reaction; both are required,
and both are kept by staged-response scaling and summation.

## Files for other programs

- `result_dataset(model, name)` and `merge_datasets([...])` give an **xarray** dataset of element forces and node displacements, in the layout OsdagBridge reads (kN, kN·m, m).
- `applied_live_loads(bridge, critical, surface)` gives every wheel as a point load (with impact and lane reduction) and the lane and footway loads as area patches, ready to type into another program to check a critical position.

Capture native support and brace results immediately after a successful physical-case solve:

```python
forces = analyze_load_case(model, case)
dataset = result_dataset(model, case.name)
reactions_kn = bearing_reactions(model)
braces_kn = brace_forces(model)
```

Bearing station indices are `0` and `model.mesh.stations_along_span - 1`. Brace station indices run over
the bracing lines, with pair index `0` joining girders `0` and `1`. Roles identify individual diagonals or
top/bottom chords. The existing girder dataset schema is unchanged; trusses do not have fictitious beam moments.
Building another model wipes the OpenSees domain, so results must be captured before a rebuild.

## Brace design values

`brace_design_values(bridge, ...)` solves an axial-force influence surface (`InfluenceSolver.for_brace_axial`)
for every truss brace member and searches IRC:6 traffic independently for each member and adverse direction:

```python
braces = brace_design_values(bridge, wind=wind, seismic=seismic)
value = braces.members[pair_index, brace_station_index, role][limit_state][adverse]
critical = braces.criticals[pair_index, brace_station_index, role, adverse]
```

Need girders as well? `bridge_design_values(...)` returns both from one analysis, so the dead load
stages (whose brace forces are recorded as `dead.brace_stages`), the model and the solver are not built twice.

It also returns `.diagrams`, forces along every girder for the load behind each result:

| Attribute | What it holds |
|---|---|
| `governing[girder, response, limit_state, adverse]` | Each governing girder value replayed as real loads (its live arrangement, braking direction, wind alternative, seismic case and factors) and solved along the span: `.governing` is the `GoverningValue`, `.forces[k]` every girder's `GirderForces`. At `governing.at_m` it gives back the design value. |
| `live[girder, response, adverse]` | Each critical live arrangement solved along the span, with impact, without braking. |
| `braking[girder, response, adverse]` | The braking direction chosen with that arrangement, solved on its own. |
| `wind[name]` | Each wind load case solved along the span. |
| `girder_positions_m[girder]`, `edge_positions_m["left" / "right"]` | Plan position `(x, z)` of each girder node and deck edge node, station by station. |

Member keys `(pair_index, brace_station_index, role)` match `brace_forces(model)`. Values are axial
truss forces in **kN, tension positive**: `BIGGER_IS_WORSE` (`"maximum"`) gives maximum tension and
`SMALLER_IS_WORSE` (`"minimum"`) gives maximum compression, each returned as a `GoverningValue` with its
governing combination, factored load-group `shares`, and longitudinal station `at_m`. Feed axial demands
directly to member design; do not resolve them again as transverse-beam shear.
