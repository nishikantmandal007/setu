"""The longitudinal search must find the worst legal train, and only legal trains."""


import numpy as np
import pytest

from src.services.vehicle_placement import find_worst_train, place_train
import oracles
from oracles import worst_train_by_enumeration

ADVERSE = ("maximum", "minimum")


def uneven_positions_and_responses(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Unevenly spaced positions - where a search done by index goes wrong."""
    rng = np.random.default_rng(seed)
    positions_m = np.unique(np.round(np.sort(rng.uniform(0, 40, 18)), 6))
    return positions_m, rng.normal(0, 5, len(positions_m))


@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("adverse", ADVERSE)
@pytest.mark.parametrize("vehicles_in_train", [1, 2, 3])
def test_matches_full_enumeration(seed, adverse, vehicles_in_train):
    positions_m, responses = uneven_positions_and_responses(seed)
    pitch_m = 7.5

    found = place_train(responses, positions_m, pitch_m, vehicles_in_train, adverse)
    expected = worst_train_by_enumeration(
        responses, positions_m, pitch_m, vehicles_in_train, adverse
    )

    if expected is None:
        assert found is None
    else:
        assert found is not None
        assert found.response == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("adverse", ADVERSE)
def test_never_returns_an_illegal_train(seed, adverse):
    """Every gap must be at least the pitch the code requires.

    Resolving this on grid indices instead of real positions once returned a
    1.18 m gap where 1.20 m was needed.
    """
    positions_m, responses = uneven_positions_and_responses(seed)
    pitch_m = 7.5

    found = place_train(responses, positions_m, pitch_m, 3, adverse)
    if found is None:
        return

    gaps_m = np.diff(found.positions_m)
    assert (gaps_m >= pitch_m - 1e-9).all()


@pytest.mark.parametrize("adverse", ADVERSE)
def test_a_longer_train_is_never_forced(adverse):
    """A shorter train may govern, so every length has to be tried.

    Here the deck helps rather than hurts beyond 20 m, so anywhere a second
    vehicle could legally stand it would relieve the response - and it must
    therefore be left off.
    """
    positions_m = np.linspace(0.0, 40.0, 41)
    hurts, helps = (-10.0, +10.0) if adverse == "minimum" else (+10.0, -10.0)
    responses = np.where(positions_m < 20.0, hurts, helps)

    found = find_worst_train(
        responses, positions_m, pitch_m=20.0, most_vehicles=2, adverse=adverse
    )

    assert found is not None
    assert found.vehicles_in_train() == 1
    assert found.response == pytest.approx(hurts)


def test_a_train_helps_when_both_vehicles_hurt():
    """Two vehicles that both make it worse must both be used."""
    positions_m = np.linspace(0.0, 40.0, 41)
    responses = -np.ones_like(positions_m) * 10.0

    one = place_train(responses, positions_m, 20.0, 1, "minimum")
    two = place_train(responses, positions_m, 20.0, 2, "minimum")

    assert two.response == pytest.approx(2 * one.response)
    assert two.vehicles_in_train() == 2


def test_rejects_an_unknown_adverse_direction():
    with pytest.raises(ValueError, match="maximum"):
        place_train(np.zeros(5), np.arange(5.0), 1.0, 1, adverse="worst")
