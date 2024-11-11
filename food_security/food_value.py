import geopandas as gpd


class FoodValue:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def get_population(self, geometry: gpd.GeoDataFrame):
        pass

    def variety_standard(self):
        pass

    def nutritional_value_per_crop(self):
        pass

    def add_food_value(self, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass
