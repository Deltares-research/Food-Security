import re
import numpy as np
import rasterio
import geopandas as gpd
import pandas as pd

from food_security import data_reader
from rasterio.transform import from_origin
from rasterio.mask import mask
from rasterio.io import MemoryFile

from typing import Optional, Union, List

from food_security.config import ConfigReader
from food_security.intersect_shapefiles import (
    intersect_shapefiles,
    create_governorates_gdf,
    create_command_gdf,
)

from pathlib import Path


def load_input_data(
    his_file: Union[str, Path],
    communes_file: Union[str, Path],
    salinity_param_file: Union[str, Path],
    mapping_file: Union[str, Path],
    fao_mapping_file: Union[str, Path],
):
    # Read the HIS file and create a dataset for crop production data.
    production_his_file = data_reader.HisFile(his_file)
    production_his_file.read()
    production_ds = production_his_file.ds.copy(deep=True)

    # Read the communes shapefile and create a geopandas dataframe.
    communes_gdf = gpd.read_file(communes_file)

    # Read csv file containing salinity threshold and yield decrease per crop from FAO
    salinity_param_df = pd.read_csv(salinity_param_file)
    # Read the mapping file for crop name from FAO and crop name in RIBASIM model
    mapping_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="crop_id")
    fao_mapping_df = pd.read_excel(
        fao_mapping_file, engine="openpyxl", sheet_name="Salt"
    )
    # Read the mapping file for area name in communes_gdf and area name and id in RIBASIM model
    area_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="area")
    # Read file for coupling of crop id and crop name in RIBASIM model
    crop_id_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="crop")

    return (
        production_ds,
        communes_gdf,
        salinity_param_df,
        mapping_df,
        fao_mapping_df,
        area_df,
        crop_id_df,
    )


def create_salinity_raster(salinity_file, crs="EPSG:32648"):
    # Load DFlow salinity results
    salinity = np.loadtxt(salinity_file)

    # Get x-coords, y-coords and corresponding salinity (in PSU)
    xcoords = salinity[:, 0]
    ycoords = salinity[:, 1]
    salinity_values = salinity[:, 2]

    # Compute resolution in x and y direction
    resolution_x = (xcoords.max() - xcoords.min()) / len(np.unique(xcoords))
    resolution_y = (ycoords.max() - ycoords.min()) / len(np.unique(ycoords))

    # Define transform, to map to correct position
    transform = from_origin(
        west=xcoords.min(), north=ycoords.max(), xsize=resolution_x, ysize=resolution_y
    )

    # Create tif file
    raster_file = MemoryFile()
    dst = raster_file.open(
        driver="GTiff",
        height=len(np.unique(ycoords)),
        width=len(np.unique(xcoords)),
        count=1,
        dtype=salinity_values.dtype,
        crs=crs,
        transform=transform,
    )
    # Initialize raster
    raster = np.full((len(np.unique(ycoords)), len(np.unique(xcoords)) + 1), np.nan)

    # Fill the raster with values
    for i in range(len(salinity_values)):
        row = int((ycoords.max() - ycoords[i]) / resolution_x)
        col = int((xcoords[i] - xcoords.min()) / resolution_y)
        raster[row, col] = salinity_values[i]

    # Write the raster to the file
    dst.write(raster, 1)
    return dst


def get_salinity(ds, node, start_ts, end_ts):
    timeframe = slice(start_ts, end_ts)
    ds_selected = ds.sel({"station": node, "time": timeframe})["TDS"]
    salinity = np.nanmedian(ds_selected.values)
    return salinity


def overlap_landuse_mask(ec_raster, mask_raster):
    # Get EC raster data, meta data and shape
    ec = ec_raster.read(1)
    ec_meta = ec_raster.meta
    ec_shape = ec.shape

    # Get mask raster data, meta data and shape
    mask = mask_raster.read(1)
    mask_meta = mask_raster.meta
    mask_shape = mask.shape

    # Reproject mask to match the resolution and CRS of the EC raster
    mask_transformed = np.empty(ec_shape, dtype=mask.dtype)
    rasterio.warp.reproject(
        source=mask,
        destination=mask_transformed,
        src_transform=mask_meta["transform"],
        src_crs=mask_raster.crs,
        dst_transform=ec_meta["transform"],
        dst_crs=ec_raster.crs,
        resampling=rasterio.enums.Resampling.nearest,
    )

    # Mask the EC raster with the transformed mask
    masked_ec = np.where(mask_transformed == 1, ec, np.nan)

    # Update metadata to match the new data type and nodata value
    ec_meta.update(dtype="float32", nodata=np.nan)

    # Write the masked EC raster to the file in memory
    raster_file = MemoryFile()
    dst = raster_file.open(**ec_meta)
    dst.write(masked_ec, 1)
    return dst


