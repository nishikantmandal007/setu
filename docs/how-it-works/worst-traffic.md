# Finding the worst traffic

With an influence surface in hand, finding the worst position means placing code vehicles on it and keeping the placement with the biggest effect.

<div class="anim" data-anim="replay"></div>

!!! info "Every girder, every design place"
    Pick any girder and result in the animation. Setu runs this search for **every girder**, at every place it designs: the moment at midspan and at 0.02L, 0.04L and 0.06L towards the bearing (the largest live moment stands a little off midspan), the shear and the reaction at the bearing, and the midspan deflection. That is seven influence surfaces and seven searches per girder.

## What Setu places

| Item | Rule | IRC:6 clause |
|---|---|---|
| **Class A** train | 8 axles, 55.4 t, 1.8 m wheel gauge; trains follow each other at least 18.5 m apart | 204.1, Fig. 3 |
| **70R wheeled** | 7 axles, 100 t, wheel lines 1.93 m apart | 204.1, Fig. 1 |
| **70R tracked** | two 4.57 m × 0.84 m tracks, 70 t | 204.1, Fig. 1 |
| **Lanes** | how many design lanes fit, from the carriageway width | Table 6, 6A |
| **Where vehicles may stand** | clearances to the kerb and to each other | 204.3, Table 3 |
| **Impact** | vehicle loads are increased by the impact factor for a steel bridge | 208 |
| **Several lanes loaded** | 3 lanes × 0.9, 4 or more × 0.8 | 205, Table 8 |
| **Residual lane load** | on carriageways narrower than 5.3 m: 500 kg/m² on the width left beside the Class A lane | Table 6 |
| **Footway** | pedestrian load, falling with span | 206.3 |
| **Braking** | 20 % of the first train, 10 % of the following ones | 211 |

Each vehicle is tried **both ways round** (a Class A lorry is not symmetric) and at every position across its lane.

## How the search works

1. **Along the span.** For each vehicle and each position across the deck, Setu slides the vehicle along the span and records its biggest effect. Because the map is known, this is fast arithmetic, not a new analysis.
2. **Across the carriageway.** It then combines lanes: which lane arrangement (for example two Class A lanes, or one 70R zone) gives the largest total once impact, lane reduction, residual lane load and footway load are included.
3. **Exact placement.** The best arrangement is refined to its exact position, and the result is recorded with every vehicle's place.

This happens for **every girder separately**. The worst position for an edge girder is usually close to the kerb; for a middle girder it is near the centre.

!!! example "See it on your own bridge"
    The web app's **Search replay** tab plays this search for your bridge, using its real influence surfaces. See [Web app](../guide/web-app.md).

## Fatigue

For fatigue, IRC:6 cl. 204.6 uses a single 40 t truck making one passage. Setu rolls it along the worst line (outer tyre at least 150 mm from the kerb) with half the normal impact. The fatigue **range** is the largest effect minus the smallest, including the empty bridge.
