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
from food_security import append_labour


def load_input_data(
    his_file: Union[str, Path],
    hectare_his_file: Union[str, Path],
    communes_file: Union[str, Path],
    salinity_param_file: Union[str, Path],
    mapping_file: Union[str, Path],
    fao_mapping_file: Union[str, Path],
    land_name: str,
):
    # Read the HIS file and create a dataset for crop production data.
    production_his_file = data_reader.HisFile(his_file, crop=None)
    production_his_file.read()
    production_ds = production_his_file.ds.copy(deep=True)

    hectare_his_file = data_reader.HisFile(hectare_his_file, crop=None)
    hectare_his_file.read(hia=True)
    hectare_ds = hectare_his_file.ds.copy(deep=True)
    # Read the communes shapefile and create a geopandas dataframe.
    if communes_file:
        communes_gdf = gpd.read_file(communes_file)
    else:
        communes_gdf = None

    # Read csv file containing salinity threshold and yield decrease per crop from FAO
    salinity_param_df = pd.read_csv(salinity_param_file)
    # Read the mapping file for crop name from FAO and crop name in RIBASIM model
    mapping_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="crop_id")
    fao_mapping_salt_df = pd.read_excel(
        fao_mapping_file, engine="openpyxl", sheet_name="Salt"
    )
    fao_mapping_price_df = pd.read_excel(
        fao_mapping_file, engine="openpyxl", sheet_name="Price"
    )
    # Read the mapping file for area name in communes_gdf and area name and id in RIBASIM model
    area_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="area")
    # Read file for coupling of crop id and crop name in RIBASIM model
    crop_id_df = pd.read_excel(mapping_file, engine="openpyxl", sheet_name="crop")

    pp_df = get_producer_prices_df(land_name=land_name)

    return (
        production_ds,
        hectare_ds,
        communes_gdf,
        salinity_param_df,
        mapping_df,
        fao_mapping_salt_df,
        fao_mapping_price_df,
        area_df,
        crop_id_df,
        pp_df,
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
    commune_geometry = communes_gdf[communes_gdf["OBJECTID"] == commune]["geometry"]
    if len(commune_geometry) == 0:
        commune_geometry = communes_gdf[communes_gdf["Name"] == commune]["geometry"]

    # Mask the EC raster with the geometry of the commune and convert to EC
    ec_masked = mask(ec_raster, commune_geometry, nodata=np.nan)[0]
    ec_masked = psu_to_ec(ec_masked[0, ...])

    return ec_masked


def yield_reduction(
    ec_raster: np.ndarray,
    threshold=3,
    yield_decrease=12,
    is_raster: Optional[bool] = False,
):
    if is_raster:
        # Compute median of EC raster (where we have EC values after masking)
        ec_median = np.nanmedian(ec_raster)
    else:
        ec_median = ec_raster
    # Convert percentage of yield_decrease to a fraction
    yield_decrease = yield_decrease / 100

    # Compute yield reduction based on EC median and threshold and clip the result between 0 and 1
    yr = 1 - yield_decrease * (ec_median - threshold)
    yr = np.clip(yr, 0, 1)
    return yr


def corrected_production(production_commune, reduction):
    # Compute corrected crop production in the commune
    if np.isnan(reduction):
        return production_commune
    corrected = reduction * production_commune
    return corrected


def get_area_id(area_df, area):
    try:
        return area_df[area_df["area_name"] == area]["area_id"].iloc[0]
    except IndexError:
        return None


def get_crop_info(
    mapping_df, fao_mapping_salt_df, fao_mapping_price_df, crop_id_df, crop
):
    # Get FAO crop name and crop id from mapping
    crop_fao = mapping_df[mapping_df["crop_name"] == crop]["crop_name_fao"].iloc[0]
    crop_fao_salt = fao_mapping_salt_df[fao_mapping_salt_df["FAOSTAT FLC"] == crop_fao][
        "FAOSTAT SALT"
    ].iloc[0]
    # try:
    crop_fao_price = fao_mapping_price_df[fao_mapping_price_df["fao_flc"] == crop_fao][
        "fao_producer"
    ].values
    # except IndexError:
    #     crop_fao_price = None
    crop_id = crop_id_df[crop_id_df["crop_name"] == crop]["crop_id"].iloc[0]
    # Get just the numbers from crop id
    crop_id = re.search(r"Cr(\d+)", crop_id).group(1)

    crop_start_ts = crop_id_df[crop_id_df["crop_name"] == crop]["start_ts"].iloc[0]
    crop_end_ts = crop_id_df[crop_id_df["crop_name"] == crop]["end_ts"].iloc[0]

    crop_start_ts_dt = datetime.datetime.strptime(crop_start_ts, "%m-%d")
    crop_end_ts_dt = datetime.datetime.strptime(crop_end_ts, "%m-%d")

    return (
        crop_fao,
        crop_fao_salt,
        crop_fao_price,
        crop_id,
        crop_start_ts,
        crop_end_ts,
        crop_start_ts_dt,
        crop_end_ts_dt,
    )


def get_year_info(production_ds):
    # Get years from dataset
    years = production_ds.time.values
    years = years.astype("datetime64[Y]").astype(int) + 1970
    # Convert to datetime
    years_dt = pd.to_datetime(years, format="%Y")
    # Update coords in production_ds
    production_ds = production_ds.assign_coords(time=years_dt)
    return production_ds, years


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


def get_hectares(
    hectare_ds: xr.Dataset,
    area: str,
    area_id,
    crop_name: str,
    crop_id,
    crop_start_ts: str,
    crop_end_ts: str,
    crop_start_ts_dt: str,
    crop_end_ts_dt: str,
    year: Union[str, int],
):
    start_ts = f"{year}-{crop_start_ts}"
    if crop_start_ts_dt >= crop_end_ts_dt:
        end_ts = f"{year + 1}-{crop_end_ts}"
    else:
        end_ts = f"{year}-{crop_end_ts}"

    variable_name = f"P Cr{crop_id}/{crop_name}"

    timeframe = slice(start_ts, end_ts)

    node = f"{area_id} / {area}"
    if node not in hectare_ds.station.values:
        node = f"{area_id} / {area}_AdvIrr{area_id}"

    selection = hectare_ds.sel(station=node, time=timeframe)[variable_name]

    if selection.sizes.get("time", 0) == 0:
        return np.nan

    hectares = selection.max(dim="time").values

    return hectares


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
    salinity_file = Path(str(salinity_filename).replace("{YEAR}", str(year)))
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
        overlapped_raster, threshold=a, yield_decrease=b, is_raster=True
    )
    # Apply yield reduction to production
    corrected_yield = corrected_production(production_commune, reduction)
    return corrected_yield


