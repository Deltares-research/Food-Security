"""Module containing utility functions."""

from pathlib import Path
from typing import Union

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from scipy.sparse import coo_matrix


def _prep_conversion_table(conversion_df: pd.DataFrame) -> pd.DataFrame:
    # drop duplicate occurrences of item code, retaining the first occurrence
    conversion_df = conversion_df.drop_duplicates(subset="code", keep="first").dropna()

    # Remove left padded zeros on code column
    conversion_df.loc[:, "code"] = conversion_df["code"].str.lstrip("0")

    # Rename code column to Item code to match FAOSTAT
    return conversion_df.rename(columns={"code": "Item Code"})


def intersect(gdf1, gdf2, index1, index2):
    data = []
    for i1, orig in gdf1.iterrows():
        for i2, ref in gdf2.iterrows():
            if ref["geometry"].intersects(orig["geometry"]):
                data.append(
                    {
                        "geometry": ref["geometry"].intersection(orig["geometry"]),
                        index1[1]: orig[index1[0]],
                        index2[1]: ref[index2[0]],
                    }
                )
    return gpd.GeoDataFrame(data)


def intersect(gdf1, gdf2, index1, index2):
    # Avoid index column name conflict
    gdf1 = gdf1.copy()
    gdf2 = gdf2.copy()

    if "index" in gdf1.columns:
        gdf1 = gdf1.drop(columns="index")
    if "index" in gdf2.columns:
        gdf2 = gdf2.drop(columns="index")

    # Spatial join to find intersecting pairs
    joined = gpd.sjoin(gdf1, gdf2, how="inner", predicate="intersects")

    # Subset the original dataframes based on join results
    gdf1_subset = gdf1.loc[joined.index]
    gdf2_subset = gdf2.loc[joined["index_right"]]

    # Reset index to align for overlay
    gdf1_subset = gdf1_subset.reset_index()
    gdf2_subset = gdf2_subset.reset_index()

    # Perform intersection
    intersection = gpd.overlay(gdf1_subset, gdf2_subset, how="intersection")

    # Rename columns to match expected output
    intersection[index1[1]] = intersection[index1[0] + "_1"]
    intersection[index2[1]] = intersection[index2[0] + "_2"]

    return intersection


def translate(command_shp, other_shp):
    # Create gdf with intersections between command and other shapefiles
    intersection = intersect(
        command_shp, other_shp, ["index", "command_id"], ["index", "dir_id"]
    )
    intersection["id"] = intersection.index

    # Compute area for each intersection and normalize it to a maximum of 1
    area = intersection.area
    areaMax = area.max()
    intersection["weight"] = area / areaMax
    intersection["weight_"] = 0

    command_shp["weight"] = 0

    for i, d in other_shp.iterrows():
        command_in_dir = intersection[intersection["dir_id"] == i]
        weight_sum = command_in_dir["weight"].sum()
        command_in_dir.loc[:, "weight_"] = command_in_dir["weight"] / weight_sum
        for j, c in command_in_dir.iterrows():
            command_shp.loc[c["command_id"], "weight"] += d["weight"] * c["weight_"]

    return command_shp


def create_command_gdf(path_command: Union[str, Path], crs: str) -> gpd.GeoDataFrame:
    command_gdf = gpd.read_file(path_command)
    command_gdf = command_gdf.to_crs(crs)
    command_gdf["index"] = command_gdf["OBJECTID"]
    command_gdf.index = command_gdf["index"]
    return command_gdf


def create_governorates_gdf(
    path_governorates: Union[str, Path], crs: str
) -> gpd.GeoDataFrame:
    governorate_gdf = gpd.read_file(path_governorates)
    governorate_gdf = governorate_gdf.to_crs(crs)

    # Clean up self intersecting geometry
    for k, v in governorate_gdf.iterrows():
        governorate_gdf.loc[[k], "geometry"] = governorate_gdf.loc[
            [k], "geometry"
        ].buffer(0)

    governorate_gdf["index"] = governorate_gdf.index
    governorate_gdf["weight"] = 1
    return governorate_gdf


def intersect_shapefiles(
    command_gdf: gpd.GeoDataFrame, governorate_gdf: gpd.GeoDataFrame
) -> pd.DataFrame:
    # command_gdf = translate(command_shp=command_gdf, other_shp=governorate_gdf)

    intersection = intersect(
        command_gdf, governorate_gdf, ["index", "command_id"], ["index", "other_id"]
    )
    intersection["id"] = intersection.index

    intersection["area"] = intersection.area
    intersection_ = intersection[["command_id", "other_id", "area"]]

    matrix = coo_matrix(
        (
            intersection_["area"].values,
            (intersection_["command_id"].values, intersection_["other_id"].values),
        )
    )
    matrix = matrix.tocsr()
    matrix_df = pd.DataFrame(matrix.toarray())

    matrix_relative = matrix_df.div(matrix_df.sum(axis=0), axis=1)
    matrix_relative = matrix_relative[matrix_relative.index.isin(command_gdf.index)]
    matrix_relative = matrix_relative[governorate_gdf.index]

    return matrix_relative