def psu_to_ec(psu_raster):
    # Convert from PSU to EC using a conversion factor
    conversion_factor = 1.19
    ec_raster = conversion_factor * psu_raster

    return ec_raster


def ppm_to_ec(ppm):
    # Convert from PPM to EC using a conversion factor
    conversion_factor = 1 / 500
    ec = conversion_factor * ppm
    return ec


def overlap_ec_commune(
    ec_raster: rasterio.io.DatasetWriter,
    commune,
    communes_gdf,
    communes_crs="EPSG:4326",
):
    # Set the CRS of the communes_gdf to match the EC raster CRS
    communes_gdf = communes_gdf.set_crs(communes_crs)
    communes_gdf = communes_gdf.to_crs(ec_raster.crs)

    # Get geometry of the commune
    commune_geometry = communes_gdf[communes_gdf["Name"] == commune]["geometry"]

    # Mask the EC raster with the geometry of the commune and convert to EC
    ec_masked = mask(ec_raster, commune_geometry, nodata=np.nan)[0]
    ec_masked = psu_to_ec(ec_masked[0, ...])

    return ec_masked


def yield_reduction(
    ec_raster: np.ndarray,
    threshold=3,
    yield_decrease=12,
    raster: Optional[bool] = False,
):
    if raster:
        # Compute median of EC raster (where we have EC values after masking)
        ec_median = np.nanmedian(ec_raster)
    # Convert percentage of yield_decrease to a fraction
    yield_decrease = yield_decrease / 100

    # Compute yield reduction based on EC median and threshold and clip the result between 0 and 1
    yr = 1 - yield_decrease * (ec_median - threshold)
    yr = np.clip(yr, 0, 1)
    return yr


def corrected_production(production_commune, reduction):
    # Compute corrected crop production in the commune
    corrected = reduction * production_commune
    return corrected


def get_area_id(area_df, area):
    try:
        return area_df[area_df["area_map_name"] == area]["area_id"].iloc[0]
    except IndexError:
        return None


def get_crop_info(mapping_df, fao_mapping_df, crop_id_df, crop):
    # Get FAO crop name and crop id from mapping
    crop_fao = mapping_df[mapping_df["crop_name"] == crop]["crop_name_fao"].iloc[0]
    crop_fao_salt = fao_mapping_df[fao_mapping_df["FAOSTAT FLC"] == crop_fao][
        "FAOSTAT SALT"
    ].iloc[0]
    crop_id = crop_id_df[crop_id_df["crop_name"] == crop]["crop_id"].iloc[0]
    # Get just the numbers from crop id
    crop_id = re.search(r"Cr(\d+)", crop_id).group(1)

    return crop_fao, crop_fao_salt, crop_id


def get_production_value(production_ds, area_id, crop_id, year):
    # Create string for production station name from RIBASIM 8 model
    number_of_underscores_area = 8 - len(str(area_id))
    number_of_underscores_crop = 3 - len(str(int(crop_id)))

    underscores_area = number_of_underscores_area * "_"
    underscores_crop = number_of_underscores_crop * "_"
    production_station = (
        f"Nd{underscores_area}{area_id} / Cr{underscores_crop}{int(crop_id)} /"
    )
    # Get production data from RIBASIM model if it exists
    try:
        production_commune = production_ds.sel(
            {"station": production_station, "time": f"{year}-01-01"}
        )["Actual farm gate pr"].values
    except KeyError:
        production_commune = None

    return production_commune