def get_producer_prices_df(land_name: str):
    area_code = faostat.get_par("PP", "area")[land_name]

    pp_df = faostat.get_data_df("PP", pars={"area": area_code})
    pp_df = pp_df[pp_df["Element"] == "Producer Price (USD/tonne)"]
    pp_df = pp_df[pp_df["Months"] == "Annual value"]

    return pp_df


def get_producer_prices(pp_df: pd.DataFrame, crop_name):
    pp_df_sorted = pp_df.sort_values(by="Year")
    pp_crop = pp_df_sorted[
        (pp_df_sorted["Item"].isin(crop_name))
        & (pp_df_sorted["Year"].isin(["2019", "2020", "2021"]))
    ]["Value"].values
    pp_crop = pp_crop.astype(np.float32)
    if len(pp_crop) == 0:
        pp_crop = pp_df_sorted[pp_df_sorted["Item"].isin(crop_name)]["Value"].values[
            -3:
        ]
        pp_crop = pp_crop.astype(np.float32)
        if len(pp_crop) == 0:
            return 0
    pp_crop = pp_crop.mean()

    return pp_crop


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
        "hectares": [],
        "year": [],
        "a": [],
        "b": [],
        "corrected_yield": [],
        "corrected_yield_pp": [],
        "comment": [],
    }

    conversion_matrix = conversion_matrix.T

    for year in corrected_df["year"].unique():
        for crop in corrected_df["crop_name"].unique():
            crop_yield_df = corrected_df[
                (corrected_df["crop_name"] == crop) & (corrected_df["year"] == year)
            ]
            crop_yield_df = crop_yield_df.sort_values(by="object_id")

            departmental_yield = get_departmental_yield(
                crop_yield_df,
                conversion_matrix,
                [
                    "salinity",
                    "yield",
                    "hectares",
                    "corrected_yield",
                    "corrected_yield_pp",
                ],
            )

            n_departments = departments_gdf.shape[0]
            department_df["area_map_name"].append(departments_gdf["Name"].values)
            department_df["crop_name"].append([crop] * n_departments)
            department_df["crop_name_fao"].append(
                [crop_yield_df["crop_name_fao"].unique()[0]] * n_departments
            )
            department_df["salinity"].append(departmental_yield["salinity"].values)
            department_df["yield"].append(departmental_yield["yield"].values)
            department_df["hectares"].append(departmental_yield["hectares"].values)
            department_df["year"].append([year] * n_departments)
            department_df["a"].append([crop_yield_df["a"].unique()[0]] * n_departments)
            department_df["b"].append([crop_yield_df["b"].unique()[0]] * n_departments)
            department_df["corrected_yield"].append(
                departmental_yield["corrected_yield"].values
            )
            department_df["corrected_yield_pp"].append(
                departmental_yield["corrected_yield_pp"].values
            )
            department_df["comment"].append(
                [crop_yield_df["comment"].unique()[0]] * n_departments
            )
    for key, value in department_df.items():
        value_array = np.array(value)
        new_value = value_array.flatten()
        department_df[key] = new_value

    department_df = pd.DataFrame(department_df)
    return department_df


