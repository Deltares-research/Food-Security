import faostat
import pandas as pd


def get_food_production_df(country_name: str, year: int) -> pd.DataFrame:
    area_code = faostat.get_par("QCL", "area")[country_name]
    pars = {"area": area_code, "year": str(year), "element": "2510"}
    coding = {"area": "FAO"}
    return _get_fao_df("QCL", pars=pars, coding=coding)


def get_food_export_df(country_name: str, year: int) -> pd.DataFrame:
    area_code = faostat.get_par("TM", "reporterarea")[country_name]
    pars = {"reporterarea": area_code, "element": "2910", "year": str(year)}  # element is the export quantity code
    coding = {"reporterarea": "FAO"}
    return _get_fao_df("TM", pars=pars, coding=coding)


def _get_fao_df(ds_code: str, pars: dict, coding: dict) -> pd.DataFrame:
    fao_df = faostat.get_data_df(ds_code, pars=pars, coding=coding)
    if fao_df.empty:
        err_msg = "No FAO data found for the given parameters."
        raise ValueError(err_msg)
    return fao_df
