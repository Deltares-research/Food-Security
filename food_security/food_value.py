"""Module containing the FoodValue class."""
import geopandas as gpd

from food_security.base import FSBase


class FoodValue(FSBase):
    def __init__(self, cfg: dict) -> None:
        super().__init__(cfg=cfg)

    def get_population(self, geometry: gpd.GeoDataFrame):
        pass

    def variety_standard(self):
        pass

    def nutritional_value_per_crop(self):
        pass

    def add_food_value(self, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass
