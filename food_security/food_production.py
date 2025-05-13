"""FoodProduction module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from food_security.base import FSBase
from food_security.data_reader import HisFile
from food_security.fao_api import get_food_production_df
from food_security.utils import _prep_conversion_table

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
            hisfile = HisFile(file_path, crop=crop)
            hisfile.read()
            crop_data = hisfile.to_table(year=self.cfg["main"]["year"])
            if not crop_data.empty:
                logger.info("Adding modelled %s production to regions", crop)
                crop_data = crop_data.rename(columns={"region": "Name"})
                self.region = self.region.merge(crop_data, how="left", on="Name")

    def add_other_crops(self) -> None:
        """Add other crop production."""
        if Path(self.cfg["food_production"]["other_crops"]["path"]).is_file():
            logger.info("Adding other crop data from file")
            other_crops = pd.read_csv(
                self.cfg["food_production"]["other_crops"]["path"],
            )
            join_column = self.cfg["food_production"]["other_crops"]["region_column"]
            self.region = self.region.merge(other_crops, how="left", on=join_column)
        else:
            logger.info("No other crop file found. Pulling other crop data from FAO")

            # fetch foastat production data
            # Next step is to calculate the production ratio of a region based on
            # its area and the area of the country, big assumption
            # Use this ratio to calculate the production of items per region and return
            other_crops = self.fetch_foastat_production_data()
            if "area" not in self.region.columns:
                self.calculate_region_area()

            # Convert m2 to km2
            self.region["area"] = self.region["area"] / 1e6

            # Calculate area to total national area ratio
            self.region["land_ratio"] = (
                self.region["area"] / self.cfg["main"]["country_area"]
            )

            # Set crop and production result to float
            other_crops["Value"] = other_crops["Value"].astype(float)

            for _, row in other_crops.iterrows():
                # Iterrate over available other crop production data and attach
                # to region dataframe
                col_name = f"{row['ITEM Nutrition']}_{row['Item Code']}"
                self.region[col_name] = self.region["land_ratio"] * row["Value"]
                self.region[col_name] = self.region[col_name].round(2)

    def fetch_foastat_production_data(self) -> pd.DataFrame:
        """Fetch the crop and livestock data of the FAO."""
        prod_data = get_food_production_df(
            country_name=self.cfg["main"]["country"],
            year=self.cfg["main"]["year"],
        )
        conversion_table = pd.read_csv(
            self.cfg["food_production"]["fao"]["conversion_table"],
        )
        # Prepare table for merge, removing duplicates and renaming code column
        conversion_table = _prep_conversion_table(conversion_table)

        # Drop rice related rows
        rice_codes = ["0027", "0028", "0029", "0032", "0038", "0033", "0034", "0035"]
        drop_index = conversion_table[
            conversion_table["Item Code"].isin(rice_codes)
        ].index
        conversion_table = conversion_table.drop(index=drop_index)
        return prod_data.merge(conversion_table, on="Item Code", how="inner").dropna()




    def calculate_region_area(self) -> None:
        """Calculate the area of the region in square meters."""
        utm = self.region.estimate_utm_crs()
        gdf = self.region.copy()
        gdf = gdf.to_crs(utm)
        self.region["area"] = gdf.geometry.area

    def run(self) -> gpd.GeoDataFrame:
        """Run the food production methods for adding data to a GeoDataFrame."""
        super().run()
        return self.region
