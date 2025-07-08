"""Data reader module for reading grid and vector data."""

from __future__ import annotations

import configparser
import logging
from datetime import datetime, timedelta
from pathlib import Path
from struct import unpack
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterstats import zonal_stats

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
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

    def get_region_stats(
        self, regions: gpd.GeoDataFrame, cols: dict,
    ) -> gpd.GeoDataFrame:
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
    data = [
        {"Name": region, "rice_yield": rice}
        for region, rice in zip(regions, rice_yield)
    ]
    return pd.DataFrame(data=data)


class HisFile:
    region_mapper = {
        "42": "Vihn Long",
        "43": "Ca Mau",
        "44": "An Giang",
        "45": "Dong Thap",
        "74": "Bac Lieu",
        "75": "Soc Trang",
        "76": "Kien Giang",
        "77": "Can Tho",
        "78": "Hau Giang",
        "164": "Tra Vinh",
        "175": "Tien Giang",
        "182": "Ben Tre",
    }

    def __init__(self, file_path: str | Path, crop: str):
        self.file_path = file_path
        self.crop = crop

    def read(self, *, hia: bool = False) -> None:
        """Read a hisfile to a xarray.Dataset.

        If hia is True, it will use the long location names from the .hia sidecar file
        if it exists.
        """
        hisfile = Path(self.file_path)
        filesize = hisfile.stat().st_size
        if filesize == 0:
            err_msg = f"HIS file is empty: {hisfile}"
            raise ValueError(err_msg)
        with hisfile.open("rb") as f:
            header = f.read(120).decode("utf-8")
            timeinfo = f.read(40).decode("utf-8")
            datestr = timeinfo[4:14].replace(" ", "0") + timeinfo[14:23]
            startdate = datetime.strptime(datestr, "%Y.%m.%d %H:%M:%S")  # noqa: DTZ007
            try:
                dt = int(timeinfo[30:-2])  # assumes unit is seconds
            except ValueError:
                # in some RIBASIM his files the s is one place earlier
                dt = int(timeinfo[30:-3])
            noout, noseg = unpack("ii", f.read(8))
            notim = int(
                (filesize - 168 - noout * 20 - noseg * 24) / (4 * (noout * noseg + 1)),
            )
            params = []
            for _ in range(noout):
                param = (f.read(20).rstrip().lstrip()).decode("utf-8")
                if (
                    count := params.count(param)
                ) > 0:  # Checks if there are duplicate data var names and adds a suffix
                    param += f"_{count + 1}"
                params.append(param)

            locnrs, locs = [], []
            for i in range(noseg):  # noqa: B007
                locnrs.append(unpack("i", f.read(4))[0])
                locs.append((f.read(20).rstrip()).decode("utf-8"))
            dates = []
            data = np.zeros((noout, notim, noseg), np.float32)
            for t in range(notim):
                ts = unpack("i", f.read(4))[0]
                date = startdate + timedelta(seconds=ts * dt)
                dates.append(date)
                for s in range(noseg):
                    data[:, t, s] = np.fromfile(f, np.float32, noout)
        if hia:
            # if there is a hia file next to the his, use the long locations
            hia_path = Path(hisfile).with_suffix(".hia")
            if hia_path.is_file():
                config = configparser.ConfigParser(interpolation=None)
                config.read(hia_path)
                locs = self._update_long(locs, config, "Long Locations")
                params = self._update_long(params, config, "Long Parameters")

        self.ds = xr.Dataset(
            {
                param: (["time", "station"], data[i, ...])
                for (i, param) in enumerate(params)
            },
            coords={
                "time": dates,
                "station": locs,
            },
            attrs={"header": header, "scu": dt, "t0": startdate},
        )

    def to_table(
        self,
        year: int,
        region_mapper: dict = region_mapper,
        param: str = "Actual farm gate pr",
    ) -> pd.DataFrame:
        """Convert the multi-dimensional his dataset to a 2D table.

        Args:
            year (int): select year of rice yield.
            region_mapper (dict, optional):dict with IDs and corresponding region names. Defaults to region_mapper.
            param (str, optional): Data variable to select. Defaults to "Actual farm gate pr".

        Returns:
            pd.DataFrame: With region and rice yield columns.

        """
        data = []
        time = f"{year}-01-01"
        for i, region in region_mapper.items():
            keys = []
            for x in range(4):
                if len(i) < 3:  # noqa: PLR2004
                    i = "_" + i  # noqa: PLW2901

                key = f"Nd_____{i} / Cr__{x + 1} /"
                if key not in self.ds.station:
                    continue
                keys.append(key)
            total_yield = self.ds.sel(station=keys, time=time)[param].to_numpy().sum()
            row = {"region": region, self.crop: total_yield}
            data.append(row)
        return pd.DataFrame(data)

    def _update_long(self, lst: list, config: dict, section: str) -> list:
        if section in config:
            # subtract 1 to get a 0 based index for the location
            long_map = {int(k) - 1: v for (k, v) in config[section].items()}
            for i, long_name in long_map.items():
                lst[i] = long_name
        return lst