def compute_salinity(
    area: str,
    year: Union[str, int],
    salinity_dir: Union[str, Path],
    salinity_filename: Union[str, Path],
    mask_dir: Union[str, Path],
    mask_filename: Union[str, Path],
    communes_gdf: gpd.GeoDataFrame,
    salinity_crs: str,
    area_crs: str,
):
    # Create salinity raster for the year
    salinity_file = salinity_filename.replace("{YEAR}", str(year))
    raster = create_salinity_raster(
        Path(salinity_dir) / salinity_file, crs=salinity_crs
    )

    # Create mask from landuse file
    mask_file = mask_filename.replace("{YEAR}", str(year))
    mask = rasterio.open(Path(mask_dir) / mask_file, "r")
    masked_raster = overlap_landuse_mask(raster, mask)

    # Get the salinity value for the commune
    overlapped_raster = overlap_ec_commune(
        masked_raster, area, communes_gdf, communes_crs=area_crs
    )

    # Compute median salinity for final table
    salinity = np.nanmedian(overlapped_raster)

    return salinity, overlapped_raster


def get_salinity_parameters(salinity_param_df: pd.DataFrame, crop_fao_salt: str):
    salinity_crop_row = salinity_param_df[
        salinity_param_df["Common name"] == crop_fao_salt
    ].iloc[0]
    # Get salinity threshold and yield decrease per crop from FAO
    try:
        a = float(salinity_crop_row["Threshold (ECe) (dS/m)"])
        b = float(salinity_crop_row["Slope (% per dS/m)"])
        comment = None
    except ValueError:
        a = 0
        b = 0
        comment = "No valid salinity parameters available."
    return a, b, comment


def apply_yield_correction(
    production_commune: float, overlapped_raster, a: float, b: float
):
    # Compute yield reduction based on salinity and FAO parameters
    reduction = yield_reduction(
        overlapped_raster, threshold=a, yield_decrease=b, raster=True
    )
    # Apply yield reduction to production
    corrected_yield = corrected_production(production_commune, reduction)
    return corrected_yield


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


def convert_to_departments(
    corrected_df: pd.DataFrame,
    conversion_matrix: pd.DataFrame,
    departments_gdf: pd.DataFrame,
):
    department_df = {
        "area_map_name": [],
        "crop_name": [],
        "crop_name_fao": [],
        "salinity": [],
        "yield": [],
        "year": [],
        "a": [],
        "b": [],
        "corrected_yield": [],
        "comment": [],
    }

    for year in corrected_df["year"].unique():
        for crop in corrected_df["crop_name"].unique():
            crop_yield_df = corrected_df[
                (corrected_df["crop_name"] == crop) & (corrected_df["year"] == year)
            ]
            crop_yield_df = crop_yield_df.sort_values(by="object_id")

            departmental_yield = get_departmental_yield(
                crop_yield_df, conversion_matrix, ["yield", "corrected_yield"]
            )

            n_departments = departments_gdf.shape[0]
            department_df["area_map_name"].append(departments_gdf["Name"].values)
            department_df["crop_name"].append([crop] * n_departments)
            department_df["crop_name_fao"].append(
                [crop_yield_df["crop_name_fao"].unique()[0]] * n_departments
            )
            department_df["salinity"].append(
                [crop_yield_df["salinity"].unique()[0]] * n_departments
            )
            department_df["yield"].append(departmental_yield["yield"].values)
            department_df["year"].append([year] * n_departments)
            department_df["a"].append([crop_yield_df["a"].unique()[0]] * n_departments)
            department_df["b"].append([crop_yield_df["b"].unique()[0]] * n_departments)
            department_df["corrected_yield"].append(
                departmental_yield["corrected_yield"].values
            )
            department_df["comment"].append(
                [crop_yield_df["comment"].unique()[0]] * n_departments
            )


