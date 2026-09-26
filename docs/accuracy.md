# Accuracy and limits

## How fine the mesh should be

Tested on the 35 m example bridge (`examples/bridge.toml`):

- **Along the span**, results settle by 16 panels between braces. Moment, reaction, deflection and fatigue change by under 0.1 % beyond that.
- **Across the deck**, the middle girders settle quickly, but the **edge girder** converges slowly: at 0.25 m its moment is about 1.6 % low, and at 0.10 m about 0.6 % low.
- **Support shear** is read in the first girder element and converges slowly (about 1.5 % low at 25 panels). The **bearing reaction** is converged and never smaller, so use it where a safe support shear is needed.

**Use 16–25 panels between braces and 0.10–0.15 m across the deck for design.**

## What Setu covers

- Simply supported, single span, steel plate girders with a composite RC deck.
- Un-propped construction.
- IRC Class A, 70R wheeled and 70R tracked vehicles, footway load, braking, fatigue truck.
- Wind, seismic (seismic coefficient method), temperature, custom loads.

## Known limits, being worked on

| Item | Effect |
|---|---|
| Every girder is held along the span at the fixed bearing | Relieves the edge girder: its live moment comes out about 5 % low and its ULS moment about 2 % low. The fix, holding one girder only, is planned. |
| Kerbs 0.6 m or wider do not yet carry footway load (IRC:6 206.4) | Name a wide kerb as a footpath for now. |
| Vertical seismic is applied only in zones IV and V | SP:114 4.2.1 also asks for it for bearings in zones II and III. |
| Surfacing outside 50–100 mm is refused | Table 15B has no values there. |

## Checks built in

- Each critical position is re-solved in OpenSees as ordinary loads; it matches the influence-surface prediction.
- The test suite races the search against brute-force searches, and pins known answers so a change cannot move them unnoticed.