def yield_correction_xyz(
    production_area: str,
    area: str,
    year,
    salinity_dir,
    salinity_filename,
    mask_dir,
    mask_filename,
    communes_gdf,
    salinity_crs,
    area_crs: str,
    a: Union[int, float],
    b: Union[int, float],
):
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
    corrected_yield = apply_yield_correction(production_area, overlapped_raster, a, b)

    return corrected_yield, salinity


def yield_correction_his(
    production_area,
    area: str,
    year: Union[int, float, str],
    crop_start_ts,
    crop_end_ts,
    crop_start_ts_dt,
    crop_end_ts_dt,
    salinity_filename: Union[Path, str],
    a: Union[int, float],
    b: Union[int, float],
    salinity_ds: xr.Dataset = None,
):
    if salinity_ds is None:
        salinity_his = data_reader.HisFile(salinity_filename, crop=None)
        salinity_his.read(hia=True)
        salinity_ds = salinity_his.ds.copy(deep=True)

    if area not in salinity_ds.station:
        return (None, None, salinity_ds)

    start_ts = f"{year}-{crop_start_ts}"
    if crop_start_ts_dt >= crop_end_ts_dt:
        end_ts = f"{year + 1}-{crop_end_ts}"
    else:
        end_ts = f"{year}-{crop_end_ts}"

    salinity = get_salinity(salinity_ds, area, start_ts, end_ts)
    salinity = ppm_to_ec(salinity)

    # Compute yield reduction based on salinity and FAO parameters
    reduction = yield_reduction(
        salinity, threshold=a, yield_decrease=b, is_raster=False
    )
    # Apply yield reduction to production
    corrected_yield = corrected_production(production_area, reduction)

    return corrected_yield, salinity, salinity_ds


