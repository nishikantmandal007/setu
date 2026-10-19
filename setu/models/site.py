import math
from setu.irc6.irc_constants import VERTICAL_ALWAYS_IN_ZONES


class WindSite:
    # IRC:6 clause 209 wind inputs; a coefficient or area left as None is worked out as per IRC:6 (OsdagBridge's "As per IRC 6" mode)
    def __init__(self, basic_wind_speed_mps, terrain, height_m, funnelling, solid_barrier_height_m,
                 gust=None, drag=None, drag_on_live_load=None, lift=None,
                 exposed_area_m2=None, plan_area_m2=None, live_load_exposed_area_m2=None,
                 *, force_height_above_deck_m=None):
        for name, value in (("exposed_area_m2", exposed_area_m2), ("plan_area_m2", plan_area_m2),
                            ("live_load_exposed_area_m2", live_load_exposed_area_m2), ("drag", drag)):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative, or None for automatic")
        if force_height_above_deck_m is not None and not math.isfinite(force_height_above_deck_m):
            raise ValueError("force_height_above_deck_m must be finite or None for automatic")
        self.basic_wind_speed_mps = basic_wind_speed_mps
        self.terrain = terrain
        self.height_m = height_m
        self.funnelling = funnelling
        self.solid_barrier_height_m = solid_barrier_height_m
        self.gust = gust
        self.drag = drag
        self.drag_on_live_load = drag_on_live_load
        self.lift = lift
        self.exposed_area_m2 = exposed_area_m2
        self.plan_area_m2 = plan_area_m2
        self.live_load_exposed_area_m2 = live_load_exposed_area_m2
        self.force_height_above_deck_m = force_height_above_deck_m

class SeismicSite:
    # IRC:SP:114 inputs as OsdagBridge gives them: zone, soil, I, T and R
    def __init__(self, zone, soil, importance_factor, period_s, response_reduction, *,
                 horizontal_coefficient=None, vertical_coefficient=None, dead_weight_kn=None, live_weight_kn=None,
                 include_vertical=None):
        for name, value in (("horizontal_coefficient", horizontal_coefficient), ("vertical_coefficient", vertical_coefficient),
                            ("dead_weight_kn", dead_weight_kn), ("live_weight_kn", live_weight_kn)):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative, or None for automatic")
        if include_vertical is not None and not isinstance(include_vertical, bool):
            raise ValueError("include_vertical must be True, False or None for automatic")
        if not math.isfinite(response_reduction) or response_reduction <= 0:
            raise ValueError("response_reduction must be finite and positive")
        self.zone = zone
        self.soil = soil
        self.importance_factor = importance_factor
        self.period_s = period_s
        self.response_reduction = response_reduction
        self.horizontal_coefficient = horizontal_coefficient
        self.vertical_coefficient = vertical_coefficient
        self.dead_weight_kn = dead_weight_kn
        self.live_weight_kn = live_weight_kn
        self._include_vertical = include_vertical

    # clause 4.2.1: vertical shaking is always taken in zones IV and V
    @property
    def include_vertical(self):
        if self._include_vertical is not None:
            return self._include_vertical
        return self.vertical_coefficient is not None or self.zone in VERTICAL_ALWAYS_IN_ZONES

class TemperatureSite:
    # IRC:6 clause 215 inputs: the site's highest and lowest shade air temperature
    def __init__(self, shade_max_c, shade_min_c):
        self.shade_max_c = shade_max_c
        self.shade_min_c = shade_min_c

