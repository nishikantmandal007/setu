# Meshing

`setu/builder/mesh.py` decides where the stations are, along the span and across the deck. Two inputs control it: `panels_between_braces` and `target_size_across_width_m`.

<div class="anim" data-anim="mesh"></div>

## Across the deck

1. **Keep the lines that matter.** These are every strip edge (footpath, kerb, carriageway, median, barrier, railing), both deck edges, and every girder line. Girders are spaced evenly from `overhang_m` to `width − overhang_m`.
2. **Fill each gap.** Each gap of width $w$ between two kept lines is split into $n = \lceil w / s \rceil$ equal pieces, where $s$ is the target size. So no piece is wider than $s$, and the pieces in one gap are all equal.
3. Coordinates are rounded to 10⁻⁵ m so that equal positions compare equal.

Keeping strip edges means that a load on a strip (a footpath load, a kerb line load, surfacing on the carriageway) starts and stops exactly on mesh lines. Keeping girder lines means every girder has a row of deck nodes to be tied to. If a girder does not land on a station, Setu raises an error rather than tying it to the nearest node.

## Along the span

Brace stations are evenly spaced from 0 to L, both ends included (`station_count` of them). Each brace panel is split into `panels_between_braces` equal pieces. Braces therefore always sit on stations.

## Tributary lengths

Loads spread along the span use each station's tributary length: half the gap to each neighbour, and half a gap at the two ends (`tributary_length_m`). Across the deck, a pressure is integrated over each station's share, cut at strip edges, so a pressure that stops at a kerb stops there in the load too.

## How fine is fine enough

See [Accuracy and limits](../accuracy.md). In short: 16–25 panels between braces, and 0.10–0.15 m across the deck, for design.
