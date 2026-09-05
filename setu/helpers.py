import logging
import numpy as np

BIGGER_IS_WORSE = "maximum"
SMALLER_IS_WORSE = "minimum"

def adverse_sign(adverse):
    if adverse == BIGGER_IS_WORSE:
        return 1.0
    if adverse == SMALLER_IS_WORSE:
        return -1.0
    raise ValueError(f"adverse must be 'maximum' or 'minimum', got {adverse!r}")

def is_worse(candidate, best, adverse):
    if adverse == BIGGER_IS_WORSE:
        return candidate > best
    return candidate < best

def index_of_worst(values, adverse, axis=None):
    if adverse == BIGGER_IS_WORSE:
        return np.asarray(np.argmax(values, axis=axis))
    return np.asarray(np.argmin(values, axis=axis))

def is_worst_first(adverse):
    return adverse == BIGGER_IS_WORSE

def where_a_load_hurts(ordinates, adverse):
    return np.asarray(ordinates) * adverse_sign(adverse) > 0.0

class SamplingSettings:
    def __init__(self, sliding_offsets_to_try=41, positions_inside_a_70r_zone_to_try=41,
                 positions_across_the_deck_to_try=241, span_positions_evaluated_at_once=192,
                 point_loads_along_a_track=4, point_loads_across_a_track=2,
                 udl_cells_per_mesh_interval_along_span=2,
                 udl_cells_per_mesh_interval_across_width=4):
        self.sliding_offsets_to_try = sliding_offsets_to_try
        self.positions_inside_a_70r_zone_to_try = positions_inside_a_70r_zone_to_try
        self.positions_across_the_deck_to_try = positions_across_the_deck_to_try
        self.span_positions_evaluated_at_once = span_positions_evaluated_at_once
        self.point_loads_along_a_track = point_loads_along_a_track
        self.point_loads_across_a_track = point_loads_across_a_track
        self.udl_cells_per_mesh_interval_along_span = udl_cells_per_mesh_interval_along_span
        self.udl_cells_per_mesh_interval_across_width = udl_cells_per_mesh_interval_across_width

DEFAULT_SAMPLING = SamplingSettings()

log = logging.getLogger("setu")
log.addHandler(logging.NullHandler())

def enable_reports(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.handlers = [handler]
    log.setLevel(level)

def report(title, rows):
    rule = "-" * 40
    label_width = max((len(label) for label in rows), default=0)
    log.info("")
    log.info(rule)
    log.info(title)
    log.info(rule)
    for label, value in rows.items():
        log.info(f"{label:<{label_width}} = {value}")
    log.info(rule)
