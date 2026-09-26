# Dead load in stages

A composite bridge is not born composite. While the concrete is wet it is only a weight; the steel girders carry it alone. Only after it hardens does the slab start working *with* the steel.

Setu follows the **un-propped** method of IRC:22 (no temporary supports under the girders while the slab is cast), which is how OsdagBridge designs.

<div class="anim" data-anim="stages"></div>

## The stages

| Stage | What is added | Section that carries it | Factored as |
|---|---|---|---|
| 1 · Steel self weight | girders and bracing | bare steel | dead (× 1.35) |
| 2 · Wet slab | the concrete deck | bare steel | dead (× 1.35) |
| 3 · Superimposed dead load | kerbs, median, crash barriers, railings, footpath | composite, long term | dead (× 1.35) |
| 4 · Surfacing | wearing course | composite, long term | surfacing (× 1.75) |
| Traffic | vehicles, lane load, footway | composite, short term | live |

Surfacing is kept apart from the rest because IRC:6 Table B.2 factors it more heavily (it can be re-laid thicker later).

## Long term and short term

Concrete under a load that stays for years slowly creeps, so it behaves as if it were softer. IRC:22 cl. 604.3 allows for this through the **modular ratio** $m$ (how many times stiffer steel is than concrete):

- **long term** (stages 3 and 4): $m = E_s / (0.5\,E_{cm})$, at least 15;
- **short term** (traffic): $m = E_s / E_{cm}$, at least 7.5.

A lower $m$ means the slab helps more. That is why traffic sees a stiffer bridge than the kerbs do.

## How the loads are applied

- **Footpath** load is an area load (kN/m²) over the footpath strip.
- **Kerb, median, crash barrier and railing** loads are line loads (kN/m) along the middle of their strip.
- **Surfacing** is its thickness × unit weight, over the carriageway.

If a load is given for a strip the deck does not have (for example a median load on a deck with no median), Setu stops and says so rather than dropping it silently.
