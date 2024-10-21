import geopandas as gpd


class FoodProduction:
    def __init__(self, cfg: dict):
        self.cfg = cfg["food_production"]

    def get_lifestock(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def get_rice_yield(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def get_other_crops(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def get_aquaculture(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def add_foodproduction_values(self, region) -> gpd.GeoDataFrame:
        region = self.get_lifestock(region=region)
        region = self.get_rice_yield(region=region)
        region = self.get_other_crops(region=region)
        region = self.get_aquaculture(region=region)
        return region