def correct_crop_yield(
    land_name: str,
    his_file: Union[str, Path],
    hectare_his_file: Union[str, Path],
    salinity_dir: Union[str, Path],
    salinity_filename: Union[str, Path],
    salinity_param_file: Union[str, Path],
    mask_dir: Union[str, Path],
    mask_filename: Union[str, Path],
    mapping_file: Union[str, Path],
    fao_mapping_file: Union[str, Path],
    crops_to_correct: List[str],
    area_crs: Optional[str] = "EPSG:4326",
    salinity_crs: Optional[str] = "EPSG:32648",
    communes_file: Optional[Union[str, Path]] = None,
    common_unit_filename: Optional[Union[str, Path]] = None,
    department_file: Optional[Union[str, Path]] = None,
    department_crs: Optional[str] = None,
):
    # Initialize a dictionary to store the results (columns in csv)
    df_dict = {
        "area_map_name": [],
        "crop_name": [],
        "crop_name_fao": [],
        "salinity": [],
        "yield": [],
        "hectares": [],
        "year": [],
        "a": [],
        "b": [],
        "corrected_yield": [],
        "corrected_yield_pp": [],
        "comment": [],
        "object_id": [],
    }

    (
        production_ds,
        hectare_ds,
        communes_gdf,
        salinity_param_df,
        mapping_df,
        fao_mapping_salt_df,
        fao_mapping_price_df,
        area_df,
        crop_id_df,
        pp_df,
    ) = load_input_data(
        his_file=his_file,
        hectare_his_file=hectare_his_file,
        communes_file=communes_file,
        salinity_param_file=salinity_param_file,
        mapping_file=mapping_file,
        fao_mapping_file=fao_mapping_file,
        land_name=land_name,
    )

    crops = mapping_df["crop_name"].values
    production_ds, years = get_year_info(production_ds=production_ds)
    salinity_ds = None
    for area in area_df["area_name"]:
        # Get area from mapping if it exists
        area_map_name = area_df[area_df["area_name"] == area]["area_map_name"].iloc[0]
        area_id = get_area_id(area_df, area)
        print(f"{area_id} / {area}")
        # print(area_id, area, area_map_name, years, crops)
        if area_id is None:
            continue
        for crop in crops:
            # Get FAO crop name and crop id from mapping
            (
                crop_fao,
                crop_fao_salt,
                crop_fao_price,
                crop_id,
                crop_start_ts,
                crop_end_ts,
                crop_start_ts_dt,
                crop_end_ts_dt,
            ) = get_crop_info(
                mapping_df, fao_mapping_salt_df, fao_mapping_price_df, crop_id_df, crop
            )

            for year in years:
                production_area = get_production_value(
                    production_ds, area_id, crop_id, year
                )
                if production_area is None:
                    continue
                hectares = get_hectares(
                    hectare_ds=hectare_ds,
                    area=area,
                    area_id=area_id,
                    crop_name=crop,
                    crop_id=crop_id,
                    crop_start_ts=crop_start_ts,
                    crop_end_ts=crop_end_ts,
                    crop_start_ts_dt=crop_start_ts_dt,
                    crop_end_ts_dt=crop_end_ts_dt,
                    year=year,
                )
                if crop_fao == "Soybeans":
                    ___ = 10
                crop_pp = get_producer_prices(pp_df=pp_df, crop_name=crop_fao_price)
                # Check if the crop needs to be corrected
                if crop in crops_to_correct:
                    a, b, comment = get_salinity_parameters(
                        salinity_param_df, crop_fao_salt
                    )

                    salinity_filename = Path(salinity_filename)
                    if salinity_filename.suffix == ".xyz":
                        corrected_yield, salinity = yield_correction_xyz(
                            production_area=production_area,
                            area=area_map_name,
                            year=year,
                            salinity_dir=salinity_dir,
                            salinity_filename=salinity_filename,
                            salinity_crs=salinity_crs,
                            mask_dir=mask_dir,
                            mask_filename=mask_filename,
                            communes_gdf=communes_gdf,
                            area_crs=area_crs,
                            a=a,
                            b=b,
                        )
                    elif (
                        salinity_filename.suffix == ".his"
                        or salinity_filename.suffix == ".HIS"
                    ):
                        result = yield_correction_his(
                            production_area=production_area,
                            area=area,
                            year=year,
                            crop_start_ts=crop_start_ts,
                            crop_end_ts=crop_end_ts,
                            crop_start_ts_dt=crop_start_ts_dt,
                            crop_end_ts_dt=crop_end_ts_dt,
                            salinity_filename=salinity_filename,
                            a=a,
                            b=b,
                            salinity_ds=salinity_ds,
                        )
                        corrected_yield, salinity, salinity_ds = result
                        if corrected_yield is None:
                            continue

                else:
                    salinity = 0
                    a, b = 0, 0
                    corrected_yield = production_area
                    comment = "No correction needed"

                try:
                    # object_id = int(area.split("_")[-1])
                    object_id = area_map_name
                except ValueError:
                    object_id = None

                # Append data to dictionary
                df_dict["area_map_name"].append(area)
                df_dict["crop_name"].append(crop)
                df_dict["crop_name_fao"].append(crop_fao)
                df_dict["salinity"].append(salinity)
                df_dict["yield"].append(production_area)
                df_dict["hectares"].append(hectares)
                df_dict["year"].append(year)
                df_dict["a"].append(a)
                df_dict["b"].append(b)
                df_dict["corrected_yield"].append(corrected_yield)
                df_dict["corrected_yield_pp"].append(corrected_yield / 1000 * crop_pp)
                df_dict["comment"].append(comment)
                df_dict["object_id"].append(object_id)

    df = pd.DataFrame(df_dict)

    if department_file:
        common_unit_gdf = create_command_gdf(common_unit_filename, crs=department_crs)
        department_gdf = create_governorates_gdf(department_file, crs=department_crs)
        conversion_matrix = intersect_shapefiles(common_unit_gdf, department_gdf)

        df = convert_to_departments(df, conversion_matrix, common_unit_gdf)
        if salinity_filename.suffix == ".xyz":
            df = correct_salinity(
                df=df,
                salinity_dir=salinity_dir,
                salinity_filename=salinity_filename,
                salinity_crs=salinity_crs,
                mask_dir=mask_dir,
                mask_filename=mask_filename,
                communes_gdf=common_unit_gdf,
                area_crs=department_crs,
            )
    else:
        df = df.drop(columns=["object_id"])

    return df


