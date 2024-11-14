"""Data reader module for reading grid and vector data."""
from __future__ import annotations

from typing import TYPE_CHECKING

import rasterio
from rasterstats import zonal_stats

if TYPE_CHECKING:
    from pathlib import Path

    import geopandas as gpd


class Grid:
    """Grid class for reading and handling grid data."""

    def __init__(self, fp: Path | str):
        self.dataset = rasterio.open(fp)
        self.affine = self.dataset.transform
        self.data = self.dataset.read(1)

    def get_region_stat(
        self, regions: gpd.GeoDataFrame, col_name: str, stat:str,
    ) -> gpd.GeoDataFrame:
        z_stats = zonal_stats(regions, self.data, affine=self.affine, stats=[stat])
        stat_list = [s[stat] for s in z_stats]
        regions[col_name] = stat_list
        return regions

    def get_region_stats(self, regions: gpd.GeoDataFrame, cols: dict) -> gpd.GeoDataFrame:
        for col, stat in cols.items():
            regions = self.get_region_stat(regions, col_name=col, stat=stat)
        return regions





