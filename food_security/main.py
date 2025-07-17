"""Main module."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

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
        self.years = (
            [self.config["main"]["year"]]
            if not isinstance(self.config["main"]["year"], list)
            else self.config["main"]["year"]
        )

    def run(self) -> None:
        """Run food security module."""
        results = []

        for year in self.years:
            # Calculate food production
            gdf = self.aoi.copy(deep=True)
            gdf["year"] = year
            food_production = FoodProduction(year=year, cfg=self.config, region=gdf)
            gdf = food_production.run()

            # Calculate food supply for the provinces
            food_supply = FoodSupply(year=year, cfg=self.config, region=gdf)
            gdf = food_supply.run()

            # Calculate food value and variety
            food_value = FoodValue(year=year, cfg=self.config, region=gdf)
            gdf = food_value.run()

            # Calculate food security per province
            results.append(self._calculate_food_security(region=gdf))

        # Write result to file
        output_path = (
            self.output_path
            if self.output_path
            else Path(self.config["main"]["output_path"])
        )
        output_path.parent.mkdir(exist_ok=True)
        results = pd.concat(results)
        results.to_file(output_path)

    def _calculate_food_security(self, region: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        return region
