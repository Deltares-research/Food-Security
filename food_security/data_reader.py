"""Data reader module for reading grid and vector data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd
import rasterio
from rasterstats import zonal_stats

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

    import geopandas as gpd


class Grid:
    """Grid class for reading and handling grid data."""

    def __init__(self, file_path: Path | str):
        self.dataset = rasterio.open(file_path)
        self.affine = self.dataset.transform
        self.data = self.dataset.read(1)

    def get_region_stat(
        self,
        regions: gpd.GeoDataFrame,
        col_name: str,
        stat: str,
    ) -> gpd.GeoDataFrame:
        z_stats = zonal_stats(regions, self.data, affine=self.affine, stats=[stat])
        stat_list = [s[stat] for s in z_stats]
        regions[col_name] = stat_list
        return regions

    def get_region_stats(self, regions: gpd.GeoDataFrame, cols: dict) -> gpd.GeoDataFrame:
        for col, stat in cols.items():
            regions = self.get_region_stat(regions, col_name=col, stat=stat)
        return regions


def read_and_transform_rice_yield_table(file_path: str | Path, year: int) -> None:
    region_mapper = {
        "VinghLn_AdvIrr42": "Vihn Long",
        "CaMau_AdvIrr43": "Ca Mau",
        "AnGi_AdvIrr44": "An Giang",
        "DongTh_AdvIrr45": "Dong Thap",
        "BacLieu_AdvIrr74": "Bac Lieu",
        "SocTrang_AdvIrr75": "Soc Trang",
        "KienGi_AdvIrr76": "Kien Giang",
        "CanTho_AdvIrr77": "Can Tho",
        "HuaGi_AdvIrr": "Hau Giang",
        "TraVinh_AdvIrr164": "Tra Vinh",
        "TienGi_AdvIrr175": "Tien Giang",
        "BenTre_AdvIrr182": "Ben Tre",
    }
    rice_yield_df = pd.read_excel(file_path, sheet_name="Sheet1")
    regions = rice_yield_df.iloc[1].dropna().to_numpy()
    regions = [region_mapper[region] for region in regions]
    date = f"01-01-{year}"
    if date not in rice_yield_df.GMT.to_numpy():
        logger.warning("No rice data found for year %s", year)
        return None
    rice_yield = rice_yield_df[rice_yield_df["GMT"] == date].to_numpy()[0][1:]
    data = [{"Name": region, "rice_yield": rice} for region, rice in zip(regions, rice_yield)]
    return pd.DataFrame(data=data)
