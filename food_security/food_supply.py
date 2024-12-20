"""Module containing the FoodSupply class."""

import logging

import geopandas as gpd
import pandas as pd

from food_security.base import FSBase
from food_security.fao_api import get_food_export_df, get_food_production_df

logger = logging.getLogger(__name__)


class FoodSupply(FSBase):
    """Calculate the total food supply based on import and export and food production."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        super().__init__(cfg=cfg)
        self.region = region
        self.export_df = get_food_export_df(country_name=self.cfg["main"]["country"], year=self.cfg["main"]["year"])
        self.total_production_FAO = get_food_production_df(
            country_name=self.cfg["main"]["country"], year=self.cfg["main"]["year"]
        )

    def get_import(self):
        pass

    def get_export(self):
        export_df = self.export_df.copy(deep=True)
        export_df = export_df[
            (export_df["Year"] == self.cfg["main"]["year"]) & (export_df["Element"] == "Export Quantity")
        ]
        food_types = list(self.cfg["food_production"]["lifestock"]["paths"].keys()) + list(
            self.cfg["food_production"]["other_crops"]["paths"].keys(),
        )

        # TODO: calculate export of food based on export ratios for country

    def get_road_density(self, geometry: gpd.GeoDataFrame):
        pass

    def get_GPD_per_capita(self, geometry: gpd.GeoDataFrame):
        pass

    def calculate_food_supply_for_region(self, geometry: gpd.GeoDataFrame) -> float:
        pass

    def calculate_food_transfer_coefficient(
        self,
        GPD_per_capita,
        road_density,
    ) -> float:
        pass

    def add_food_supply_per_province(
        self,
        provinces: gpd.GeoDataFrame,
        region: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        food_supply_region = self.calculate_food_supply_for_region(geometry=region)

    def _calculate_export_ratio(self, food_items: list[str]) -> pd.DataFrame:
        mapping_df = pd.read_csv(self.cfg["food_supply"]["FAO_item_mapping"]["path"])
        tp = self.total_production_FAO
        tt = self.export_df

        export_ratios = []
        for food in food_items:
            item_code = str(mapping_df[mapping_df["Item"] == food]["Item_code"].to_numpy()[0])
            total_production = pd.to_numeric(tp[tp["Item Code"] == item_code]["Value"])
            total_export = pd.to_numeric(tt[tt["Item Code"] == item_code]["Value"]).sum()
            export_ratio = total_export / total_production
            export_ratios.append({"item": food, "export_ratio": export_ratio})
        return pd.DataFrame(export_ratios)

    @property
    def total_production_FAO(self) -> pd.DataFrame:  # noqa: N802
        return self._total_production_FAO

    @total_production_FAO.setter
    def total_production_FAO(self, df: pd.DataFrame):  # noqa: N802
        self._total_production_FAO = df[df["Area"] == self.cfg["main"]["country"]]
