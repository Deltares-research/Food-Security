"""Main module."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from food_security.components import FoodProduction, FoodSupply, FoodValue
from food_security.config import ConfigReader

DEFAULT_CRS = "EPSG:4326"


class FoodSecurity:
    """Run the food security components and calculate the food security."""

    def __init__(
        self,
        cfg_path: Path | str,
        output_path: Path | str | None = None,
        root: Path | str | None = None,
    ) -> None:
        """Instantiate a food security object."""
        self.config = ConfigReader(cfg_path, root=root)
        self.aoi = gpd.read_file(self.config["main"]["aoi"]["path"])
        self.output_path = output_path

    def run(self) -> None:
        """Run food security module."""
        # Calculate food production
        food_production = FoodProduction(cfg=self.config, region=self.aoi)
        self.aoi = food_production.run()

        # Calculate food supply for the provinces
        food_supply = FoodSupply(cfg=self.config, region=self.aoi)
        self.aoi = food_supply.run()

        # Calculate food value and variety
        food_value = FoodValue(cfg=self.config, region=self.aoi)
        self.aoi = food_value.run()

        # Calculate food security per province
        result = self._calculate_food_security(region=self.aoi)

        # Write result to file
        output_path = (
            self.output_path
            if self.output_path
            else Path(self.config["main"]["output_path"])
        )
        output_path.parent.mkdir(exist_ok=True)
        result.to_file(output_path)

    def _calculate_food_security(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        return region
