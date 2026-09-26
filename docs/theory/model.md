# The structural model

`setu/builder/assembly.py` builds a three-dimensional shell-and-beam model of the bridge in OpenSees (`-ndm 3 -ndf 6`).

## Coordinates

| Axis | Direction | Origin |
|---|---|---|
| x | along the span | the first bearing line |
| y | up | the mid-plane of the slab |
| z | across the deck | the left edge of the deck |

For a skewed deck, every node at width position z is shifted along the span by `skew × z`, where `skew` is the tan of the skew angle. The mesh stays regular in the skewed coordinates: an **oblique** mesh.

## Elements

| Part | OpenSees element | Where it sits |
|---|---|---|
| Deck slab | `ShellMITC4` with an `ElasticMembranePlateSection` (E, ν, thickness) | one shell per mesh cell, nodes at y = 0 (slab mid-plane) |
| Girders | `elasticBeamColumn` with the plate girder's A, E, G, J, I<sub>y</sub>, I<sub>z</sub> | one element per span station interval, nodes at the **steel centroid** |
| Slab–girder tie | `rigidLink beam` | from every girder node up to the deck node above it |
| Bracing | `corotTruss` (area from the input) | between nodes at the top and bottom of neighbouring girders, at each brace station, in the X, XT, XB, XTB, K or KT pattern |
| Brace to girder | `rigidLink beam` | from the girder node to its top and bottom brace nodes |
| Bearings | `zeroLength` vertical spring, k = 10¹⁰ kN/m, to a fixed ground node | under each girder end |

The girder node level below the slab mid-plane is

$$
y_g = -\left(d - \bar y_b + \tfrac{t_s}{2}\right)
$$

where $d$ is the girder depth, $\bar y_b$ the steel neutral axis height above the bottom flange, and $t_s$ the slab thickness. The distance $a = -y_g$ is the **composite lever arm** used for the composite moment.

## Composite moment

A girder in a composite deck carries its bending partly as its own moment $M_z$ and partly as an axial couple with the slab. Setu reads the girder's share of the composite moment as

$$
M_c = M_z + N\,a
$$

where $N$ is the girder's axial force and $a$ the lever arm above. This is the moment the design is checked for, and the one the influence surfaces are built for.

## Bearings and supports

Each bearing is a very stiff vertical spring (10¹⁰ kN/m). It is rigid for design purposes, and it makes the **reaction an element force**, so the reaction has an exact influence surface too.

| Node | Restrained | Free |
|---|---|---|
| girder end at x = 0 | x and z translation | rotations |
| girder end at x = L | z translation | x translation, rotations |
| K-brace meeting points | x, rotations about x, y, z | move with the deck vertically and across |

The vertical degree of freedom at each bearing is carried by the spring.

!!! warning "Known limit"
    Every girder is held along the span at x = 0. The girders then push against each other through the deck at the fixed end. This relieves the edge girder by a few percent (see [Accuracy and limits](../accuracy.md)). Holding a single girder is the planned change.

## Section properties

`setu/models/sections.py` computes, from the plate dimensions: area, neutral axis height, strong- and weak-axis second moments, and the torsion constant of the open section, $J = \sum b t^3/3$ over the three plates. Shear deformation is not modelled (Euler–Bernoulli beams).

## Short term, long term, bare steel

The same geometry is built three ways:

| Model | Deck shells | Used for |
|---|---|---|
| Bare steel (`composite=False`) | none | stage 1 (steel self weight) and stage 2 (wet slab) |
| Composite, long term | E<sub>s</sub> / m with m = E<sub>s</sub> / (0.5 E<sub>cm</sub>) ≥ 15 | stage 3 (SIDL) and stage 4 (surfacing) |
| Composite, short term | E<sub>s</sub> / m with m = E<sub>s</sub> / E<sub>cm</sub> ≥ 7.5 | traffic, influence surfaces, wind, seismic, braking |

The modular ratio follows IRC:22 cl. 604.3 (`Concrete.modulus_for`).

## Node and element numbering

Deck nodes start at 1000 and run across the width first (`1000 + i × stations_across + j`). Girder, brace and K-brace nodes follow in blocks; deck shells start at 1000, then girder beams, then braces. The numbering is deterministic, so the same bridge always gives the same tags.
