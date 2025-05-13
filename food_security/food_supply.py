"""Module containing the FoodSupply class."""

import logging

import geopandas as gpd
import pandas as pd

from food_security.base import FSBase

logger = logging.getLogger(__name__)


class FoodSupply(FSBase):
    """Calculate the total food supply based on import and export and food production."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        """Instantiate a FoodSupply object."""
        super().__init__(cfg=cfg)
        self.region = region
        self.fs_data_table = pd.read_csv(
           self.cfg["food_security_data_table"]["path"]
        )


    def add_food_supply(self) -> None:
        """Calculate food supply for regions."""


    def calculate_trade(self) -> gpd.GeoDataFrame:
        trade_gdf = self.region.merge(
            self.fs_data_table,
            on="region",
        )
        trade_gdf["imports"] = (
            trade_gdf["rice_yield"] * trade_gdf["import_coeff"]
        )

    def run(self) -> gpd.GeoDataFrame:
        """Run the food supply methods for adding data to the region GeoDataFrame."""
        super().run()
        return self.region
