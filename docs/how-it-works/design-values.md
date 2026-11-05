# From forces to design values

By now Setu knows, for every girder, the effect of each dead stage, of the worst traffic, and of wind and earthquake. IRC:6 Annex B says how to combine them.

## One leading load at a time

Loads that come and go (traffic, wind) are unlikely to be at their worst together. So Annex B lets **one** of them *lead* with its full factor, while the others *accompany* with a smaller factor. Setu tries each one as the leader and keeps the worst. (Temperature takes part in the combinations too, but on a simply supported span with a free bearing it adds no girder force; see below.)

<div class="anim" data-anim="combination"></div>

Other rules Setu follows:

- A variable load that would **reduce** the effect is left out.
- Permanent loads take their larger factor where they add to the effect and their smaller factor where they relieve it.
- No traffic is taken on the bridge in winds above 36 m/s at deck level (cl. 209.5.2.4, Amendment 10).

The limit states checked are **ULS basic**, **ULS seismic**, **SLS rare**, **SLS frequent** and **SLS quasi-permanent**. Every design value records which combination produced it and how much each load contributed.

## The other checks

**Deflection (IRC:22 cl. 604.3.2).** Traffic with impact but without the footway load must stay under span/800. Dead load, surfacing and traffic together must stay under span/600 (camber may offset this, as IRC:24 cl. 504.6 allows).

**Wind (IRC:6 cl. 209, Amendment 10).** Design speed Vz = Vb k1 k2 k3 k4 and pressure 0.6 Vz², on the deck's area in elevation with the Table 8 drag for its width-to-depth ratio, acting sideways, along (25 %) and up or down at B/4 off centre, plus wind on the traffic. Spans over 40 m or piers over 20 m also take the hourly mean method with the gust factor, resolved for skewed wind.

**Earthquake (IRC:SP:114).** The design coefficient is

$$
A_h = \frac{Z}{2}\cdot\frac{S_a/g}{R/I}
$$

but never below the Table 5.2 minimum. 20 % of the traffic is included, and the three directions combine as 100 % + 30 % + 30 %.

<div class="anim" data-anim="temperature"></div>

**Construction stage (IRC:22 cl. 604.1.1, IRC:6 cl. 218 and Annex B Table B.2).** While the slab is cast, the bare steel alone carries its own weight, the wet slab (+1 kN/m³ for wet concrete), the shuttering and the construction live load. IRC gives no value for the last two: they come from the construction programme as inputs. `construction_design_values` factors them per Table B.2 (dead 1.35 / 1.0, shuttering 1.35, construction live load 1.35, wind during construction 1.5 leading or 0.9 accompanying with a 10-year return period and C<sub>D</sub> = 2(1 + c/20d) ≤ 4; seismic during construction 0.75 with the live load at 1.0 and an importance factor of 1 per IRC:SP:114 cl. 4.5) for every girder and brace member. These are the moments the construction-stage lateral-torsional buckling check (IRC:22 cl. 603.3.3.1) needs.

**Temperature (IRC:6 cl. 215).** A simply supported span with a free bearing expands freely, so temperature gives the girders no force. What it does give is **stress through the depth** when the slab is hotter or colder than the steel (Fig. 16b). Setu reports these heating and cooling stresses for each girder, and the bearing movement.

**Custom loads.** Your own point, line or area loads, filed under a group (DL, SIDL, DW, LL, EL, WL, TL, or a name of your own that only your own combination uses).
