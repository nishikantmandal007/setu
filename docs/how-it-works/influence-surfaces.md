# Influence surfaces

## The question

A truck on a bridge makes girder 2 bend. How much depends on **where** the truck stands. Put it near the bearing and girder 2 hardly notices. Put it at midspan, right above girder 2, and the girder bends a lot.

To design girder 2 we need the worst position. Before that, we need a quick way to answer *"how much does girder 2 bend if a load stands **here**?"* for any "here" on the deck.

## The map

Imagine placing a 1 kN load on every point of the deck, one at a time, and writing down the moment in girder 2 at midspan each time. Colour each point by that number, and you get a map. That map is the **influence surface**.

<div class="anim" data-anim="influence"></div>

Once you have the map, any load is easy. A wheel of 57 kN standing where the map reads 5.2 causes 57 × 5.2 = 296 kN·m. A whole truck is the sum over its wheels:

$$
M = \sum_{\text{wheels}} P_i \; \eta(x_i, z_i)
$$

where $P_i$ is the wheel load and $\eta(x_i, z_i)$ is the map value under that wheel. A uniform lane load is the map value times the pressure, added up over the loaded area.

!!! info "One map per result"
    Each result has its own map. Setu builds, for every girder: the moment at midspan and at three sections just off it, the shear at the support, the bearing reaction, and the midspan deflection.

## Getting the map with one solve

Placing a load on every point and solving the bridge each time would take thousands of solves. Setu uses a shortcut from structural mechanics called **reciprocity** (Maxwell–Betti), also known as the *adjoint method*:

> Apply a special "virtual" action at the place you care about. The way the deck moves under it **is** the influence surface.

For a bending moment the virtual action is a unit **kink** (a relative rotation) in the girder at that section. For a shear it is a unit relative slip. For a deflection it is simply a 1 kN load at that point, and for a bearing reaction a 1 kN load on the bearing. One solve, and every deck point has its value.

<div class="anim" data-anim="adjoint"></div>

## Checked, not assumed

After the search, Setu places the winning vehicles on the full model as ordinary loads and solves it normally. The result matches what the map predicted, for every girder and every result. The web app does this check on every run.
