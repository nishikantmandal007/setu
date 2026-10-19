"""The longitudinal search must find the worst legal train, and only legal trains."""


import numpy as np
import pytest

from setu.analysis.along_span import find_worst_train, place_train
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

    assert one is not None and two is not None
    assert two.response == pytest.approx(2 * one.response)
    assert two.vehicles_in_train() == 2


def test_rejects_an_unknown_adverse_direction():
    with pytest.raises(ValueError, match="maximum"):
        place_train(np.zeros(5), np.arange(5.0), 1.0, 1, adverse="worst")


def test_a_train_follower_exactly_at_minimum_spacing_is_found():
    """On a long, coarsely meshed span the worst train can have a vehicle that sits on no mesh
    breakpoint of its own: it is exactly one pitch behind a vehicle that does. A search that only
    tries each vehicle's own breakpoints misses it. Checked against a 1 cm brute force.
    """
    from setu.analysis.along_span import VehicleResponses, sum_over_wheels
    from setu.analysis.influence_surface import InfluenceSurface
    from setu.irc6.vehicles import CLASS_A, most_vehicles_that_fit, pitch_between_vehicles_m
    from setu.helpers import DEFAULT_SAMPLING
    from setu.irc6.impact import impact_factor
    from setu.irc6.wheel_loads import wheel_load_offsets

    span_m = 90.0
    length_mesh_m = np.linspace(0.0, span_m, 13)
    width_mesh_m = np.linspace(0.0, 10.0, 5)
    peak_at_m = 0.37 * span_m
    along = np.where(length_mesh_m <= peak_at_m, length_mesh_m / peak_at_m, (span_m - length_mesh_m) / (span_m - peak_at_m))
    surface = InfluenceSurface(values=along[:, None] * np.ones(len(width_mesh_m))[None, :], length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m, name="peak", skew=0.0)
    z_m = 5.0

    found = VehicleResponses(surface, span_m, 0.0, 0.0, DEFAULT_SAMPLING).for_vehicle(CLASS_A, [z_m], "maximum").response[0] / impact_factor("Class_A", span_m)

    offsets = wheel_load_offsets(CLASS_A, 0.0, DEFAULT_SAMPLING)
    step_m = 0.01
    x_m = np.round(np.arange(-offsets[:, 0].max(), span_m + step_m, step_m), 6)
    one_vehicle = sum_over_wheels(surface, offsets, x_m, [z_m])[:, 0]
    pitch_steps = int(round(pitch_between_vehicles_m(CLASS_A) / step_m))
    best = one_vehicle.copy()
    worst_train = best.max()
    for _ in range(1, most_vehicles_that_fit(CLASS_A, float(x_m[0]), float(x_m[-1]))):
        best_behind = np.maximum.accumulate(best)
        best = np.full_like(best, -np.inf)
        best[pitch_steps:] = one_vehicle[pitch_steps:] + best_behind[:-pitch_steps]
        worst_train = max(worst_train, best.max())

    assert found == pytest.approx(worst_train, rel=1e-9)


# batched growing trains keep the scalar DP's exact responses, ties and positions
@pytest.mark.parametrize("adverse", ADVERSE)
@pytest.mark.parametrize("seed", range(12))
def test_batched_trains_are_bit_identical_to_separate_lengths(seed, adverse):
    from setu.analysis.along_span import find_worst_trains
    from setu.helpers import is_worse

    rng = np.random.default_rng(seed)
    positions = np.cumsum(rng.choice([0.25, 0.5, 1.0, 2.0], 24))
    responses = rng.normal(size=(24, 7))
    responses[:, 1] = rng.integers(-2, 3, 24)
    responses[:, 2] = 0.0
    responses[:, 3] = -0.0
    responses[:, 4] = -np.inf if adverse == "maximum" else np.inf
    responses[:, 5] = responses[:, 4]
    responses[0, 5] = 1.0
    responses[:, 6] = rng.choice([1e16, 1., -1e16, -1.], 24)
    found = find_worst_trains(responses, positions, 4.0, 10, adverse)
    for column, actual in enumerate(found):
        expected = None
        for length in range(1, 11):
            candidate = place_train(responses[:, column], positions, 4.0, length, adverse)
            if candidate is None:
                break
            if expected is None or is_worse(candidate.response, expected.response, adverse):
                expected = candidate
        if expected is None:
            assert actual is None
        else:
            assert actual.positions_m == expected.positions_m
            assert np.float64(actual.response).tobytes() == np.float64(expected.response).tobytes()


# a column that cannot fit even one vehicle keeps the existing public exception
def test_batched_trains_refuse_an_impossible_first_vehicle():
    from setu.analysis.along_span import VehicleResponses
    from setu.irc6.vehicles import CLASS_A

    responses = np.full((3, 2), -np.inf)
    with pytest.raises(RuntimeError, match="even a single vehicle"):
        VehicleResponses.worst_train_at_each_position(object.__new__(VehicleResponses), CLASS_A, responses, np.array([0., 10., 20.]), "maximum")


# strict ties retain the first position and the shorter train
def test_batched_train_ties_keep_the_first_shortest_placement():
    from setu.analysis.along_span import find_worst_trains

    found = find_worst_trains(np.zeros((5, 2)), np.arange(5.), 1., 5, "maximum")
    assert [placement.positions_m for placement in found] == [(0.,), (0.,)]
    two = place_train(np.ones(5), np.arange(5.), 1., 2, "maximum")
    assert two is not None and two.positions_m == (0., 1.)
