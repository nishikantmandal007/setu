import multiprocessing
import struct

import numpy as np
import pytest
import xarray as xr

from setu import bridge_design_values
from test_brace_design_values import BRACE_BRIDGE
from test_seismic import SITE as SEISMIC_SITE
from test_wind import SITE as WIND_SITE


# retain dict order and every float's bits, including influence surfaces and datasets
def exact(value):
    if isinstance(value, np.ndarray):
        return value.dtype.str, value.shape, value.tobytes()
    if isinstance(value, np.generic):
        return value.dtype.str, value.tobytes()
    if isinstance(value, float):
        return struct.pack("!d", value)
    if isinstance(value, dict):
        return [(key, exact(item)) for key, item in value.items()]
    if isinstance(value, (tuple, list)):
        return [exact(item) for item in value]
    if isinstance(value, xr.Dataset):
        return exact(value.to_dict())
    if hasattr(value, "__dict__"):
        return type(value).__name__, exact(vars(value))
    return value


# different worker histories must produce the same surfaces, searches, sums and diagrams
def test_parallel_bridge_is_bit_identical():
    serial = bridge_design_values(BRACE_BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE, workers=1)
    parallel = bridge_design_values(BRACE_BRIDGE, wind=WIND_SITE, seismic=SEISMIC_SITE, workers=2)
    for part in ("girders", "braces", "diagrams"):
        assert exact(getattr(serial, part)) == exact(getattr(parallel, part)), part
    assert not multiprocessing.active_children()


# invalid explicit counts surface through the pool rather than silently choosing another count
@pytest.mark.parametrize("workers", [0, -1])
def test_invalid_worker_count(workers):
    with pytest.raises(ValueError):
        bridge_design_values(BRACE_BRIDGE, workers=workers)


# worker exceptions must reach the caller and the pool must close on that path too
def test_worker_exception_reaches_caller():
    from setu.postprocess.parallel import analysis_for, place_task
    from setu.utils.constants import MAX_MOMENT

    with pytest.raises(KeyError):
        with analysis_for(BRACE_BRIDGE, None, (), (), 2) as analysis:
            assert analysis.work is not None
            analysis.work.submit("place", place_task, -1, (MAX_MOMENT, 0)).result()
    assert not multiprocessing.active_children()
