"""Module containing the FoodSupply class."""

import logging

import geopandas as gpd
import pandas as pd

from food_security.base import FSBase

logger = logging.getLogger(__name__)


class FoodSupply(FSBase):
    """Calculate the total food supply based on import and export and food production."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        self.region = region
        self.eximport_df = pd.read_csv(self.cfg["food_supply"]["export"]["path"])
        self.total_production_FAO = pd.read_csv(self.cfg["food_supply"]["total_production_FAO"]["path"])
        super().__init__(cfg=cfg)

    def get_import(self):
        pass

    def get_export(self):
        export_df = self.eximport_df.copy(deep=True)
        export_df = export_df[
            (export_df["Year"] == self.cfg["main"]["year"]) & (export_df["Element"] == "Export Quantity")
        ]
        food_types = list(self.cfg["food_production"]["lifestock"]["paths"].keys()) + list(
            self.cfg["food_production"]["other_crops"]["paths"].keys(),
        )
        for food_type in food_types:
            pass

    def get_road_density(self, geometry: gpd.GeoDataFrame):
        pass

    def get_GPD_per_capita(self, geometry: gpd.GeoDataFrame):
        pass

    def calculate_food_supply_for_region(self, geometry: gpd.GeoDataFrame) -> float:
        pass

    def calculate_food_transfer_coefficient(
        self,
        GPD_per_capita,
        road_density,
    ) -> float:
        pass

    def add_food_supply_per_province(
        self,
        provinces: gpd.GeoDataFrame,
        region: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        food_supply_region = self.calculate_food_supply_for_region(geometry=region)

    def _calculate_export_ratio(self, food_items):
        pass

    @property
    def total_production_FAO(self) -> pd.DataFrame:  # noqa: N802
        return self._total_production_FAO

    @total_production_FAO.setter
    def total_production_FAO(self, df: pd.DataFrame):  # noqa: N802
        return df[df["Area"] == self.cfg["main"]["country"]]
