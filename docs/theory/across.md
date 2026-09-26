# Search across the carriageway

`setu/analysis/across_carriageway.py` and `setu/irc6/lanes.py`. With each vehicle's worst response known at every lateral position, this step decides **which lanes are loaded, by what, and where**.

<div class="anim" data-anim="lanes"></div>

## 1. Envelopes per block

A carriageway is filled with *blocks*: **Class A lanes** and **70R zones**. For each block type, the envelope $E(z)$ is the worst response over the vehicles allowed in it, at each lateral position z, together with which vehicle gave it (`envelope_every_block`). On a carriageway narrower than 5.3 m, a Class A lane's envelope also includes the residual 500 kg/m² on the width it leaves uncovered (Table 6).

## 2. The lane patterns the code allows

`list_admissible_arrangements` enumerates every sequence of blocks, left to right, that:

- uses no more design lanes than Table 6 gives for the width (a 70R zone counts as two);
- fits, using Table 3 widths: a Class A lane is 2.3 m with 0.15 m to the kerb and a gap to the next Class A lane of 1.2 m, closing to 0.4 m on narrow carriageways; a 70R zone is 5.3 m alone, 7.25 m at an edge, 7.0 m inside;
- is one of the Table 6A drawings: at most two 70R vehicles, each 70R zone reaching a kerb or another 70R zone.

## 3. Packing and sliding

Each pattern is packed hard against the left kerb (`fit_blocks_between`), which leaves some **sliding room** at the right. A Class A vehicle is pinned to the middle of its lane. A 70R vehicle may stand anywhere in its zone with its clearances kept, and its best spot is searched inside the zone (ends, 41 even points, and the envelope's kinks).

Offsets to try are 41 evenly spread values from 0 to the sliding room, **plus** every offset that puts a vehicle centre exactly on a kink of an envelope.

## 4. Dynamic programming over blocks

Blocks may slide **independently**, but must stay in order: a block's offset is at least the one to its left (gaps may open up, never close). For blocks $b = 1 \dots m$ with contribution $c_b(o)$ at offset o:

$$
S_1(o) = c_1(o), \qquad S_b(o) = c_b(o) + \max_{o' \le o} S_{b-1}(o')
$$

Again the inner maximum is a running maximum, and back-pointers give every block's offset (`place_vehicles`).

## 5. Lane reduction and several carriageways

The best placement of each pattern gives one *case* per carriageway. For a deck with several carriageways, every combination of one case per carriageway is formed. Its total is multiplied by the Table 8 reduction for the **total** number of design lanes loaded (1.0, 1.0, 0.9, then 0.8 for four or more). All combinations are ranked; the worst is the critical arrangement (`rank_all_positions` returns them all).

## 6. Footway, and exact placement

The footway load (cl. 206.3 intensity, reduced with span, and with footway width for spans over 30 m) is added on every footpath where the surface is adverse, times the same lane reduction.

Finally each winning vehicle is **re-solved exactly at its chosen centre** (`place_exactly`) to get its precise x, its train, and its impact factor. The result is a `CriticalPosition`: vehicles, lane pattern, lane reduction, residual UDL and footway strips, and the response.
