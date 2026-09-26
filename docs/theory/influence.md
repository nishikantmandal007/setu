# Influence surfaces

`setu/analysis/influence_surface.py`. An influence surface $\eta(x, z)$ gives, for one response $R$ (the composite moment of girder 2 at midspan, for example), the value of $R$ caused by a unit downward load at deck point $(x, z)$.

## Derivation: one solve per response

The model is linear: $K u = f$, with $K$ symmetric. Take a girder element $e$ between nodes $i$ and $j$. Its end forces in local axes are

$$
q = k_e \, T \, u_e
$$

where $k_e$ is the 12 × 12 local beam stiffness, $T$ the rotation to local axes, and $u_e$ the element's 12 nodal displacements. Any response that is a weighted sum of end forces, $R = w^{\mathsf T} q$, is then a linear function of all displacements:

$$
R = w^{\mathsf T} k_e T\, u_e = g^{\mathsf T} u, \qquad g = L_e^{\mathsf T}\, T^{\mathsf T} k_e\, w
$$

where $L_e$ picks the element's degrees of freedom out of $u$. With $u = K^{-1} f$ and $K$ symmetric,

$$
R = g^{\mathsf T} K^{-1} f = \left(K^{-1} g\right)^{\mathsf T} f = \psi^{\mathsf T} f, \qquad K\psi = g .
$$

So **one solve with the load vector $g$** gives $\psi$, and the response to *any* load $f$ is $\psi^{\mathsf T} f$. For a unit downward load at deck node $n$, $f = -e_{n,y}$, so $R = -\psi_{n,y}$: the influence surface is simply the **downward deflection of the deck** under the load $g$. This is Maxwell–Betti reciprocity; $g$ is the *adjoint load*.

<div class="anim" data-anim="adjoint"></div>

In the code, `adjoint_loads_for_girder_force` builds $g$ from the weighted columns of `beam_stiffness_matrix` (`setu/solver/stiffness.py`), rotated to global axes and applied at the element's two nodes (with the sign that turns end forces into internal forces).

## The surfaces Setu builds

| Response | Weights $w$ or load | Surface |
|---|---|---|
| Composite moment $M_c = M_z + N a$ | $w = e_{M_z} + a\, e_{N}$ at the element's i-end | deck deflection under $g$ |
| Shear $V$ | $w = e_{V_y}$ | deck deflection under $g$ |
| Deflection of a node | a unit downward load at that node | deck deflection (Maxwell's theorem directly) |
| Bearing reaction | a unit downward load on the bearing node | $k \times$ deck deflection, with $k$ = 10¹⁰ kN/m |

For each girder, Setu builds the moment surface at midspan and at 0.02L, 0.04L and 0.06L towards the first bearing (the largest live moment stands a little off midspan), the shear and the reaction at the first bearing, and the midspan deflection. That is **7 solves per girder**, whatever the size of the mesh.

## Reading a surface

The surface is known at the mesh nodes. Between them it is read by **bilinear interpolation** in the cell that contains the point. For a skewed deck, the point is first moved into mesh coordinates, $x_{\text{mesh}} = x - \text{skew}\cdot z$. Outside the deck the value is zero.

A vehicle's effect is the sum over its wheels:

$$
R = \sum_k P_k\, \eta(x_k, z_k),
$$

and an area load is $p \iint \eta \, dA$, integrated on sub-cells (2 per mesh interval along the span and 4 across each loaded strip, by default) and counted **only where $\eta$ has the adverse sign**, so a lane load or footway load is placed only where it makes things worse.

## Every other load case by reciprocity

The same $\psi$ reads any nodal load case, with all six components at every node:

$$
R = \sum_{\text{nodes}} \sum_{d=1}^{6} F_{n,d}\,\psi_{n,d}
$$

Setu stores all six displacement components of $\psi$ at every node, so braking, wind, seismic and custom load cases are read at every design place **without another solve per place** (`response_to_load_case`). Loads applied as element loads, like the girder self weight, cannot be read this way; the construction stages are therefore solved directly (see [Design values](design-values.md)).

## A guard

Before the first surface, Setu checks that the model moves under no load at all. If another load pattern were still active, its effect would be added into every surface; Setu stops with `ModelAlreadyLoadedError` instead.
