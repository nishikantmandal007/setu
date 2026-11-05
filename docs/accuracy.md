# Accuracy and limits

## How fine the mesh should be

IRC does not specify a mesh; these are numerical choices, measured. Along the span the mesh is set by **element length**, not by panels per brace bay: on a 35 m bridge with 2 brace bays and with 6, the same element length gave the same accuracy. Support shear is read in the first element at the bearing and converges only as that element shrinks, so elements are made short within 1.5 m of each bearing. (Swapping in the bearing reaction would not do: the converged support shear stays 3-6 % below the reaction, the rest going straight into the bearing through the end diaphragm.)

`MeshSettings.preset(name)`, measured on a 35 m, five-girder, 6-bay bridge with girders, braces and every load, against 16 panels per bay x 0.10 m (one process):

| Preset | Along span / at bearings / across | Time | Edge, inner moment | Support shear | Worst brace carrying over 25 % of the largest force |
|---|---|---|---|---|---|
| `fast` | 3.0 m / 0.2 m / 0.25 m | 22 s | -0.35 %, -0.31 % | -0.01 %, +0.60 % | -2.0 % |
| `standard` | 1.5 m / 0.1 m / 0.15 m | 36 s | -0.24 %, -0.12 % | +0.60 %, +1.51 % | -0.8 % |
| `fine` | 0.75 m / 0.05 m / 0.10 m | 95 s | +0.02 %, 0.00 % | +0.95 %, +2.46 % | -0.2 % |

The previous fixed setting, 16 panels per bay x 0.15 m, took 74 s for -0.37 %, -0.03 % moment and -0.23 %, -0.09 % shear. Small end top chords near the bearings (about 3 % of the largest brace force) converge slowly on coarse meshes; they do not govern.

**The edge girder converges slowly across the deck**: the 0.10 m reference itself is about 0.7 % low on the edge girder's moment, extrapolating 0.15 m to 0.10 m. Tying the girder to the slab across its top flange width instead of one line of nodes should help; to be checked against an independent model before changing.

## What Setu covers

- Simply supported, single span, steel plate girders with a composite RC deck; individual sections may differ across the width.
- Un-propped construction.
- IRC Class A, 70R wheeled and 70R tracked vehicles, footway load, braking, fatigue truck.
- Wind, seismic (seismic coefficient method), temperature, custom loads.

Supports now form a true simply supported span: every girder end has its vertical spring, and girder `(count - 1) // 2` alone is held longitudinally at the near bearing and transversely at both bearings. This chooses the middle girder, or the lower-index middle girder for an even count, to keep the fixed point near the deck centre. Braking and longitudinal seismic reach that near bearing; transverse wind and seismic reach the two transverse bearings, while thermal expansion remains free along the span. K-brace meeting nodes follow a girder longitudinally; internal axial links stabilize the bare-steel construction model before the slab joins the girders, without adding ground restraints.

Different-depth girders share a common top-of-steel level. Automatic unequal-depth wind is refused:
the deepest girder is not necessarily the windward girder required by the drag formula, and shielding
and application height need a project-specific assessment. Supply `exposed_area_m2`, `drag` and
`force_height_above_deck_m` together to apply an engineer-defined wind resultant. That resultant is used
in both transverse directions; use separate analyses if direction-specific values are needed.
Bracing still has one arrangement and area across the model. Per-pair bracing
and independent end-diaphragm arrangements require a separately supported model, even when an external
application permits different member-design selections.

## Known limits, being worked on

| Item | Effect |
|---|---|
| Kerbs 0.6 m or wider do not yet carry footway load (IRC:6 206.2) | Name a wide kerb as a footpath for now. |
| Automatic vertical seismic uses the zone IV/V rule and a fixed spectral ordinate | For bearings and other required components in zones II/III, explicitly include vertical seismic. Supply effective coefficients where the automatic method is unsuitable; accepted overrides do not establish code compliance. |
| Slab depth outside 0.2–0.3 m is refused | IRC:6 Fig. 16b gives T1 only for those depths (interpolation allowed). |
| The moment is designed only at midspan and 0.02L, 0.04L, 0.06L towards the bearing | The true peak can fall between two sections: on a 35 m, four-girder bridge an inner girder's governing load gives 0.05 % more moment 0.36 m off the checked section. Small, but unconservative. |

## Checks built in

- Each critical position is re-solved in OpenSees as ordinary loads; it matches the influence-surface prediction.
- The test suite races the search against brute-force searches, and pins known answers so a change cannot move them unnoticed.
- Bearing springs are finite (1e9 kN/m): a unit load over a support can produce a small nonzero moment. Direct support-load checks and a tenfold-stiffness convergence test verify this response without changing the model stiffness.
