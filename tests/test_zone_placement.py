"""The 70R zone placement reads every offset at once (a range-maximum over the curve's kinks) and must pick exactly what the
per-offset search picks: the same candidates (zone ends, an even spread, the kinks inside), the worst value, the smallest position
on a tie."""

import numpy as np
import pytest

from setu.analysis.across_carriageway import worst_spot_inside_the_zone
from setu.analysis.along_span import positions_inside_zone, read_curve
from setu.helpers import DEFAULT_SAMPLING, index_of_worst
from setu.utils.constants import BIGGER_IS_WORSE, ROUND_TO_DECIMALS, SMALLER_IS_WORSE


class Search:
    def __init__(self, adverse, kinks_m):
        self.adverse, self.curve_breakpoints_m, self.sampling = adverse, kinks_m, DEFAULT_SAMPLING


# the search as it was, one offset at a time
def one_offset_at_a_time(block, packed_left_m, nearest_m, furthest_m, offsets_m, curves, search):
    zone_from_m = packed_left_m + offsets_m + nearest_m
    zone_to_m = packed_left_m + offsets_m + furthest_m
    values, centres_m = np.empty(len(offsets_m)), np.empty(len(offsets_m))
    for i, (from_m, to_m) in enumerate(zip(zone_from_m, zone_to_m, strict=True)):
        inside_m = positions_inside_zone(from_m, to_m, search.curve_breakpoints_m, search.sampling)
        responses = read_curve(curves[block], inside_m)
        worst = int(index_of_worst(responses, search.adverse))
        values[i], centres_m[i] = responses[worst], inside_m[worst]
    return values, centres_m


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("adverse", [BIGGER_IS_WORSE, SMALLER_IS_WORSE])
def test_same_spot_as_one_offset_at_a_time(seed, adverse):
    rng = np.random.default_rng(seed)
    width_m = rng.uniform(4.0, 25.0)
    kinks_m = np.unique(np.round(np.sort(rng.uniform(0.0, width_m, rng.integers(0, 60))), ROUND_TO_DECIMALS))
    levels = rng.choice([-2.0, -1.0, 0.0, 1.0, 3.0], len(kinks_m)) if seed % 3 == 0 else rng.normal(size=len(kinks_m))  # ties on purpose
    ends = (np.array([0.0, width_m]), np.array([0.0, 0.0]))
    xs, ys = np.concatenate([kinks_m, ends[0]]), np.concatenate([levels, ends[1]])
    order = np.argsort(xs, kind="stable")
    xs, ys = xs[order], ys[order]
    curves = {"zone": lambda z, xs=xs, ys=ys: np.interp(z, xs, ys)}
    zone_m = rng.uniform(0.5, 3.0)
    offsets_m = np.unique(np.round(rng.uniform(0.0, max(width_m - zone_m - 1.0, 0.1), rng.integers(1, 120)), ROUND_TO_DECIMALS))
    args = ("zone", rng.uniform(0.0, 0.5), 0.0, zone_m, offsets_m, curves, Search(adverse, kinks_m))

    new_values, new_centres = worst_spot_inside_the_zone(*args)
    old_values, old_centres = one_offset_at_a_time(*args)

    assert np.array_equal(new_values, old_values)
    assert np.array_equal(new_centres, old_centres)
