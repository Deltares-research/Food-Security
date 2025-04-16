"""FoodProduction module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from food_security.base import FSBase
from food_security.data_reader import HisFile
from food_security.fao_api import get_food_production_df

if TYPE_CHECKING:
    import geopandas as gpd

logger = logging.getLogger(__name__)


class FoodProduction(FSBase):
    """FoodProduction class that groups methods for calculating the food production."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        """Instatiate a FoodProduction object.

        Args:
            cfg (dict): config dict.
            region (gpd.GeoDataFrame): GeoDataFrame containing regions with a Name
            column and geometries.

        """
        self.region = region
        super().__init__(cfg=cfg)

    def add_modelled_crops(self) -> None:
        """Add modeled crops to region GeoDataFrame."""
        for crop, file_path in self.cfg["food_production"]["modelled_crops"].items():
            logger.info("Parsing %s data from file", crop)
            hisfile = HisFile(file_path).read()
            crop_data = hisfile.to_table(year=self.cfg["main"]["year"])
            if crop_data:
                logger.info("Adding %s to regions")
                self.region = self.region.merge(crop_data, how="left", on="Name")

    def add_other_crops(self) -> None:
        """Add other crop production."""
        if Path(self.cfg["food_production"]["other_crops"]["path"]).exists():
            logger.info("Adding other crop data from file")
            other_crops = pd.read_csv(
                self.cfg["food_production"]["other_crops"]["path"],
            )
            join_column = self.cfg["food_production"]["other_crops"]["region_column"]
            self.region = self.region.merge(other_crops, how="left", on=join_column)
        else:
            logger.info("No other crop file found. Pulling other crop data from FAO")

            # fetch foastat production data
            # Next step is to calculate the production ratio of a region based on its area 
            # and the area of the country, big assumption
            # Use this ratio to calculate the production of items per region and return 

    def fetch_foastat_production_data(self) -> pd.DataFrame:
        prod_data = get_food_production_df(
            country_name=self.cfg["main"]["country"],
            year=self.cfg["main"]["year"],
        )
        conversion_table = pd.read_csv(
            self.cfg["food_production"]["fao"]["conversion_table"]
        )
        # merge prod_data with conversion table and only include items that are present
        # in the conversion table, how="inner"

        # Then pivot table so that items are columns
        # You now have total national production of items
        

    def run(self) -> gpd.GeoDataFrame:
        """Run the food production methods for adding data to a GeoDataFrame."""
        super().run()
        return self.region
