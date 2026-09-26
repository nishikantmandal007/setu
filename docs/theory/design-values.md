# Design values

`setu/postprocess/design_values.py`, function `girder_design_values`.

## Places

A *place* is a response at a station. For each girder Setu designs at:

| Response | Stations |
|---|---|
| Composite moment | midspan, and 0.02L, 0.04L, 0.06L towards the first bearing |
| Support shear | first bearing |
| Bearing reaction | first bearing |

The design value of a response is the worst over its places.

## Effects at a place

| Group | How it is obtained |
|---|---|
| **dead** | stages 1–3 read from the solved girder forces (bare steel, then long-term composite) |
| **surfacing** | stage 4, kept apart for its own factor |
| **live** | the critical position for this place and direction, plus the worse of braking forwards or backwards; one value for each direction |
| **wind** | every mix of wind from the left or right, along the span either way, and lift up or down (8 alternatives); when traffic is in the combination, wind on the vehicles is added |
| **seismic** | longitudinal (dead weight), transverse and vertical (dead weight plus 20 % of the critical traffic, impact excluded), combined 100 % + 30 % + 30 % with every sign |
| **custom** | each custom load case, added into its group |

Live, braking, wind, seismic and custom effects are read by reciprocity from the place's influence surface ([Influence surfaces](influence.md)).

## Combinations

`setu/irc6/combinations.py` generates the IRC:6 Annex B combinations. For ULS basic, SLS rare and SLS frequent, each variable load leads in turn; for the others, the loads that have a leading factor lead. Above 36 m/s wind at deck level, traffic and wind are not combined.

For a combination and a direction (maximum or minimum), each group:

1. takes its **worst alternative** in that direction (for example, the worst of the 8 wind cases);
2. takes its **adding** factor if it makes the response worse, or its **relieving** factor if it helps (a variable load that helps is ignored, factor 0);
3. is added. The design value is the largest over combinations, recorded with its combination, each group's factored share, and the station.

## Deflection

IRC:22 cl. 604.3.2. Live deflection is the worst ranked arrangement on the deflection surface **after taking the footway load out** (the clause allows it), with impact. Each dead stage's midspan deflection is read from its solve; the total is their sum plus the live deflection. Limits: L/800 live, L/600 total.

## Fatigue

IRC:6 cl. 204.6 (`setu/analysis/fatigue.py`). The 40 t fatigue truck runs along every line on each carriageway that keeps the outer tyre edge 150 mm from the kerb, with half the cl. 208 impact. For each line the range of one passage is $\max(R_{\max}, 0) - \min(R_{\min}, 0)$: the empty bridge counts. The worst line is kept, for the moment near midspan and the shear at the support.

## Braking

IRC:6 cl. 211. 20 % of the first train in a lane plus 10 % of those following, plus 5 % of the load in lanes beyond two, from the vehicles actually on the span. It acts along the road 1.2 m above the surface, applied at the deck nodes under the vehicles in proportion to their wheel loads, as a force and the matching moment.

## Wind, seismic, temperature

- **Wind** (cl. 209): hourly mean speed and pressure from Table 12 at the deck height, scaled for the basic wind speed; gust factor 2.0; drag 2.2 for one girder, 2(1 + c/20d) up to 4.0 for several; lift 0.75; longitudinal 25 %; wind on traffic with C<sub>D</sub> = 1.2 over 3 m at 1.5 m above the road.
- **Seismic** (IRC:SP:114): $A_h = (Z/2)(S_a/g)/(R/I)$ with the Fig. 5.1(a) spectrum, never below Table 5.2; vertical at 2/3 of Z in zones IV and V; weights lumped at the nodes.
- **Temperature** (cl. 215): no girder force on a simply supported span with a free bearing. Heating and cooling primary stresses through each girder's composite section (Fig. 17b / Table 15B profiles on the IRC:22 cl. 603.2.1 effective width) and the free bearing movement $\alpha\,\Delta T\,L$.
