# Mesh convergence — example bridge (26 Sep 2026)

The bridge is `examples/bridge.toml`: a 35 m simply supported span, five plate girders, a 13.5 m deck and a 0.23 m slab. The results are live load (search, with impact) and ULS basic design values for the outer girder (0) and the middle girder (2). Reproduce with `uv run python docs/mesh_convergence.py`.

## Along the span (element size across the deck 0.25 m)

| panels between braces | outer live M (kN·m) | middle live M | middle live V (kN) | middle live R (kN) | middle ULS V | outer fatigue M range | time (s) |
|---|---|---|---|---|---|---|---|
| 4 | 2672.3 | 2733.1 | −391.5 | 448.5 | −1259.7 | 1165.3 | 7 |
| 8 | 2667.1 | 2730.5 | −406.6 | 448.5 | −1299.3 | 1156.5 | 15 |
| 16 | 2665.2 | 2730.1 | −413.9 | 448.1 | −1310.9 | 1154.3 | 26 |
| 25 | 2664.9 | 2730.1 | −417.8 | 447.9 | −1320.8 | 1154.0 | 39 |
| 40 | 2664.7 | 2730.5 | −420.2 | 447.7 | −1326.3 | 1153.9 | 79 |

- Moment, bearing reaction, deflection and fatigue range settle by 8–16 panels (under 0.1%).
- The **support shear keeps rising, to first order.** It is read in the first girder element, and any load within half an element of the bearing goes straight into the bearing instead. Extrapolating to a zero-length element, the live shear is about −424 kN: 25 panels is about 1.5% low, 40 panels about 1%. The ULS shear is closer (−1321 → −1326, 0.4%) because dead-load shear converges fast.
- The **bearing reaction is converged and never smaller than the support shear.** Use it for bearing design. When a conservative design shear at the support is wanted, the reaction is a safe upper bound.

## Across the deck (16–25 panels between braces)

| element size (m) | outer live M (kN·m) | middle live M | outer LL deflection (mm) | outer fatigue M range | time (s) |
|---|---|---|---|---|---|
| 0.60 | 2642.9 | 2725.0 | 11.79 | 1116.6 | 22 |
| 0.40 | 2652.4 | 2728.5 | 11.84 | 1133.9 | 28 |
| 0.25 | 2664.9 | 2730.1 | 11.89 | 1154.0 | 36 |
| 0.15 | 2677.6 | 2735.3 | 11.96 | 1173.5 | 55 |
| 0.10 | 2687.0 | 2737.4 | 12.00 | 1185.7 | 53 |
| 0.075 | 2692.2 | 2738.5 | 12.03 | 1192.1 | 67 |

- The **middle girder** is settled within 0.3% at every size.
- The **outer girder** converges only to first order: its live moment rises about 200 kN·m for every metre of element size removed. Extrapolating to a zero element size gives about 2707 kN·m, so 0.25 m is about 1.6% low and 0.10 m about 0.6% low. The outer girder's fatigue range behaves the same way (about 2.6% low at 0.25 m).
- **Likely cause:** each girder is tied to the slab along a single line of nodes (a knife edge), while the real top flange is 0.55 m wide. As the slab mesh refines, the slab's local flexibility over that line keeps changing how load is shared onto the outer girder, mostly from loads on the overhang and near the kerb. Tying each girder to the deck nodes across its flange width would model it more faithfully and should converge faster. This is logged as a point to investigate.

## Recommended mesh

- Element size across the deck **0.10–0.15 m** (at 0.25 m the outer girder moment is about 1.6% low; at 0.10 m about 0.6%).
- **16–25 panels between braces** along the span.
- Use the **bearing reaction** where a conservative support shear is needed.
- Runtime on this bridge is about 1 minute for the design values; the full CLI with the OpenSees checks and outputs is about 1.5–2 minutes.