def correct_salinity(
    df: pd.DataFrame,
    salinity_dir,
    salinity_filename,
    salinity_crs,
    mask_dir,
    mask_filename,
    communes_gdf,
    area_crs,
):
    for i, row in df.iterrows():
        a, b = row["a"], row["b"]
        if a == 0 and b == 0:
            continue
        else:
            corrected_yield, salinity = yield_correction_xyz(
                production_area=row["yield"],
                area=row["area_map_name"],
                year=row["year"],
                salinity_dir=salinity_dir,
                salinity_filename=salinity_filename,
                salinity_crs=salinity_crs,
                mask_dir=mask_dir,
                mask_filename=mask_filename,
                communes_gdf=communes_gdf,
                area_crs=area_crs,
                a=a,
                b=b,
            )
            df.loc[i, "corrected_yield"] = corrected_yield
            df.loc[i, "salinity"] = salinity
    return df


def generate_crop_yield_csv(
    config_path: Union[str, Path],
    save=True,
    add_labor=False,
    convert_departments=True,
    username="",
    password="",
):
    cfg_path = Path(config_path)
    config = ConfigReader(cfg_path)
    salinity_config = config["salinity_correction"]

    faostat.set_requests_args(
        username=username,
        password=password,
    )

    if convert_departments:
        common_unit_filename = salinity_config["departments"]["common_unit_path"]
        department_file = salinity_config["departments"]["departments_path"]
        department_crs = salinity_config["crs"]["department"]
    else:
        common_unit_filename = None
        department_file = None
        department_crs = None

    corrected_df = correct_crop_yield(
        land_name=config["main"]["country"],
        his_file=salinity_config["crop_production"]["path"],
        hectare_his_file=salinity_config["crop_production"]["ha_path"],
        communes_file=salinity_config["provinces"]["path"],
        salinity_dir=salinity_config["salinity_map"]["dir"],
        salinity_filename=salinity_config["salinity_map"]["filename"],
        salinity_param_file=salinity_config["salt_tolerance"]["path"],
        mask_dir=salinity_config["land_use"]["directories"]["Rice, paddy"],
        mask_filename=salinity_config["land_use"]["filename"]["filename"],
        fao_mapping_file=salinity_config["mapping"]["fao_mapping"],
        mapping_file=salinity_config["mapping"]["path"],
        crops_to_correct=salinity_config["crops"]["crops_to_correct"],
        area_crs=salinity_config["crs"]["commune"],
        salinity_crs=salinity_config["crs"]["salinity"],
        common_unit_filename=common_unit_filename,
        department_file=department_file,
        department_crs=department_crs,
    )

    if add_labor:
        corrected_df = append_labour.add_labour_to_production(
            production_df=corrected_df,
            field_size_tif_file=salinity_config["mapping"]["field_sizes"],
            area_gdf_file=salinity_config["departments"]["common_unit_path"],
            area_crs=salinity_config["crs"]["department"],
            mapping_file=salinity_config["mapping"]["path"],
            labour_mapping_file=salinity_config["mapping"]["fao_mapping"],
        )

    if save:
        corrected_df.to_csv(salinity_config["output"]["salinity_path"])

    return corrected_df
