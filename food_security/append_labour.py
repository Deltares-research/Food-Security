import re
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import rasterstats
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.transform import Affine, from_bounds, from_origin


def count_per_type(x, field_type):
    x = x[x == field_type]
    return np.ma.count(x)


def read_field_sizes(tif_file, area_gdf):
    with rasterio.open(tif_file) as src:
        stats = rasterstats.zonal_stats(
            area_gdf,
            tif_file,
            stats="count",
            add_stats={
                "count_0": lambda x: count_per_type(x, 0),
                "count_1": lambda x: count_per_type(x, 3502),
                "count_2": lambda x: count_per_type(x, 3503),
                "count_3": lambda x: count_per_type(x, 3504),
                "count_4": lambda x: count_per_type(x, 3505),
                "count_5": lambda x: count_per_type(x, 3506),
            },
            nodata=src.nodata,
        )

    return stats


def create_stats_df(stats, area_gdf):
    df_dict = {
        "name": area_gdf["Name"].values,
        "nr_of_fields": [s["count"] for s in stats],
        "nr_no_field": [s["count_0"] for s in stats],
        "nr_<0.64ha": [s["count_5"] for s in stats],
        "nr_0.64-2.56ha": [s["count_4"] for s in stats],
        "nr_2.56-16ha": [s["count_3"] for s in stats],
        "nr_16-100ha": [s["count_2"] for s in stats],
        "nr_>100ha": [s["count_1"] for s in stats],
    }
    df = pd.DataFrame(df_dict)
    return df


def compute_fraction(df, field):
    total = df["nr_of_fields"]
    value = df[f"nr_{field}"]

    df[f"fraction_{field}"] = value / total
    return df


def get_dominant_mech_score(df, mechanization_mapping, fields):
    field_type = df[[f"nr_{field}" for field in fields]].idxmax()
    field_type = field_type.split("nr_")[1]
    return mechanization_mapping[field_type]


def compute_weighted_mech_score(row, mechanization_mapping, fields):
    total = 0
    for field in fields:
        fraction = row[f"fraction_{field}"]
        score = mechanization_mapping[field]
        total += fraction * score
    return total


def add_mechanization_scores(df):
    mechanization_mapping = {
        "no_field": 0,
        "<0.64ha": 0,
        "0.64-2.56ha": 0.8,
        "2.56-16ha": 1,
        "16-100ha": 1,
        ">100ha": 1,
    }

    fields = ["no_field", "<0.64ha", "0.64-2.56ha", "2.56-16ha", "16-100ha", ">100ha"]

    for field in fields:
        df = compute_fraction(df, field)

    df["dom_mech_score"] = df.apply(
        lambda x: get_dominant_mech_score(
            x, mechanization_mapping=mechanization_mapping, fields=fields
        ),
        axis=1,
    )
    df["weighted_mech_score"] = df.apply(
        lambda x: compute_weighted_mech_score(
            x, mechanization_mapping=mechanization_mapping, fields=fields
        ),
        axis=1,
    )

    return df


def linear_labour_hours(x, min_val, max_val):
    a = max_val - min_val
    b = min_val
    y = a * x + b
    return y


def add_labour(df, production_df, mapping_df, crop, crop_category, year):
    nm_labour = mapping_df[
        (mapping_df["Food Category"] == crop_category)
        & (mapping_df["mechanized"] == "non-mechanized")
    ]["Labour for kg of Food (hrs/kg)"].values[0]
    m_labour = mapping_df[
        (mapping_df["Food Category"] == crop_category)
        & (mapping_df["mechanized"] == "mechanized")
    ]["Labour for kg of Food (hrs/kg)"].values[0]

    df["lb_hr_per_kg_dom"] = linear_labour_hours(
        df["dom_mech_score"], nm_labour, m_labour
    )
    df["lb_hr_per_kg_wa"] = linear_labour_hours(
        df["weighted_mech_score"], nm_labour, m_labour
    )

    yields_df = production_df[production_df["year"] == year]
    yields_df = yields_df[yields_df["crop_name"] == crop]
    yields_df["corrected_yield"] = yields_df["corrected_yield"].astype(np.float32)
    yields_df = yields_df.groupby("area_map_name")["corrected_yield"].sum()
    yields_df = yields_df.sort_index()

    df["production"] = yields_df.values
    df["lb_hr_dom"] = df["lb_hr_per_kg_dom"] * df["production"]
    df["lb_hr_wa"] = df["lb_hr_per_kg_wa"] * df["production"]
    df["FTE_dom"] = df["lb_hr_dom"] / (8 * 273)
    df["FTE_wa"] = df["lb_hr_wa"] / (8 * 273)

    return df


def add_labour_to_production(
    production_df: pd.DataFrame,
    input_path,
    field_size_tif_file,
    area_gdf_file,
    area_crs,
    mapping_file,
    labour_mapping_file,
):
    input_path = Path(input_path)
    labour_crop_mapping_df = pd.read_excel(
        input_path / labour_mapping_file, engine="openpyxl", sheet_name="labour_clc"
    )
    labour_value_mapping_df = pd.read_excel(
        input_path / labour_mapping_file, engine="openpyxl", sheet_name="labour"
    )

    area_mapping_df = pd.read_excel(
        input_path / mapping_file, engine="openpyxl", sheet_name="area"
    )

    area_gdf = gpd.read_file(input_path / area_gdf_file, crs=area_crs)
    area_gdf = area_gdf.set_crs(area_crs)
    area_gdf = area_gdf.to_crs("EPSG:4326")
    area_gdf = area_gdf.sort_values(by="Name")

    years = production_df["year"].unique()
    crops = production_df["crop_name"].unique()

    stats = read_field_sizes(
        tif_file=input_path / field_size_tif_file, area_gdf=area_gdf
    )
    labour_df = create_stats_df(stats=stats, area_gdf=area_gdf)
    labour_df = add_mechanization_scores(labour_df)

    # labour_df = labour_df[
    #     labour_df["name"].isin(area_mapping_df["area_map_name"].values)
    # ]
    labour_df = labour_df.reset_index(drop=True)

    production_df["FTE"] = 0.0
    production_df = production_df.sort_values(by="area_map_name")
    for crop in crops:
        crop_name_fao = production_df[production_df["crop_name"] == crop][
            "crop_name_fao"
        ].values[0]
        crop_category = labour_crop_mapping_df[
            labour_crop_mapping_df["FAOSTAT FLC"] == crop_name_fao
        ]["Category"].values[0]
        for year in years:
            labour_df = add_labour(
                df=labour_df,
                production_df=production_df,
                mapping_df=labour_value_mapping_df,
                crop=crop,
                crop_category=crop_category,
                year=year,
            )

            production_df.loc[
                (production_df["year"] == year) & (production_df["crop_name"] == crop),
                "FTE",
            ] = labour_df["FTE_wa"].values

    return production_df
