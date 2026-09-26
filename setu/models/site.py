from setu.irc6.irc_constants import VERTICAL_ALWAYS_IN_ZONES


class WindSite:
    # IRC:6 clause 209 wind inputs; a coefficient or area left as None is worked out as per IRC:6 (OsdagBridge's "As per IRC 6" mode)
    def __init__(self, basic_wind_speed_mps, terrain, height_m, funnelling, solid_barrier_height_m,
                 gust=None, drag=None, drag_on_live_load=None, lift=None,
                 exposed_area_m2=None, plan_area_m2=None, live_load_exposed_area_m2=None):
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

class SeismicSite:
    # IRC:SP:114 inputs as OsdagBridge gives them: zone, soil, I, T and R
    def __init__(self, zone, soil, importance_factor, period_s, response_reduction):
        self.zone = zone
        self.soil = soil
        self.importance_factor = importance_factor
        self.period_s = period_s
        self.response_reduction = response_reduction

    # clause 4.2.1: vertical shaking is always taken in zones IV and V
    @property
    def include_vertical(self):
        return self.zone in VERTICAL_ALWAYS_IN_ZONES

class TemperatureSite:
    # IRC:6 clause 215 inputs: the site's highest and lowest shade air temperature
    def __init__(self, shade_max_c, shade_min_c):
        self.shade_max_c = shade_max_c
        self.shade_min_c = shade_min_c

