"""The transverse search must find the worst arrangement, keeping every clearance."""

from __future__ import annotations

import numpy as np
import pytest

from setu import Carriageway
from setu.irc_code_rules.lane_arrangements import CLASS_A_LANE, ZONE_70R
from setu.vehicle_placement.across_carriageway import find_worst_placement
from setu.vehicle_placement.sliding_blocks import place_vehicles
from tests.oracles import worst_chain_by_enumeration

ADVERSE = ("maximum", "minimum")


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize("adverse", ADVERSE)
@pytest.mark.parametrize("blocks", [1, 2, 3, 4])
def test_matches_full_enumeration(seed, adverse, blocks):
    rng = np.random.default_rng(seed)
    curves = [rng.normal(0, 5, 11) for _ in range(blocks)]

    found, _ = place_vehicles(curves, adverse)

    assert found == pytest.approx(worst_chain_by_enumeration(curves, adverse), abs=1e-9)


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize("adverse", ADVERSE)
def test_the_blocks_never_overtake_each_other(seed, adverse):
    """Sliding offsets must never decrease left to right.

    That single rule is what stands in for every clearance in Table 3, so a
    decreasing chain means two vehicles have been placed illegally close.
    """
    rng = np.random.default_rng(seed)
    curves = [rng.normal(0, 5, 15) for _ in range(4)]

    _, chosen = place_vehicles(curves, adverse)

    assert all(right >= left for left, right in zip(chosen, chosen[1:], strict=False))


def test_worst_case_is_ranked_first():
    carriageway = [Carriageway(0.0, 9.0)]
    curves = [
        {
            CLASS_A_LANE: lambda z: -np.abs(np.asarray(z) - 4.5),
            ZONE_70R: lambda z: -2.0 * np.abs(np.asarray(z) - 4.5),
        }
    ]

    ranked = find_worst_placement(carriageway, curves, adverse="minimum")

    assert ranked[0].response == min(placement.response for placement in ranked)


def test_complains_when_curves_and_carriageways_disagree():
    """A narrow carriageway carries its own UDL, so each one needs its own curves."""
    carriageways = [Carriageway(0.0, 9.0), Carriageway(10.0, 19.0)]
    one_set = [{CLASS_A_LANE: lambda z: np.zeros_like(z), ZONE_70R: lambda z: np.zeros_like(z)}]

    with pytest.raises(ValueError, match="own residual UDL"):
        find_worst_placement(carriageways, one_set)
