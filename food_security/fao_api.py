import faostat
import pandas as pd


class FAOClient:
    def __init__(self, username: str = None, password: str = None, token: str = None):
        self.token = token
        self.username = username
        self.password = password

        if self.token is None:
            faostat.set_requests_args(
                username=self.username,
                password=self.password,
            )
        else:
            faostat.set_requests_args(token=self.token)

    def get_food_production_df(self, country_name: str, year: int) -> pd.DataFrame:
        area_code = faostat.get_par("QCL", "area")[country_name]
        pars = {"area": area_code, "year": str(year), "element": "2510"}
        coding = {"area": "FAO"}
        return self._get_fao_df("QCL", pars=pars, coding=coding)

    def get_trade_matrix_df(self, country_name: str, year: int) -> pd.DataFrame:
        area_code = faostat.get_par("TM", "reporterarea")[country_name]
        pars = {
            "reporterarea": area_code,
            "element": ["2910", "2610"],
            "year": str(year),
        }  # element is the export quantity code
        coding = {"reporterarea": "FAO"}
        return self._get_fao_df("TM", pars=pars, coding=coding)

    def get_producer_price_df(
        self, country_name: str, year: int = None
    ) -> pd.DataFrame:
        area_code = faostat.get_par("PP", "area")[country_name]

        pars = {"area": area_code}
        coding = {}
        return self._get_fao_df("PP", pars=pars, coding=coding)

    def _get_fao_df(self, ds_code: str, pars: dict, coding: dict) -> pd.DataFrame:
        fao_df = faostat.get_data_df(ds_code, pars=pars, coding=coding)
        if fao_df.empty:
            err_msg = "No FAO data found for the given parameters."
            raise ValueError(err_msg)

        # Cast Value from str to float
        fao_df["Value"] = fao_df["Value"].astype(float)
        return fao_df

    def get_df(self, ds_code: str, pars: dict, coding: dict):
        return faostat.get_data_df(
            ds_code,
            pars=pars,
            coding=coding,
            token=self.token,
        )
