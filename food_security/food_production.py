import logging

import geopandas as gpd
import pandas as pd

from food_security import DATA_DIR
from food_security.data_reader import Grid

logger = logging.getLogger(__name__)

class FoodProduction:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def get_lifestock(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
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


    def get_rice_yield(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def get_other_crops(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass

    def get_aquaculture(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass


    def add_foodproduction_values(self, region:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        region = self.get_lifestock(region=region)
        region = self.get_rice_yield(region=region)
        region = self.get_other_crops(region=region)
        return self.get_aquaculture(region=region)

