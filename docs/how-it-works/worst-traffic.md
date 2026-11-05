# Finding the worst traffic

With an influence surface in hand, finding the worst position means placing code vehicles on it and keeping the placement with the biggest effect.

<div class="anim" data-anim="replay"></div>

!!! info "Every girder, every design place"
    Pick any girder and result in the animation. Setu runs this search for **every girder**, at every place it designs: the moment at midspan and at 0.02L, 0.04L and 0.06L towards the bearing (the largest live moment stands a little off midspan), the shear and the reaction at the bearing, and the midspan deflection. That is seven influence surfaces per girder, each searched for its worst traffic, plus a top- and a bottom-flange stress surface at each of the four moment sections for fatigue. Girders that differ across the width also check the mirrored moment sections and the far bearing.

## What Setu places

| Item | Rule | IRC:6 clause |
|---|---|---|
| **Class A** train | 8 axles, 554 kN, 1.8 m wheel gauge; trains follow each other at least 18.5 m apart | 204.1, Fig. 3 |
| **70R wheeled** | 7 axles, 1000 kN, wheel lines 1.93 m apart | 204.1, Fig. 1 |
| **70R tracked** | two 4.57 m × 0.84 m tracks, 700 kN | 204.1, Fig. 1 |
| **70R single axle / bogie** | 200 kN on one axle; 2 × 200 kN at 1.22 m; wheeled 70R impact, 2 lanes for braking, 30 m to the next vehicle | 204.1, Fig. 1 note 3 |
| **Congestion** (`DeckCrossSection(congestion=True)`, set by the authority) | each placement also tried with the vehicles × Table 7 (1.15 to 30 m … 1.70 from 70 m), after impact, lane reduction kept, no braking; never with SV | 204.4, Table 7 |
| **Crowd load** (`DeckCrossSection(crowd_load=True)`) | footways 5 kN/m² with no span reduction, and a case with 5 kN/m² over every carriageway and footway (no impact, no braking) | 206.1, 206.3 |
| **Class SV** (`special_vehicle_design_values`) | 3850 kN: 60, 95, 95 kN prime mover, 5.427 m, 20 trailer axles of 180 kN at 1.5 m, 8 tyres an axle; centreline within 300 mm of its carriageway's centreline; nothing else on that carriageway or its footways, no impact or braking on it; other carriageways keep their traffic; factor 1.15 / 1.0 / 0.75; required for new bridges except rural, district and village roads | 201.1 (Amendment 10), 204.5, Fig. 6, 6A, 6B |
| **Lanes** | how many design lanes fit, from the carriageway width | Table 6, 6A |
| **Where vehicles may stand** | clearances to the kerb and to each other | 204.3, Table 3 |
| **Impact** | vehicle loads are increased by the impact factor for a steel bridge | 208 |
| **Several lanes loaded** | 3 lanes × 0.9, 4 or more × 0.8 | 205, Table 8 |
| **Residual lane load** | on carriageways narrower than 5.3 m: 5 kN/m² on the width left beside the Class A lane | Table 6 |
| **Footway** | pedestrian load, falling with span | 206.3 |
| **Braking** | 20 % of the first train, 10 % of the following ones | 211 |

Loads are the kN values IRC:6-2017 prints since Amendment 10 (in force from 1 October 2026): Class A axles 27, 114 and 68 kN, 70R axles 80, 120 and 170 kN, footway 4 kN/m². There is no tonne-to-kN conversion.

Each vehicle is tried **both ways round** (a Class A lorry is not symmetric) and at every position across its lane.

## How the search works

1. **Along the span.** For each vehicle and each position across the deck, Setu slides the vehicle along the span and records its biggest effect. Because the map is known, this is fast arithmetic, not a new analysis.
2. **Across the carriageway.** It then combines lanes: which lane arrangement (for example two Class A lanes, or one 70R zone) gives the largest total once impact, lane reduction, residual lane load and footway load are included.
3. **Exact placement.** The best arrangement is refined to its exact position, and the result is recorded with every vehicle's place.

This happens for **every girder separately**. The worst position for an edge girder is usually close to the kerb; for a middle girder it is near the centre.

!!! example "See it on your own bridge"
    The web app's **Search replay** tab plays this search for your bridge, using its real influence surfaces. See [Web app](../guide/web-app.md).

## Fatigue

For fatigue, IRC:6 cl. 204.6 uses the Fig. 7A Fatigue Load Train of Amendment 8: the 400 kN truck, which must be included, with 120 kN trucks ahead and behind at 20 m from rear axle to front axle, as many as the influence line holds. Setu tries every such train, rolls each along the worst line (outer tyre at least 150 mm from the kerb) in one passage with half the normal impact, and keeps the worst. The fatigue **range** is the largest effect minus the smallest, including the empty bridge.
