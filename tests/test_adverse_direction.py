# Every function in adverse_direction has exactly two legal inputs - check both,
# plus the ValueError a third one must raise.


import numpy as np
import pytest

from src.utils.helpers import (
    adverse_sign,
    index_of_worst,
    is_worse,
    is_worst_first,
    where_a_load_hurts,
)


def test_adverse_sign_is_positive_for_maximum():
    assert adverse_sign("maximum") == 1.0


def test_adverse_sign_is_negative_for_minimum():
    assert adverse_sign("minimum") == -1.0


def test_adverse_sign_rejects_anything_else():
    with pytest.raises(ValueError, match="adverse must be 'maximum' or 'minimum', got 'worst'"):
        adverse_sign("worst")


def test_is_worse_for_maximum_wants_bigger():
    assert is_worse(5.0, 3.0, "maximum") is True
    assert is_worse(1.0, 3.0, "maximum") is False


def test_is_worse_for_minimum_wants_smaller():
    assert is_worse(1.0, 3.0, "minimum") is True
    assert is_worse(5.0, 3.0, "minimum") is False


def test_index_of_worst_picks_the_largest_for_maximum():
    values = np.array([1.0, -5.0, 4.0, 2.0])
    assert index_of_worst(values, "maximum") == 2


def test_index_of_worst_picks_the_smallest_for_minimum():
    values = np.array([1.0, -5.0, 4.0, 2.0])
    assert index_of_worst(values, "minimum") == 1


def test_index_of_worst_takes_an_axis():
    values = np.array([[1.0, -5.0], [4.0, 2.0]])
    assert list(index_of_worst(values, "maximum", axis=0)) == [1, 1]
    assert list(index_of_worst(values, "minimum", axis=0)) == [0, 0]


def test_is_worst_first_for_maximum():
    assert is_worst_first("maximum") is True


def test_is_worst_first_for_minimum():
    assert is_worst_first("minimum") is False


def test_where_a_load_hurts_for_maximum_is_the_positive_ordinates():
    ordinates = np.array([-2.0, 0.0, 3.0])
    assert list(where_a_load_hurts(ordinates, "maximum")) == [False, False, True]


def test_where_a_load_hurts_for_minimum_is_the_negative_ordinates():
    ordinates = np.array([-2.0, 0.0, 3.0])
    assert list(where_a_load_hurts(ordinates, "minimum")) == [True, False, False]
