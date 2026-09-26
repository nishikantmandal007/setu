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
| `fatigue[girder][response]` | Fatigue `range`, `largest`, `smallest`, and where the truck stood. |
| `live_shear_range_kn[girder]` | Live shear range at the support. |
| `thermal` | Effective temperature range, bearing movement, and heating/cooling stresses per girder. |

Signs: every force is an internal force, **sagging positive**; deflection is positive downward.

## Files for other programs

- `result_dataset(model, ops, name)` and `merge_datasets([...])` give an **xarray** dataset of element forces and node displacements, in the layout OsdagBridge reads (kN, kN·m, m).
- `applied_live_loads(bridge, critical, surface)` gives every wheel as a point load (with impact and lane reduction) and the lane and footway loads as area patches, ready to type into another program to check a critical position.
