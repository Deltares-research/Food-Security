"""Main module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import geopandas as gpd

from food_security.config import ConfigReader
from food_security.food_production import FoodProduction
from food_security.food_supply import FoodSupply
from food_security.food_value import FoodValue

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_CRS = "EPSG:4326"


class FoodSecurity:
    def __init__(self, cfg_path: Path | str) -> None:
        """Instantiate a food security object."""
        self.config = ConfigReader(cfg_path)
        self.region = gpd.read_file(self.config["region"]["path"])
        provinces = gpd.read_file(self.config["provinces"]["path"])
        if provinces.crs != DEFAULT_CRS:
            provinces = provinces.to_crs(DEFAULT_CRS)
        self.provinces = provinces

    def run(self) -> None:
        """Run food security module."""
        # Calculate food production
        food_production = FoodProduction(cfg=self.config)
        provinces = food_production.run(region=self.provinces)

        # Calculate food supply for the provinces
        food_supply = FoodSupply(cfg=self.config)
        provinces = food_supply.add_food_supply_per_province(
            provinces=provinces,
            region=self.region,
        )

        # Calculate food value and variety
        food_value = FoodValue(cfg=self.cfg)
        provinces = food_value.add_food_value(provinces=provinces)

        # Calculate food security per province
        result = self._calculate_food_security(provinces=provinces)

        # Write result to file

        result.to_file()

    def _calculate_food_security(self, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        pass
