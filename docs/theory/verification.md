# Verification

Setu checks itself at run time, and its test suite (about 880 tests) checks the rest.

## At run time

| Check | What it catches |
|---|---|
| The model must not move under no load before the first influence surface | a load pattern left on the model, which would pollute every surface |
| Each critical position is re-applied to the full model as ordinary loads and solved (web app) | any disagreement between the influence-surface prediction and a direct analysis |
| Inputs are validated with the offending value named | missing inputs, unknown strip names, loads with nowhere to go, surfacing outside Table 15B |

On the example bridge all 35 critical positions agree with the direct solve. The one tolerance, 10⁻³ kN on a support shear, is there because an axle standing exactly on the bearing line is shared through a spring that is rigid only to about 10⁻⁶.

## In the tests

| Kind | Examples |
|---|---|
| **Oracles** | The dynamic programs (trains along the span, blocks across the carriageway) are checked against slow searches that enumerate every possibility; they must give the same answer. |
| **Golden values** | Known answers are pinned to 12 significant figures so a refactor cannot move them silently. |
| **Traceability** | The wheel and patch loads Setu reports sum to what it actually applied, and re-solving them gives the predicted response. |
| **Code clauses** | Each clause value has a test that names the clause, e.g. the 70R wheel lines 1.93 m apart (IRC:6 Fig. 1). |
| **Physics** | Reciprocity, symmetry of symmetric bridges, stage sums, sign conventions, skew. |

Run them with:

```bash
uv run pytest
```

## Mesh convergence

Measured on the 35 m example bridge:

| Panels between braces | Edge girder live M (kN·m) | Middle girder live V (kN) |
|---|---|---|
| 4 | 2672.3 | −391.5 |
| 8 | 2667.1 | −406.6 |
| 16 | 2665.2 | −413.9 |
| 25 | 2664.9 | −417.8 |
| 40 | 2664.7 | −420.2 |

| Size across (m) | Edge girder live M (kN·m) | Middle girder live M (kN·m) |
|---|---|---|
| 0.60 | 2642.9 | 2725.0 |
| 0.40 | 2652.4 | 2728.5 |
| 0.25 | 2664.9 | 2730.1 |
| 0.15 | 2677.6 | 2735.3 |
| 0.10 | 2687.0 | 2737.4 |

The moment settles along the span by 16 panels. Across the deck the edge girder converges to first order (about 2707 kN·m extrapolated), which is why 0.10–0.15 m is recommended. Support shear converges slowly because loads within half an element of the bearing go straight into it; the bearing reaction is the safe value.
