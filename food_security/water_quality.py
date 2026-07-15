import datetime
import re
from pathlib import Path
from typing import List, Optional, Union

import faostat
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from food_security.utils import (
    create_command_gdf,
    create_governorates_gdf,
    intersect_shapefiles,
)
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.transform import from_origin

from food_security import data_reader
from food_security.config import ConfigReader
from food_security import salinity_correction


def load_input_data(
    wq_his_file: Union[str, Path],
    prod_his_file: Union[str, Path],
    mapping_file: Union[str, Path],
    land_name: str,
):
    wq_his_file = data_reader.HisFile(wq_his_file, crop=None)
    wq_his_file.read(hia=True)
    wq_ds = wq_his_file.ds.copy(deep=True)

    # Read the HIS file and create a dataset for crop production data.
    prod_his_file = data_reader.HisFile(prod_his_file, crop=None)
    prod_his_file.read(hia=True)
    prod_ds = prod_his_file.ds.copy(deep=True)

    area_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="area")

    return (wq_ds, prod_ds, area_df)


def get_departmental_yield(
    df: pd.DataFrame, multiplication_matrix: pd.DataFrame, cols: List[str]
):
    df_agg = df.groupby("object_id", as_index=True).agg(
        {
            col: "sum" if col in cols else "first"
            for col in df.columns
            if col != "object_id"
        }
    )
    departmental_yields = {}

    for col in cols:
        if multiplication_matrix.shape[0] == df_agg.shape[0]:
            departmental_yields[col] = df_agg[col]
        else:
            weighted_yields = df_agg[col] * multiplication_matrix.T
            departmental_yields[col] = weighted_yields.sum(axis=1)

    return departmental_yields


def get_hectares(prod_ds: xr.Dataset, area, area_id, year, timesteps=False):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    node = f"{area_id} / {area}"

    if timesteps:
        hectares = prod_ds.sel({"station": node, "time": timeframe})[
            "Area cultivated actual (ha)"
        ].values
    else:
        hectares = (
            prod_ds.sel({"station": node, "time": timeframe})
            .mean(dim="time")["Area cultivated actual (ha)"]
            .values
        )
    return hectares


