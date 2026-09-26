# Search along the span

`setu/analysis/along_span.py`. For one surface, one vehicle and one lateral position z, find the position x (and, for trains, the positions of every vehicle) that makes the response worst.

## Wheels

`setu/irc6/wheel_loads.py` turns a vehicle into point loads relative to its front axle:

- **Wheeled vehicles**: two wheels per axle, half the axle load each, at ± half the wheel gauge.
- **Tracked vehicle**: each track, spread at 45° through the wearing course (so it grows by the surfacing thickness on every side), is split into a grid of point loads (4 along × 2 across by default) carrying equal shares.

For a skewed deck the offsets are sheared into mesh coordinates first.

## Only the kinks need checking

Along a line of constant z, bilinear interpolation is **linear in x inside each cell**. The response to a vehicle, $\sum_k P_k\,\eta(x + \Delta x_k, z + \Delta z_k)$, is therefore piecewise linear in the vehicle position x, with kinks only where some wheel crosses a mesh station. A linear piece reaches its extreme at an end, so **the worst position is always at one of those kinks**.

<div class="anim" data-anim="breakpoints"></div>

Setu evaluates exactly the set

$$
\mathcal{X} = \{\, x_s - \Delta x_k \;:\; x_s \text{ a station},\ k \text{ a wheel} \,\}
$$

kept to positions where the vehicle is at least partly on the span. There is no step size to choose, and nothing can be missed between steps. All positions and all lateral positions are evaluated in one vectorised pass, in chunks (`span_positions_evaluated_at_once`).

## Lateral positions

Across the deck the envelope of a vehicle is not piecewise linear in general (it is a maximum over x), so Setu samples z densely: an even spread of 241 positions over the carriageways, **plus** every position where a wheel line crosses a width station (`positions_across_width`). The winner is then placed exactly (see [Search across the carriageway](across.md)).

## Trains: dynamic programming

IRC vehicles follow each other in trains with a minimum spacing. Setu adds positions exactly one pitch apart to $\mathcal{X}$ (so vehicles can line up on kinks together) and then places trains of 1, 2, … vehicles by dynamic programming (`place_train`):

$$
B_1(x) = r(x), \qquad B_n(x) = r(x) + \max_{x' \le x - p} B_{n-1}(x')
$$

where $r(x)$ is the response to one vehicle with its front axle at x, and $p$ is the pitch (vehicle length plus minimum gap). The inner maximum is a running maximum, so each $B_n$ costs one pass over $\mathcal{X}$. Back-pointers recover every vehicle's position. The train length giving the worst total wins (`find_worst_train`).

<div class="anim" data-anim="trains"></div>

## Impact and both directions

The vehicle's response is multiplied by its impact factor (IRC:6 cl. 208, `setu/irc6/impact.py`), which depends on the vehicle class and the span. Asymmetric vehicles are also tried turned round (`facing_backwards`), which reverses the axle order.

## Output

For each vehicle and each lateral position the search keeps the worst response, where the leading vehicle stands, and the whole train. These response curves are remembered, so each vehicle is swept only once per surface.
