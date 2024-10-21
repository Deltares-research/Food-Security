import geopandas as gpd
from pathlib import Path
from food_security.config import ConfigReader
from food_security.food_production import FoodProduction
from food_security.food_supply import FoodSupply


class FoodSecurity:
    def __init__(self, cfg_path: Path | str):
        self.config = ConfigReader(cfg_path)
        self.region = gpd.read_file(self.config["region"]["path"])

    def run(self):
        # Calculate food production
        food_production = FoodProduction(cfg=self.config)
        region = food_production.add_foodproduction_values(region=self.region)

        # Calculate food supply
        food_supply = FoodSupply(cfg=self.config)
        region = food_supply.calculate_food_supply(region=region)
