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
| `Girders` | `count`, `section` |
| `PlateGirderSection` | `top_flange_width_m`, `top_flange_thickness_m`, `bottom_flange_width_m`, `bottom_flange_thickness_m`, `web_height_m`, `web_thickness_m` |
| `Bracing` | `arrangement` (`X`, `XT`, `XB`, `XTB`, `K`, `KT`), `station_count` (brace lines along the span, both ends included), `area_m2` |

Girders are spaced evenly between the two overhangs.

## Materials

| Class | Fields |
|---|---|
| `Steel` | `elastic_modulus_mpa`, `poissons_ratio`, `unit_weight_kn_m3` |
| `Concrete` | `elastic_modulus_mpa` (Ecm), `poissons_ratio`, `unit_weight_kn_m3` |

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

Custom load groups `DL`, `SIDL`, `DW`, `LL`, `EL`, `WL`, `TL` are combined as dead, dead, surfacing, live, seismic, wind and thermal. Any other group name is only used by a combination you define with `custom_combination(name, {group: factor})`.
