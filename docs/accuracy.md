# Accuracy and limits

## How fine the mesh should be

Tested on a 35 m bridge with five plate girders, a 13.5 m deck and a 0.23 m slab (the web app's default inputs):

- **Along the span**, results settle by 16 panels between braces. Moment, reaction, deflection and fatigue change by under 0.1 % beyond that.
- **Across the deck**, the middle girders settle quickly, but the **edge girder** converges slowly: at 0.25 m its moment is about 1.6 % low, and at 0.10 m about 0.6 % low.
- **Support shear** is read in the first girder element and converges slowly (about 1.5 % low at 25 panels). The **bearing reaction** is converged and never smaller, so use it where a safe support shear is needed.

**Use 16–25 panels between braces and 0.10–0.15 m across the deck for design.**

## What Setu covers

- Simply supported, single span, steel plate girders with a composite RC deck; individual sections may differ across the width.
- Un-propped construction.
- IRC Class A, 70R wheeled and 70R tracked vehicles, footway load, braking, fatigue truck.
- Wind, seismic (seismic coefficient method), temperature, custom loads.

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
| Every girder is held along the span at the near bearing; K-brace meeting nodes are also held longitudinally | These restraints must match the real arrangement. Historical estimates of 5% live/2% ULS moment differences have not been independently revalidated. |
| Kerbs 0.6 m or wider do not yet carry footway load (IRC:6 206.2) | Name a wide kerb as a footpath for now. |
| Automatic vertical seismic uses the zone IV/V rule and a fixed spectral ordinate | For bearings and other required components in zones II/III, explicitly include vertical seismic. Supply effective coefficients where the automatic method is unsuitable; accepted overrides do not establish code compliance. |
| Surfacing outside 50–100 mm is refused | Table 15B has no values there. |

## Checks built in

- Each critical position is re-solved in OpenSees as ordinary loads; it matches the influence-surface prediction.
- The test suite races the search against brute-force searches, and pins known answers so a change cannot move them unnoticed.
- Bearing springs are finite (1e9 kN/m): a unit load over a support can produce a small nonzero moment. Direct support-load checks and a tenfold-stiffness convergence test verify this response without changing the model stiffness.
