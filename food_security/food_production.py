"""FoodProduction module."""
import logging

import geopandas as gpd
import pandas as pd

from food_security import DATA_DIR
from food_security.base import FSBase
from food_security.data_reader import Grid

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
            region[f"{key}_kg_ha"] = total_kg / region["area [ha]"]
        return region


    def add_rice_yield(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def add_other_crops(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

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


