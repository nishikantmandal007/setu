from setu.utils.constants import PLAIN_TERRAIN


class WindSite:
    def __init__(self, basic_wind_speed_mps=33.0, terrain=PLAIN_TERRAIN, height_m=10.0, funnelling=False, construction=False,
                 solid_barrier_height_m=0.0, gust=None, drag=None, drag_on_live_load=None, lift=None,
                 exposed_area_m2=None, plan_area_m2=None, live_load_exposed_area_m2=None, **kwargs):
        self.basic_wind_speed_mps = basic_wind_speed_mps
        self.terrain = terrain
        self.height_m = height_m
        self.funnelling = funnelling
        self.construction = construction
        self.solid_barrier_height_m = solid_barrier_height_m
        self.gust = gust
        self.drag = drag
        self.drag_on_live_load = drag_on_live_load
        self.lift = lift
        self.exposed_area_m2 = exposed_area_m2
        self.plan_area_m2 = plan_area_m2
        self.live_load_exposed_area_m2 = live_load_exposed_area_m2

    def to_dict(self):
        return self.__dict__
