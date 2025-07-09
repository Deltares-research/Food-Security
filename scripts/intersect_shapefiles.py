# %%
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import pandas as pd

from typing import Union
import pathlib
from pathlib import Path
from scipy.sparse import coo_matrix

src_dir = pathlib.Path("~").expanduser().resolve() / "data/food-security"


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
    return command_shp


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


# # path_command = 'data/1-input/Final3_Command_Area.shp'
# path_command = "data/1-input/Final4b_Command_Area_Feddans.shp"
# command_shp = gpd.read_file(
#     src_dir / "shapefiles/Final4b_Command_Area_Feddans.shp"
# ).to_crs("epsg:32636")
# command_shp["index"] = command_shp["OBJECTID"]
# command_shp.index = command_shp["index"]

# governorates = gpd.read_file(src_dir / "shapefiles/EGY_Governorates_WGS.shp").to_crs(
#     "epsg:32636"
# )
# governorates = gpd.read_file(src_dir / "shapefiles/departments.shp").to_crs(
#     "epsg:32636"
# )
# # governorates.index = governorates["OBJECTID"].values

# others = [
#     {"name": "governorates", "df": governorates},
# ]


def intersect_shapefiles(
    command_gdf: gpd.GeoDataFrame, governorate_gdf: gpd.GeoDataFrame
) -> pd.DataFrame:
    intersection = intersect(
        command_gdf, governorate_gdf, ["index", "command_id"], ["index", "other_id"]
    )
    intersection["id"] = intersection.index

    intersection["area"] = intersection.area
    intersection_ = intersection[["command_id", "other_id", "area"]]

    matrix = pd.DataFrame(
        coo_matrix(
            (
                intersection_["area"].values,
                (intersection_["command_id"].values, intersection_["other_id"].values),
            )
        )
    )

    matrix_relative = matrix.div(matrix.sum(axis=0), axis=1)
    matrix_relative = matrix_relative[matrix_relative.index.isin(command_gdf.index)]
    matrix_relative = matrix_relative[governorate_gdf.index]

    return matrix_relative


# for other in others:
#     other_shp = other["df"]

#     # clean up self intersecting geometry
#     for k, v in other_shp.iterrows():
#         other_shp.loc[[k], "geometry"] = other_shp.loc[[k], "geometry"].buffer(0)

#     other_shp["index"] = other_shp.index

#     # directorates_shp['weight'] = random.sample(range(10, 300), len(directorates_shp))
#     other_shp["weight"] = 1
#     command_new_shp = translate(command_shp, other_shp)

#     intercection = intersect(
#         command_shp, other_shp, ["index", "command_id"], ["index", "other_id"]
#     )
#     intercection["id"] = intercection.index

#     intercection["area"] = intercection.area
#     intercection_ = intercection[["command_id", "other_id", "area"]]

#     matrix = pd.DataFrame(
#         coo_matrix(
#             (
#                 intercection_["area"].values,
#                 (intercection_["command_id"].values, intercection_["other_id"].values),
#             )
#         ).toarray()
#     )
#     matrix_relative = matrix.div(matrix.sum(axis=0), axis=1)

#     matrix_relative = matrix_relative[matrix_relative.index.isin(command_shp.index)]
#     matrix_relative = matrix_relative[other_shp.index]

#     matrix_relative.to_excel(src_dir / f'shapefiles/command-area-{other["name"]}.xlsx')
