# From forces to design values

By now Setu knows, for every girder, the effect of each dead stage, of the worst traffic, and of wind, earthquake and temperature. IRC:6 Annex B says how to combine them.

## One leading load at a time

Loads that come and go (traffic, wind, temperature) are unlikely to be at their worst all together. So Annex B lets **one** of them *lead* with its full factor, while the others *accompany* with a smaller factor. Setu tries each one as the leader and keeps the worst.

<div class="anim" data-anim="combination"></div>

Other rules Setu follows:

- A variable load that would **reduce** the effect is left out.
- Permanent loads take their larger factor where they add to the effect and their smaller factor where they relieve it.
- No traffic is taken on the bridge in winds above 36 m/s at deck level (cl. 209.3.7).

The limit states checked are **ULS basic**, **ULS seismic**, **SLS rare**, **SLS frequent** and **SLS quasi-permanent**. Every design value records which combination produced it and how much each load contributed.

## The other checks

**Deflection (IRC:22 cl. 604.3.2).** Traffic with impact but without the footway load must stay under span/800. Dead load, surfacing and traffic together must stay under span/600 (camber may offset this, as IRC:24 cl. 504.6 allows).

**Wind (IRC:6 cl. 209).** Table 12 pressure with the gust factor and drag coefficient for plate girders, acting sideways, along and upward, plus wind on the traffic.

**Earthquake (IRC:SP:114).** The design coefficient is

$$
A_h = \frac{Z}{2}\cdot\frac{S_a/g}{R/I}
$$

but never below the Table 5.2 minimum. 20 % of the traffic is included, and the three directions combine as 100 % + 30 % + 30 %.

**Temperature (IRC:6 cl. 215).** A simply supported span with a free bearing expands freely, so temperature gives the girders no force. What it does give is **stress through the depth** when the slab is hotter or colder than the steel (Fig. 17b / Table 15B). Setu reports these heating and cooling stresses for each girder, and the bearing movement.

**Custom loads.** Your own point, line or area loads, filed under a group (DL, SIDL, DW, LL, EL, WL, TL, or a name of your own that only your own combination uses).