def correct_crop_yield(
    his_file: Union[str, Path],
    communes_file: Union[str, Path],
    salinity_dir: Union[str, Path],
    salinity_filename: Union[str, Path],
    salinity_param_file: Union[str, Path],
    mask_dir: Union[str, Path],
    mask_filename: Union[str, Path],
    mapping_file: Union[str, Path],
    fao_mapping_file: Union[str, Path],
    crops_to_correct: List[str],
    years: List[Union[int, str]],
    area_crs: Optional[str] = "EPSG:4326",
    salinity_crs: Optional[str] = "EPSG:32648",
    common_unit_conversion: Optional[bool] = False,
    common_unit_filename: Optional[Union[str, Path]] = None,
    department_file: Optional[Union[str, Path]] = None,
):
    # Initialize a dictionary to store the results (columns in csv)
    df_dict = {
        "area_map_name": [],
        "crop_name": [],
        "crop_name_fao": [],
        "salinity": [],
        "yield": [],
        "year": [],
        "a": [],
        "b": [],
        "corrected_yield": [],
        "comment": [],
        "object_id": [],
    }

    (
        production_ds,
        communes_gdf,
        salinity_param_df,
        mapping_df,
        fao_mapping_df,
        area_df,
        crop_id_df,
    ) = load_input_data(
        his_file=his_file,
        communes_file=communes_file,
        salinity_param_file=salinity_param_file,
        mapping_file=mapping_file,
        fao_mapping_file=fao_mapping_file,
    )

    crops = mapping_df["crop_name"].values
    for area in communes_gdf["Name"]:
        # Get area from mapping if it exists
        area_id = get_area_id(area_df, area)
        if area_id is None:
            continue
        for crop in crops:
            # Get FAO crop name and crop id from mapping
            crop_fao, crop_fao_salt, crop_id = get_crop_info(
                mapping_df, fao_mapping_df, crop_id_df, crop
            )
            for year in years:
                production_area = get_production_value(
                    production_ds, area_id, crop_id, year
                )
                if production_area is None:
                    continue
                # Check if the crop needs to be corrected
                if crop in crops_to_correct:
                    salinity, overlapped_raster = compute_salinity(
                        area,
                        year,
                        salinity_dir,
                        salinity_filename,
                        mask_dir,
                        mask_filename,
                        communes_gdf,
                        salinity_crs,
                        area_crs,
                    )

                    a, b, comment = get_salinity_parameters(
                        salinity_param_df, crop_fao_salt
                    )
                    corrected_yield = apply_yield_correction(
                        production_area, overlapped_raster, a, b
                    )
                else:
                    salinity = 0
                    a, b = 0, 0
                    corrected_yield = production_area
                    comment = "No correction needed"

                try:
                    object_id = int(area.split("_")[-1])
                except ValueError:
                    object_id = None

                # Append data to dictionary
                df_dict["area_map_name"].append(area)
                df_dict["crop_name"].append(crop)
                df_dict["crop_name_fao"].append(crop_fao)
                df_dict["salinity"].append(salinity)
                df_dict["yield"].append(production_area)
                df_dict["year"].append(year)
                df_dict["a"].append(a)
                df_dict["b"].append(b)
                df_dict["corrected_yield"].append(corrected_yield)
                df_dict["comment"].append(comment)
                df_dict["object_id"].append(object_id)

    df = pd.DataFrame(df_dict)

    if common_unit_conversion:
        common_unit_gdf = create_command_gdf(common_unit_filename, crs="epsg:32636")
        department_gdf = create_governorates_gdf(department_file, crs="epsg:32636")
        conversion_matrix = intersect_shapefiles(common_unit_gdf, department_gdf)

        df = convert_to_departments(df, conversion_matrix, department_gdf)
    else:
        df = df.drop(columns=["object_id"])

    return df


if __name__ == "__main__":
    cfg_path = Path(
        "/Users/hemert/projects/food-security/Food-Security/examples/salinity_correction.toml"
    )  # Replace with the actual path to your config file
    config = ConfigReader(cfg_path)
    salinity_config = config["salinity_correction"]

    corrected_df = correct_crop_yield(
        his_file=salinity_config["crop_production"]["path"],
        communes_file=salinity_config["provinces"]["path"],
        salinity_dir=salinity_config["salinity_map"]["dir"],
        salinity_filename=salinity_config["salinity_map"]["filename"],
        salinity_param_file=salinity_config["salt_tolerance"]["path"],
        mask_dir=salinity_config["land_use"]["directories"]["Rice, paddy"],
        mask_filename=salinity_config["land_use"]["filename"]["filename"],
        fao_mapping_file="/Users/hemert/OneDrive - Stichting Deltares/Documents - International Delta Toolset/Food security/FAO.xlsx",
        mapping_file=salinity_config["mapping"]["path"],
        crops_to_correct=salinity_config["crops"]["crops_to_correct"],
        years=salinity_config["years"]["years"],
        area_crs=salinity_config["crs"]["commune"],
        salinity_crs=salinity_config["crs"]["salinity"],
    )

    corrected_df.to_csv(salinity_config["output"]["path"])
