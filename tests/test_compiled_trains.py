"""The compiled train placement (Numba, when installed) must give the very bits the NumPy one gives: train lengths, responses and
chosen positions, on random responses with deliberate ties, trains of one to six vehicles, both directions."""

import numpy as np
import pytest

pytest.importorskip("numba")

import setu.analysis.along_span as along_span


@pytest.mark.parametrize("seed", range(60))
@pytest.mark.parametrize("adverse", ["maximum", "minimum"])
def test_compiled_equals_numpy(seed, adverse, monkeypatch):
    rng = np.random.default_rng(seed)
    along, across = int(rng.integers(2, 250)), int(rng.integers(1, 30))
    positions_m = np.unique(np.round(np.sort(rng.uniform(0.0, 60.0, along)), 3))
    shape = (len(positions_m), across)
    response = rng.integers(-4, 5, shape).astype(float) if seed % 2 else rng.normal(size=shape)
    pitch_m, most = float(rng.uniform(1.0, 25.0)), int(rng.integers(1, 7))

    monkeypatch.setattr(along_span, "USE_COMPILED", False)
    expected = along_span.worst_trains_as_arrays(response, positions_m, pitch_m, most, adverse)
    monkeypatch.setattr(along_span, "USE_COMPILED", True)
    got = along_span.worst_trains_as_arrays(response, positions_m, pitch_m, most, adverse)

    lengths = expected[0]
    assert np.array_equal(got[0], lengths)
    assert np.array_equal(got[1], expected[1])
    for row in range(len(lengths)):
        assert np.array_equal(got[2][row, :lengths[row]], expected[2][row, :lengths[row]])
