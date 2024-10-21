import geopandas as gpd


class FoodSupply:
    def __init__(self, cfg: dict):
        self.cfg = cfg["food_supply"]

    def get_import(self):
        pass

    def get_export(self):
        pass

    def calculate_food_supply(self, region: gpd.GeoDataFrame):
        pass
