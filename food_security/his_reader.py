"""Module for reading and parsing his files."""

from __future__ import annotations

import configparser
from datetime import datetime, timedelta
from pathlib import Path
from struct import unpack

import numpy as np
import xarray as xr


def _update_long(lst: list, config: dict, section: str) -> list:
    if section in config:
        # subtract 1 to get a 0 based index for the location
        long_map = {int(k) - 1: v for (k, v) in config[section].items()}
        for i, long_name in long_map.items():
            lst[i] = long_name
    return lst


def read(hisfile: str | Path, *, hia: bool = True) -> xr.dataset:
    """Read a hisfile to a xarray.Dataset.

    If hia is True, it will use the long location names from the .hia sidecar file
    if it exists.
    """
    hisfile = Path(hisfile)
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
        params = [(f.read(20).rstrip()).decode("utf-8") for _ in range(noout)]
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
            locs = _update_long(locs, config, "Long Locations")
            params = _update_long(params, config, "Long Parameters")

    return xr.Dataset(
        {param: (["time", "station"], data[i, ...]) for (i, param) in enumerate(params)},
        coords={
            "time": dates,
            "station": locs,
        },
        attrs={"header": header, "scu": dt, "t0": startdate},
    )
