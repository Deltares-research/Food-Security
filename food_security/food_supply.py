"""Module containing the FoodSupply class."""
import geopandas as gpd

from food_security.base import FSBase


class FoodSupply(FSBase):
    def __init__(self, cfg: dict):
        super().__init__(cfg=cfg)

    def get_import(self):
        pass

    def get_export(self):
        pass

    def get_road_density(self, geometry: gpd.GeoDataFrame):
        pass

    def get_GPD_per_capita(self, geometry: gpd.GeoDataFrame):
        pass

    def calculate_food_supply_for_region(self, geometry: gpd.GeoDataFrame) -> float:
        pass

    def calculate_food_transfer_coefficient(
        self, GPD_per_capita, road_density,
    ) -> float:
        pass

    def add_food_supply_per_province(
        self, provinces: gpd.GeoDataFrame, region: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        food_supply_region = self.calculate_food_supply_for_region(geometry=region)
