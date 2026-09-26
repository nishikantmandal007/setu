---
hide:
  - navigation
  - toc
---

# Setu { .hide-title }

<div class="hero" markdown>
![Setu](assets/logo.svg){ .only-light }
![Setu](assets/logo-dark.svg){ .only-dark }

Find the worst legal traffic on a bridge deck,<br>and the IRC design forces for every girder.

[Get started](getting-started.md){ .md-button .md-button--primary }
[How it works](how-it-works/index.md){ .md-button }
[Theory](theory/index.md){ .md-button }
</div>

**Setu** (Sanskrit for *bridge*) analyses simply supported steel–concrete composite plate girder bridges to **IRC:6-2017**, **IRC:22-2015** and **IRC:SP:114-2018**. It is the analysis engine behind [OsdagBridge](https://github.com/osdag-admin/OsdagBridge).

<div class="anim" data-anim="replay"></div>

!!! info "Every girder, every design place"
    Pick any girder and result in the animation. Setu runs this search for **every girder**, at every place it designs: the moment at midspan and at 0.02L, 0.04L and 0.06L towards the bearing (the largest live moment stands a little off midspan), the shear and the reaction at the bearing, and the midspan deflection. That is seven influence surfaces and seven searches per girder.

<div class="grid cards" markdown>

-   **One solve per result**

    ---

    Influence surfaces by the adjoint method: one solve gives the effect of a load anywhere on the deck. Seven solves per girder, however fine the mesh.

    [:octicons-arrow-right-24: Influence surfaces](how-it-works/influence-surfaces.md)

-   **Exact search, no step size**

    ---

    The worst position is always where a wheel crosses a mesh station, so Setu checks exactly those. Trains and lanes are placed by dynamic programming.

    [:octicons-arrow-right-24: Search along the span](theory/along-span.md)

-   **The code, clause by clause**

    ---

    Class A and 70R vehicles, lanes, impact, footway, braking, fatigue, wind, seismic, temperature and Annex B combinations, each value checked against the printed page.

    [:octicons-arrow-right-24: Codes followed](codes.md)

-   **Built the way it is built**

    ---

    Dead load in un-propped construction stages: bare steel, wet slab, then the composite deck, with long- and short-term modular ratios.

    [:octicons-arrow-right-24: Dead load in stages](how-it-works/dead-load.md)

-   **Checks itself**

    ---

    Every critical position is re-solved as ordinary loads; the dynamic programs race brute-force oracles; known answers are pinned.

    [:octicons-arrow-right-24: Verification](theory/verification.md)

-   **Python or browser**

    ---

    A plain Python API, and a local web app with animations, plots and a CSV export of the critical position's loads.

    [:octicons-arrow-right-24: Web app](guide/web-app.md)

</div>

## In five lines

```python
from setu import girder_design_values
from setu.utils.constants import BASIC, BIGGER_IS_WORSE, MAX_MOMENT

results = girder_design_values(bridge)          # bridge = BridgeInput(...)
for girder, by_response in results.girders.items():
    print(girder, by_response[MAX_MOMENT][BASIC][BIGGER_IS_WORSE].value)
```

See [Getting started](getting-started.md) for the full example.
