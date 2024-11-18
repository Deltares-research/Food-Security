"""FoodProduction module."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from food_security import DATA_DIR
from food_security.base import FSBase
from food_security.data_reader import Grid

if TYPE_CHECKING:
    import geopandas as gpd

logger = logging.getLogger(__name__)

class FoodProduction(FSBase):
    """FoodProduction class that groups methods for calculating the food production in an area."""

    def __init__(self, cfg: dict) -> None:
        """Instatiate a FoodProduction object.

        Args:
            cfg (dict): config dict

        """
        super().__init__(cfg=cfg)

    def add_lifestock(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Calculate the lifestock expressed as kg meat per ha per animal.

        Args:
            region (gpd.GeoDataFrame): GeoDataFrame containing (multi)polygons that should contain a column with
            'area [ha]'.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with the kg meat per ha per animal for every geometry.

        """
        paths = self.cfg["food_production"]["lifestock"].get("paths")
        animal_yield = pd.read_csv(DATA_DIR / "animal_yield.csv")
        for key, path in paths.items():
            logging.info("Reading %s grid data", key)
            grid = Grid(path)
            n_of_animals = f"n_{key}"
            region = grid.get_region_stat(regions=region, col_name=n_of_animals, stat="sum")
            region.loc[region[n_of_animals] < 0 ,n_of_animals] = 0 # set negative n of animals to 0
            kg_per_animal = animal_yield.loc[
                (animal_yield["animal"] == key) &
                  (animal_yield["Area"] == self.cfg["area"]["country"]), "kg_per_animal"]
            logging.info("Calculating the total kg of meat for %s", key)
            total_kg = kg_per_animal.to_numpy()[0] * region[n_of_animals]
            region[f"{key}_kg"] = total_kg
        return region


    def add_rice_yield(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def add_other_crops(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame | None:
        """Add other crops data to region geodataframe.

        Args:
            region (gpd.GeoDataFrame):  GeoDataFrame containing polygons of an area of interest
        Returns:
            gpd.GeoDataFrame | None: GeoDataFrame with added columns for the other crops.

        """
        paths = self.cfg["food_production"]["other_crops"].get("paths")
        if not paths:
            logging.warning("No other crops data found")
            return None

        for key, path in paths.items():
            data = pd.read_csv(path)
            data[key] = pd.to_numeric(data[key], errors="coerce")
            data = data.dropna()
            data[key] = data[key] * 1e6 # convert thousands of tons to kg
            join_column = "Name"
            if col := self.cfg["food_production"]["other_crops"].get("join_column"):
                join_column = col
            region = region.merge(data, left_on="Name", right_on=join_column, how="left")
            if join_column != "Name":
                region = region.drop(columns=join_column)
        return region




    def add_aquaculture(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def run(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Run the food production methods for adding data to a GeoDataFrame.

        Args:
            region (gpd.GeoDataFrame): GeoDataFrame containing polygons of an area of interest

        Returns:
            gpd.GeoDataFrame: Region GeoDataFrame with data columns on food production

        """
        super().run(gdf=region)


