import math
from setu.irc6.irc_constants import VERTICAL_ALWAYS_IN_ZONES


class WindSite:
    # IRC:6-2017 cl. 209 as replaced by Amendment 10. Every input that changes the result is explicit:
    # basic wind speed Vb (Fig. 2 map, m/s); terrain category 1-4 (Table 2); superstructure_top_m, the average height of the top of
    # the superstructure above the mean retarding surface (209.3 (i)); road_level_m, the roadway above that surface (live load at
    # road_level_m + 3 m, 209.3 (v); deck-level speed for 209.5.2.4); pier_height_m (pier cap top to foundation top, Table 5 and 209.1);
    # return_period_years for k1 (Table 1); valley_or_leeward_hill for k3; cyclonic_region for k4; deck_cross_slope_deg for the
    # Table 8 note 7 camber increase; solid_barrier_height_m above the road (0 for an open parapet, Fig. 5).
    # A coefficient or area left as None is worked out as per IRC:6 (OsdagBridge's "As per IRC 6" mode).
    def __init__(self, basic_wind_speed_mps, terrain_category, superstructure_top_m, road_level_m, pier_height_m, return_period_years,
                 valley_or_leeward_hill, cyclonic_region, deck_cross_slope_deg, solid_barrier_height_m,
                 gust=None, drag=None, drag_on_live_load=None, lift=None,
                 exposed_area_m2=None, plan_area_m2=None, live_load_exposed_area_m2=None,
                 *, force_height_above_deck_m=None):
        for name, value in (("exposed_area_m2", exposed_area_m2), ("plan_area_m2", plan_area_m2),
                            ("live_load_exposed_area_m2", live_load_exposed_area_m2), ("drag", drag)):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative, or None for automatic")
        if force_height_above_deck_m is not None and not math.isfinite(force_height_above_deck_m):
            raise ValueError("force_height_above_deck_m must be finite or None for automatic")
        if terrain_category not in (1, 2, 3, 4):
            raise ValueError(f"terrain_category must be 1, 2, 3 or 4 (IRC:6 Table 2), got {terrain_category!r}")
        for name, value in (("superstructure_top_m", superstructure_top_m), ("road_level_m", road_level_m), ("pier_height_m", pier_height_m)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive, got {value}")
        self.basic_wind_speed_mps = basic_wind_speed_mps
        self.terrain_category = terrain_category
        self.superstructure_top_m = superstructure_top_m
        self.road_level_m = road_level_m
        self.pier_height_m = pier_height_m
        self.return_period_years = return_period_years
        self.valley_or_leeward_hill = valley_or_leeward_hill
        self.cyclonic_region = cyclonic_region
        self.deck_cross_slope_deg = deck_cross_slope_deg
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

    # clause 4.2.1 (b): in zones II and III vertical shaking is still taken for bearings; an explicit include_vertical wins everywhere
    def include_vertical_for_bearings(self):
        if self._include_vertical is not None:
            return self._include_vertical
        return True

class TemperatureSite:
    # IRC:6 clause 215 inputs: the site's highest and lowest shade air temperature, and whether it is snowbound (215.2)
    def __init__(self, shade_max_c, shade_min_c, snowbound=False):
        self.shade_max_c = shade_max_c
        self.shade_min_c = shade_min_c
        self.snowbound = snowbound

