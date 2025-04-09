"""FoodProduction module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from food_security.base import FSBase
from food_security.data_reader import HisFile

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

    def add_rice_yield(self) -> None:
        """Add rice yield to self.region GeoDataFrame."""
        path = self.cfg["food_production"]["rice_yield"]["path"]
        logger.info("Parsing rice yield data from his file.")
        hisfile = HisFile(path).read()
        rice_yield_df = hisfile.to_table(year=self.cfg["main"]["year"])
        if rice_yield_df:
            logger.info("Adding rice yield to regions.")
            self.region = self.region.merge(rice_yield_df, how="left", on="Name")

    def add_aquaculture(self) -> None:
        """Add aquaculture production."""
        raise NotImplementedError

    def run(self) -> gpd.GeoDataFrame:
        """Run the food production methods for adding data to a GeoDataFrame."""
        super().run()
        return self.region