def compute_water_productivity(wq_ds: xr.Dataset, producer_price, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_supply = (
        wq_ds.sel({"station": area, "time": timeframe})
        .mean(dim="time")["Supply from network (m3/s)"]
        .values
    )

    water_supply_annual = water_supply * 365.25 * 24 * 3600

    water_productivity = producer_price / water_supply_annual

    return water_productivity


def get_timesteps(prod_ds: xr.Dataset, area, area_id, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-01"
    timeframe = slice(start_ts, end_ts)
    node = f"{area_id} / {area}"
    timesteps = prod_ds.sel({"station": node, "time": timeframe})["time"].values

    return timesteps


def compute_water_use(prod_ds: xr.Dataset, area, area_id, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-01"
    timeframe = slice(start_ts, end_ts)
    node = f"{area_id} / {area}"
    water_use = prod_ds.sel({"station": node, "time": timeframe})[
        "Supply (mm/day)"
    ].values

    return water_use


def compute_water_exploitation_index(wq_ds: xr.Dataset, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_supply = wq_ds.sel({"station": area, "time": timeframe})[
        "Supply from network (m3/s)"
    ].values

    water_demand = wq_ds.sel({"station": area, "time": timeframe})[
        "Demand from network (m3/s)"
    ].values

    water_expoitation_index = water_supply / water_demand

    return water_expoitation_index


def get_water_demand(wq_ds: xr.Dataset, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_demand = wq_ds.sel({"station": area, "time": timeframe})[
        "Demand from network (m3/s)"
    ].values

    return water_demand


def get_water_supply(wq_ds: xr.Dataset, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_supply = wq_ds.sel({"station": area, "time": timeframe})[
        "Supply from network (m3/s)"
    ].values

    return water_supply


def convert_to_departments(
    corrected_df: pd.DataFrame,
    conversion_matrix: pd.DataFrame,
    departments_gdf: pd.DataFrame,
    indicator_columns: List[str],
):

    conversion_matrix = conversion_matrix.T

    base_keys = ["year", "area_map_name"]

    # Add 'timestep' if present
    if "timestep" in corrected_df.columns:
        base_keys.insert(1, "timestep")  # insert after 'year'

    department_df = {}

    for key in base_keys + indicator_columns:
        department_df[key] = []

    group_cols = ["year"]
    if "timestep" in corrected_df.columns:
        group_cols.append("timestep")

    for group_vals, wq_df in corrected_df.groupby(group_cols):
        # Unpack group values
        if len(group_cols) == 2:
            year, timestep = group_vals
        else:
            year = group_vals
            timestep = None

        # wq_df = corrected_df[corrected_df["year"] == year]
        # wq_df = wq_df.sort_values(by="object_id")

        departmental_yield = get_departmental_yield(
            wq_df,
            conversion_matrix,
            indicator_columns,
        )

        n_departments = departments_gdf.shape[0]
        department_df["year"].append([year] * n_departments)
        if timestep is not None:
            department_df["timestep"].append([timestep] * n_departments)
        department_df["area_map_name"].append(departments_gdf["Name"].values)
        for indicator in indicator_columns:
            department_df[indicator].append(departmental_yield[indicator].values)

    for key, value in department_df.items():
        value_array = np.array(value)
        new_value = value_array.flatten()
        department_df[key] = new_value

    department_df = pd.DataFrame(department_df)
    return department_df


def create_water_df(
    land_name: str,
    corrected_df: pd.DataFrame,
    wq_his_file: Union[str, Path],
    prod_his_file: Union[str, Path],
    mapping_file: Union[str, Path],
    common_unit_filename: Optional[Union[str, Path]] = None,
    department_file: Optional[Union[str, Path]] = None,
    department_crs: Optional[str] = None,
):
    # Initialize a dictionary to store the results (columns in csv)
    df_dict = {
        "year": [],
        "area_map_name": [],
        "water_productivity": [],
        "hectares": [],
        "object_id": [],
    }

    df_dict_time = {
        "year": [],
        "timestep": [],
        "area_map_name": [],
        "water_use": [],
        "water_supply": [],
        "water_demand": [],
        "water_exploitation_index": [],
        "hectares": [],
        "object_id": [],
    }

    (
        wq_ds,
        prod_ds,
        area_df,
    ) = load_input_data(
        wq_his_file=wq_his_file,
        prod_his_file=prod_his_file,
        mapping_file=mapping_file,
        land_name=land_name,
    )

    years = corrected_df["year"].unique()
    areas = corrected_df["area_map_name"].unique()

    for year in years:
        for area in areas:
            area_id = salinity_correction.get_area_id(area_df, area)
            # print(area_id, area, area_map_name, years, crops)
            if area_id is None:
                continue

            hectares = get_hectares(
                prod_ds=prod_ds, area=area, area_id=area_id, year=year
            )
            hectares_t = get_hectares(
                prod_ds=prod_ds, area=area, area_id=area_id, year=year, timesteps=True
            )
            producer_price = corrected_df[
                (corrected_df["year"] == year) & (corrected_df["area_map_name"] == area)
            ]["corrected_yield_pp"].sum()

            water_productivity = compute_water_productivity(
                wq_ds=wq_ds, producer_price=producer_price, area=area, year=year
            )

            timesteps = get_timesteps(
                prod_ds=prod_ds, area=area, area_id=area_id, year=year
            )
            water_use = compute_water_use(
                prod_ds=prod_ds, area=area, area_id=area_id, year=year
            )
            water_supply = get_water_supply(wq_ds=wq_ds, area=area, year=year)
            water_demand = get_water_demand(wq_ds=wq_ds, area=area, year=year)
            water_exploitation_index = compute_water_exploitation_index(
                wq_ds=wq_ds, area=area, year=year
            )

            n_timesteps = timesteps.shape[0]

            try:
                object_id = int(area.split("_")[-1])
            except ValueError:
                object_id = None

            df_dict["year"].append(year)
            df_dict["area_map_name"].append(area)
            df_dict["water_productivity"].append(water_productivity)
            df_dict["hectares"].append(hectares)
            df_dict["object_id"].append(object_id)

            df_dict_time["year"].append([year] * n_timesteps)
            df_dict_time["area_map_name"].append([area] * n_timesteps)
            df_dict_time["timestep"].append(timesteps)
            df_dict_time["water_use"].append(water_use)
            df_dict_time["water_supply"].append(water_supply)
            df_dict_time["water_demand"].append(water_demand)
            df_dict_time["water_exploitation_index"].append(water_exploitation_index)
            df_dict_time["hectares"].append(hectares_t)
            df_dict_time["object_id"].append([object_id] * n_timesteps)

    for indicator in df_dict_time.keys():
        try:
            df_dict_time[indicator] = np.concatenate(df_dict_time[indicator])
        except ValueError:
            # Fallback for scalars or inconsistent shapes
            df_dict_time[indicator] = np.array(df_dict_time[indicator])

    df = pd.DataFrame(df_dict)
    df_time = pd.DataFrame(df_dict_time)

    if department_file:
        common_unit_gdf = create_command_gdf(common_unit_filename, crs=department_crs)
        department_gdf = create_governorates_gdf(department_file, crs=department_crs)
        conversion_matrix = intersect_shapefiles(common_unit_gdf, department_gdf)

        df = convert_to_departments(
            df,
            conversion_matrix,
            common_unit_gdf,
            indicator_columns=["water_productivity", "hectares"],
        )
        df_time = convert_to_departments(
            df_time,
            conversion_matrix,
            common_unit_gdf,
            indicator_columns=[
                "water_use",
                "water_supply",
                "water_demand",
                "water_exploitation_index",
                "hectares",
            ],
        )
    else:
        df = df.drop(columns=["object_id"])
        df_time = df_time.drop(columns=["object_id"])

    df_time["water_exploitation_index"] = (
        df_time["water_supply"] / df_time["water_demand"]
    )
    df_time = df_time.drop(columns=["water_supply", "water_demand"])

    return df, df_time


def generate_water_csv(
    config_path: Union[str, Path],
    save=True,
    corrected_df=None,
    username="",
    password="",
):
    cfg_path = Path(config_path)
    config = ConfigReader(cfg_path)
    salinity_config = config["salinity_correction"]

    if corrected_df is None:
        corrected_df = salinity_correction.generate_crop_yield_csv(
            config_path=config_path,
            save=False,
            add_labor=False,
            convert_departments=False,
            username=username,
            password=password,
        )

    water_df, water_df_time = create_water_df(
        land_name=config["main"]["country"],
        corrected_df=corrected_df,
        wq_his_file=salinity_config["crop_production"]["wq_path"],
        prod_his_file=salinity_config["crop_production"]["ha_path"],
        mapping_file=salinity_config["mapping"]["path"],
        common_unit_filename=salinity_config["departments"]["common_unit_path"],
        department_file=salinity_config["departments"]["departments_path"],
        department_crs=salinity_config["crs"]["department"],
    )

    if save:
        water_df.to_csv(salinity_config["output"]["water_prod_path"])
        water_df_time.to_csv(salinity_config["output"]["water_use_path"])

    return water_df, water_df_time
