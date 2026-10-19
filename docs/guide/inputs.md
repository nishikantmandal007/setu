# Describing a bridge

A bridge is one `BridgeInput`. Every field is required; Setu never fills in a value for you. Each name carries its unit.

```python
BridgeInput(span_m, skew, cross_section, deck, girders, bracing, mesh,
            steel, concrete, wearing_course_unit_weight_kn_m3, added_dead_loads)
```

## The bridge

| Field | Meaning |
|---|---|
| `span_m` | Distance between bearings (m). |
| `skew` | Tan of the skew angle. `0` is a square deck. |
| `wearing_course_unit_weight_kn_m3` | Unit weight of the surfacing (kN/m³). |

## Cross-section

The deck, left to right, as named strips and their widths:

```python
DeckCrossSection.from_widths({
    "footpath_left": 1.5, "kerb_left": 0.45, "carriageway_1": 4.5, "median": 0.6,
    "carriageway_2": 4.5, "kerb_right": 0.45, "footpath_right": 1.5,
})
```

A strip's **name tells Setu what it is**: it must start with `footpath`, `kerb`, `carriageway`, `median`, `crash_barrier` or `railing`. Vehicles go only on carriageways, pedestrians only on footpaths.

## Deck, girders, bracing

| Class | Fields |
|---|---|
| `DeckSlab` | `thickness_m`, `overhang_m` (slab past the outer girder), `wearing_course_thickness_m` |
| `Girders` | `count`, either shared `section` or keyword-only `sections` |
| `PlateGirderSection` | `top_flange_width_m`, `top_flange_thickness_m`, `bottom_flange_width_m`, `bottom_flange_thickness_m`, `web_height_m`, `web_thickness_m` |
| `Bracing` | `arrangement` (`X`, `XT`, `XB`, `XTB`, `K`, `KT`), `station_count` (brace lines along the span, both ends included), `area_m2` |

Girders are spaced evenly between the two overhangs.

`Girders(count, section)` keeps the existing uniform input. For different sections across the deck use
`Girders(count=3, sections=[left_section, middle_section, right_section])`. Supply exactly one form;
the list must contain one section per girder, left to right. `girders.section_at(index)` reads either form.
All girder tops meet the slab underside; centroid and bottom-flange levels follow each individual section.
K-brace meeting nodes bisect the line between adjacent bottom-flange nodes. Sections remain constant along each girder.

`model.girders[index]` contains the individual calculated properties. `model.girder` remains the first
section for existing uniform-model callers; use the indexed form for bridges with different sections.

`Bracing` also accepts optional `steel_grade` and `end_diaphragm_steel_grade` labels. End diaphragms are represented by the end brace lines; all steel members use the entered `Steel` elastic properties.

## Materials

| Class | Fields |
|---|---|
| `Steel` | `elastic_modulus_mpa`, `poissons_ratio`, `unit_weight_kn_m3` |
| `Concrete` | `elastic_modulus_mpa` (Ecm), `poissons_ratio`, `unit_weight_kn_m3` |

Both materials accept an optional `grade` label, for example `"E350"` or `"M35"`. Labels record the specification and appear in the web verification report; they do not infer E, strength or density. Omitted labels are reported as **Not specified**.

## Superimposed dead load

`AddedDeadLoads(footpath_kpa, kerb_kn_per_m, median_kn_per_m, crash_barrier_kn_per_m, railing_kn_per_m)`

The footpath load is per square metre of footpath. The others are per metre run of their strip. Give `0` for a strip the deck does not have.

## Mesh

`MeshSettings(panels_between_braces, target_size_across_width_m)` sets how fine the model is. For design use **16–25 panels** and **0.10–0.15 m** (see [Accuracy and limits](../accuracy.md)).

## Site loads (optional)

| Class | Fields |
|---|---|
| `WindSite` | `basic_wind_speed_mps`, `terrain` (`"plain"` or `"obstructed"`), `height_m`, `funnelling`, `solid_barrier_height_m`; optional overrides for gust, drag, lift and areas |
| `SeismicSite` | `zone` (`"II"`–`"V"`), `soil` (`"I"`–`"III"`), `importance_factor`, `period_s`, `response_reduction` |
| `TemperatureSite` | `shade_max_c`, `shade_min_c` |
| `CustomLoad` | `group`, `shape` (`"point"`, `"line"`, `"area"`), `magnitude` (kN, kN/m or kN/m²), `x_from_bearing_m`, `z_from_left_edge_m`, and `x_end_m`, `z_end_m` for a line or area |

### Seismic overrides

`SeismicSite` also accepts keyword-only `horizontal_coefficient`, `vertical_coefficient`,
`dead_weight_kn`, `live_weight_kn` and `include_vertical`. Omit them to keep the existing SP:114 calculation.

- Coefficients are effective **force divided by weight**, already including response reduction and any
  damping adjustment. An explicit coefficient is used directly, including zero; the automatic minimum is not applied to it.
- `live_weight_kn` is the full live weight **before** the 20% participation factor. Longitudinal inertia uses
  dead weight only; transverse and vertical inertia use dead plus participating live weight. `dead_weight_kn`
  changes seismic weight only, without changing dead-load analysis.
- Weight overrides scale the native nodal weight distribution. If no native weight exists, the override is
  distributed by tributary deck area. This is distinct from always distributing the entire seismic force uniformly.
- `include_vertical=True` requests vertical seismic in any zone; `False` disables it. When omitted, an explicit
  vertical coefficient requests the case, otherwise the existing zone IV/V rule applies.

For OsdagBridge's current IRC:6 coefficients, the Core adapter must pass `Ah / R` and `Av / R`.
Its existing damping calculation belongs to that coefficient calculation. Setu's automatic SP:114 method
uses the existing 5% basis; adding these overrides does not switch the automatic code method.
The returned `SeismicLoadCases.live_weight_kn` remains the **participating** live weight, as before.

### Wind scope and force height

Uniform-depth bridges retain the existing automatic wind calculation. Unequal-depth bridges require
all three engineer-supplied inputs: `exposed_area_m2`, `drag` and `force_height_above_deck_m`.
Setu refuses the unsupported automatic approximation rather than using maximum girder depth as windward depth.
`force_height_above_deck_m` is signed metres above the **top of the concrete slab**; a negative value
places the resultant below it. Setu adds half the slab thickness to reach its deck-node reference.
The overrides define one resultant magnitude and height for both transverse directions; separate
analyses are needed for different directional inputs. This API does not calculate unequal-girder shielding.

### Braking height

`girder_design_values(..., braking_height_above_deck_m=value)` and
`braking_load_cases(model, critical, height_above_deck_m=value)` accept metres above the **deck top**.
Zero is valid. Setu adds half the slab thickness to reach its deck-node reference. With the argument omitted,
the existing 1.2 m above-road default still includes wearing-course thickness. The override changes the moment
arm and preserves the standard braking force calculation and wheel distribution.

Custom load groups `DL`, `SIDL`, `DW`, `LL`, `EL`, `WL`, `TL` are combined as dead, dead, surfacing, live, seismic, wind and thermal. Any other group name is only used by a combination you define with `custom_combination(name, {group: factor})`.
