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
from intersect_shapefiles import (
    create_command_gdf,
    create_governorates_gdf,
    intersect_shapefiles,
)
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.transform import from_origin

from food_security import data_reader
from food_security.config import ConfigReader

import salinity_correction


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
        weighted_yields = df_agg[col] * multiplication_matrix.T
        departmental_yields[col] = weighted_yields.sum(axis=1)

    return departmental_yields


def get_hectares(prod_ds: xr.Dataset, area, area_id, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    node = f"{area_id} / {area}"

    hectares = (
        prod_ds.sel({"station": node, "time": timeframe})
        .sum(dim="time")["Area cultivated actual (ha)"]
        .values
    )
    return hectares


def compute_water_productivity(wq_ds: xr.Dataset, producer_price, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_supply = (
        wq_ds.sel({"station": area, "time": timeframe})
        .sum(dim="time")["Supply from network (m3/s)"]
        .values
    )

    water_productivity = producer_price / water_supply

    return water_productivity


def compute_water_use(prod_ds: xr.Dataset, area, area_id, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)
    node = f"{area_id} / {area}"
    water_use = (
        prod_ds.sel({"station": node, "time": timeframe})
        .mean(dim="time")["Supply (mm/day)"]
        .values
    )

    return water_use


def compute_water_exploitation_index(wq_ds: xr.Dataset, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_supply = (
        wq_ds.sel({"station": area, "time": timeframe})
        .sum(dim="time")["Supply from network (m3/s)"]
        .values
    )

    water_demand = (
        wq_ds.sel({"station": area, "time": timeframe})
        .sum(dim="time")["Demand from network (m3/s)"]
        .values
    )

    water_expoitation_index = water_supply / water_demand

    return water_expoitation_index


def get_water_demand(wq_ds: xr.Dataset, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_demand = (
        wq_ds.sel({"station": area, "time": timeframe})
        .sum(dim="time")["Demand from network (m3/s)"]
        .values
    )

    return water_demand


def get_water_supply(wq_ds: xr.Dataset, area, year):
    start_ts = f"{year}-10-01"
    end_ts = f"{year + 1}-10-1"
    timeframe = slice(start_ts, end_ts)

    water_supply = (
        wq_ds.sel({"station": area, "time": timeframe})
        .sum(dim="time")["Supply from network (m3/s)"]
        .values
    )

    return water_supply


def convert_to_departments(
    corrected_df: pd.DataFrame,
    conversion_matrix: pd.DataFrame,
    departments_gdf: pd.DataFrame,
):
    department_df = {
        "year": [],
        "area_map_name": [],
        "water_productivity": [],
        "water_use": [],
        "water_supply": [],
        "water_demand": [],
        "water_exploitation_index": [],
    }

    for year in corrected_df["year"].unique():
        wq_df = corrected_df[corrected_df["year"] == year]
        wq_df = wq_df.sort_values(by="object_id")

        departmental_yield = get_departmental_yield(
            wq_df,
            conversion_matrix,
            [
                "water_productivity",
                "water_use",
                "water_supply",
                "water_demand",
                "water_exploitation_index",
            ],
        )

        n_departments = departments_gdf.shape[0]
        department_df["year"].append([year] * n_departments)
        department_df["area_map_name"].append(departments_gdf["Name"].values)
        department_df["water_productivity"].append(
            departmental_yield["water_productivity"].values
        )
        department_df["water_use"].append(departmental_yield["water_use"].values)
        department_df["water_supply"].append(departmental_yield["water_supply"].values)
        department_df["water_demand"].append(departmental_yield["water_demand"].values)
        department_df["water_exploitation_index"].append(
            departmental_yield["water_exploitation_index"].values
        )
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
        "water_use": [],
        "water_supply": [],
        "water_demand": [],
        "water_exploitation_index": [],
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
            producer_price = corrected_df[
                (corrected_df["year"] == year) & (corrected_df["area_map_name"] == area)
            ]["corrected_yield_pp"].sum()

            water_productivity = compute_water_productivity(
                wq_ds=wq_ds, producer_price=producer_price, area=area, year=year
            )
            water_use = compute_water_use(
                prod_ds=prod_ds, area=area, area_id=area_id, year=year
            )
            water_supply = get_water_supply(wq_ds=wq_ds, area=area, year=year)
            water_demand = get_water_demand(wq_ds=wq_ds, area=area, year=year)
            water_exploitation_index = compute_water_exploitation_index(
                wq_ds=wq_ds, area=area, year=year
            )

            try:
                object_id = int(area.split("_")[-1])
            except ValueError:
                object_id = None

            df_dict["year"].append(year)
            df_dict["area_map_name"].append(area)
            df_dict["water_productivity"].append(water_productivity)
            df_dict["water_use"].append(water_use)
            df_dict["water_supply"].append(water_supply)
            df_dict["water_demand"].append(water_demand)
            df_dict["water_exploitation_index"].append(water_exploitation_index)
            df_dict["object_id"].append(object_id)

    df = pd.DataFrame(df_dict)

    if department_file:
        common_unit_gdf = create_command_gdf(common_unit_filename, crs=department_crs)
        department_gdf = create_governorates_gdf(department_file, crs=department_crs)
        conversion_matrix = intersect_shapefiles(common_unit_gdf, department_gdf)

        df = convert_to_departments(df, conversion_matrix, department_gdf)
    else:
        df = df.drop(columns=["object_id"])

    df["water_exploitation_index"] = df["water_supply"] / df["water_demand"]
    df = df.drop(columns=["water_supply", "water_demand"])

    return df


if __name__ == "__main__":
    cfg_path = Path(
        "/Users/hemert/projects/food-security/Food-Security/examples/salinity_correction_egypt.toml"
    )  # Replace with the actual path to your config file
    config = ConfigReader(cfg_path)
    salinity_config = config["salinity_correction"]

    corrected_df = salinity_correction.correct_crop_yield(
        land_name=config["main"]["country"],
        his_file=salinity_config["crop_production"]["path"],
        hectare_his_file=salinity_config["crop_production"]["ha_path"],
        communes_file=salinity_config["provinces"]["path"],
        salinity_dir=salinity_config["salinity_map"]["dir"],
        salinity_filename=salinity_config["salinity_map"]["filename"],
        salinity_param_file=salinity_config["salt_tolerance"]["path"],
        mask_dir=salinity_config["land_use"]["directories"]["Rice, paddy"],
        mask_filename=salinity_config["land_use"]["filename"]["filename"],
        fao_mapping_file="/Users/hemert/OneDrive - Stichting Deltares/Documents - International Delta Toolset/Food security/FAO.xlsx",
        mapping_file=salinity_config["mapping"]["path"],
        crops_to_correct=salinity_config["crops"]["crops_to_correct"],
        area_crs=salinity_config["crs"]["commune"],
        salinity_crs=salinity_config["crs"]["salinity"],
        common_unit_filename=None,
        department_file=None,
        department_crs=None,
    )

    water_df = create_water_df(
        land_name=config["main"]["country"],
        corrected_df=corrected_df,
        wq_his_file=salinity_config["crop_production"]["wq_path"],
        prod_his_file=salinity_config["crop_production"]["ha_path"],
        mapping_file=salinity_config["mapping"]["path"],
        common_unit_filename=salinity_config["departments"]["common_unit_path"],
        department_file=salinity_config["departments"]["departments_path"],
        department_crs=salinity_config["crs"]["department"],
    )

    water_df.to_csv(salinity_config["output"]["water_path"])
