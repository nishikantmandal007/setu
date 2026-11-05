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

IRC:6 cl. 204.6 (`setu/analysis/fatigue.py`). The 400 kN fatigue truck runs along every line on each carriageway that keeps the outer tyre edge 150 mm from the kerb, with half the cl. 208 impact. For each line the range of one passage is $\max(R_{\max}, 0) - \min(R_{\min}, 0)$: the empty bridge counts. The worst line is kept, for the moment near midspan and the shear at the support.

The web report shows the **nominal longitudinal steel stress range in MPa**. For each checked section near midspan, stress influence surfaces are formed at the top and bottom steel faces using the composite FE model's steel axial force and steel bending moment:

$$\sigma(y) = \frac{1}{1000}\left[\frac{N}{A_s} + \frac{M_s(y_{NA}-y)}{I_s}\right].$$

Here $y$ is measured upward from the bottom steel face, $N$ is tension positive (kN), $M_s$ is the steel moment (kN·m), and section properties are in metres. Each face is searched independently for its worst truck passage, including the unloaded zero. The displayed range is the larger of the two face ranges, with each face's extrema and truck coordinates available for verification. The original force ranges remain available in the API.

This uses the steel forces already produced by the composite shell-and-beam model, rather than treating its total composite moment as a bare-steel moment. Nominal stress ranges are the input to a separate fatigue resistance assessment; detail categories, local stress concentrations and fatigue life are not checked here. See the [FHWA fatigue reference manual](https://www.fhwa.dot.gov/bridge/steel/pubs/nhi16016.pdf) for the distinction between calculating stress ranges and checking fatigue resistance; Setu retains its IRC truck and impact rules.

## Braking

IRC:6 cl. 211. 20 % of the first train in a lane plus 10 % of those following, plus 5 % of the load in lanes beyond two, from the vehicles actually on the span. It acts along the road 1.2 m above the surface, applied at the deck nodes under the vehicles in proportion to their wheel loads, as a force and the matching moment.

## Wind, seismic, temperature

- **Wind** (cl. 209 as replaced by Amendment 10): V<sub>z</sub> = V<sub>b</sub> k<sub>1</sub> k<sub>2</sub> k<sub>3</sub> k<sub>4</sub> (Tables 1, 3), P<sub>z</sub> = 0.6 V<sub>z</sub><sup>2</sup>; F<sub>T</sub> = P<sub>z</sub> A<sub>1</sub> C<sub>D</sub> with A<sub>1</sub> from Fig. 5 / Table 7 and C<sub>D</sub> from Table 8 by B/d (Fig. 7), +3 % per degree of camber; F<sub>L</sub> = 0.25 F<sub>T</sub>; F<sub>V</sub> = P<sub>z</sub> A<sub>2</sub> × 0.9 at B/4. Spans over 40 m or piers over 20 m take the larger of that and the hourly mean method (Table 4, gust factor by terrain category), resolved by the Table 6 skew coefficients. Wind on traffic: C<sub>D</sub> = 1.2 over 3 m above the road, at 1.5 m, pressure at road level + 3 m. Over 36 m/s at deck level no traffic is taken. Read literally, Table 7 also puts the traffic in the deck's area while 209.5.2.3 adds wind on the traffic (decision D18).
- **Seismic** (IRC:SP:114): $A_h = (Z/2)(S_a/g)/(R/I)$ with the Fig. 5.1(a) spectrum, never below Table 5.2; vertical at 2/3 of Z in zones IV and V; weights lumped at the nodes.
- **Temperature** (cl. 215): no girder force on a simply supported span with a free bearing. Heating and cooling primary stresses through each girder's composite section (Fig. 16b profiles, used for any surfacing as IRC:SP:120 does, on the IRC:22 cl. 603.2.1 effective width) and the free bearing movement $\alpha\,\Delta T\,L$.
