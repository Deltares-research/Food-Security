import geopandas as gpd
from pathlib import Path
from food_security.config import ConfigReader
from food_security.food_production import FoodProduction
from food_security.food_supply import FoodSupply
from food_security.food_value import FoodValue


class FoodSecurity:
    def __init__(self, cfg_path: Path | str):
        self.config = ConfigReader(cfg_path)
        self.region = gpd.read_file(self.config["region"]["path"])
        self.provinces = gpd.read_file(self.config["provinces"]["path"])

    def run(self):
        # Calculate food production
        food_production = FoodProduction(cfg=self.config)
        provinces = food_production.add_foodproduction_values(geometry=self.provinces)

        # Calculate food supply for the provinces
        food_supply = FoodSupply(cfg=self.config)
        provinces = food_supply.add_food_supply_per_province(
            provinces=provinces, region=self.region
        )

        # Calculate food value and variety
        food_value = FoodValue(cfg=self.cfg)
        provinces = food_value.add_food_value(provinces=provinces)

        # Calculate food security per province
        result = self.calculate_food_security(provinces=provinces)

        # Write result to file

        result.to_file()

    def calculate_food_security(self, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass
