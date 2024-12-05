"""FoodProduction module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from food_security import DATA_DIR
from food_security.base import FSBase
from food_security.data_reader import Grid, read_and_transform_rice_yield_table

if TYPE_CHECKING:
    import geopandas as gpd

logger = logging.getLogger(__name__)


class FoodProduction(FSBase):
    """FoodProduction class that groups methods for calculating the food production in an area."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        """Instatiate a FoodProduction object.

        Args:
            cfg (dict): config dict.
            region (gpd.GeoDataFrame): GeoDataFrame containing regions with a Name column and geometries.

        """
        self.region = region
        super().__init__(cfg=cfg)

    def add_lifestock(self) -> None:
        """Calculate the lifestock expressed as kg meat per ha per animal."""
        paths = self.cfg["food_production"]["lifestock"].get("paths")
        animal_yield = pd.read_csv(DATA_DIR / "animal_yield.csv")
        for key, path in paths.items():
            logging.info("Reading %s grid data", key)
            grid = Grid(path)
            n_of_animals = f"n_{key}"
            self.region = grid.get_region_stat(regions=self.region, col_name=n_of_animals, stat="sum")
            self.region.loc[self.region[n_of_animals] < 0, n_of_animals] = 0  # set negative n of animals to 0
            kg_per_animal = animal_yield.loc[
                (animal_yield["animal"] == key) & (animal_yield["Area"] == self.cfg["main"]["country"]), "kg_per_animal"
            ]
            logging.info("Calculating the total kg of meat for %s", key)
            total_kg = kg_per_animal.to_numpy()[0] * self.region[n_of_animals]
            self.region[f"{key}_kg"] = total_kg

    def add_rice_yield(self) -> None:
        """Add rice yield to self.region GeoDataFrame."""
        path = self.cfg["food_production"]["rice_yield"]["path"]
        rice_yield_df = read_and_transform_rice_yield_table(file_path=path, year=self.cfg["main"]["year"])
        if rice_yield_df:
            logging.info("Adding rice yield to regions.")
            self.region = self.region.merge(rice_yield_df, how="left", on="Name")

    def add_other_crops(self) -> None:
        """Add other crops data to region geodataframe."""
        paths = self.cfg["food_production"]["other_crops"].get("paths")
        if not paths:
            logging.warning("No other crops data found")
            return

        for key, path in paths.items():
            data = pd.read_csv(path)
            data[key] = pd.to_numeric(data[key], errors="coerce")
            data = data.dropna()
            data[key] = data[key] * 1e6  # convert thousands of tons to kg
            join_column = "Name"
            if col := self.cfg["food_production"]["other_crops"].get("join_column"):
                join_column = col
            self.region = self.region.merge(data, left_on="Name", right_on=join_column, how="left")
            logging.info("Added %s to region GeoDataFrame", key)
            if join_column != "Name":
                self.region = self.region.drop(columns=join_column)

    def add_aquaculture(self):
        pass

    def run(self) -> gpd.GeoDataFrame:
        """Run the food production methods for adding data to a GeoDataFrame."""
        super().run()
        return self.region
