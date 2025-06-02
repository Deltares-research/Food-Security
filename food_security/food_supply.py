"""Module containing the FoodSupply class."""

import logging
import re

import geopandas as gpd
import pandas as pd

from food_security.base import FSBase
from food_security.fao_api import get_trade_matrix_df

logger = logging.getLogger(__name__)


class FoodSupply(FSBase):
    """Calculate the total food supply based on import and export and food production."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        """Instantiate a FoodSupply object."""
        super().__init__(cfg=cfg)
        self.region = region

    def add_food_supply(self) -> None:
        """Calculate food supply for regions."""

    def get_food_trade_fluxes(self) -> pd.DataFrame:
        food_items = self.get_food_items()
        trade_matrix_df = get_trade_matrix_df(
            country_name=self.cfg["main"]["country"],
            year=self.cfg["main"]["year"],
        )

        # Filter food trade df by the available crop items attached to the region
        # geodataframe
        food_item_codes = [item[1] for item in food_items]
        trade_matrix_df = trade_matrix_df.loc[
            trade_matrix_df["Item Code"].isin(food_item_codes)
        ]

        export_food_df = trade_matrix_df.loc[
            trade_matrix_df["Element"] == "Export quantity"
        ]
        import_food_df = trade_matrix_df.loc[
            trade_matrix_df["Element"] == "Import quantity"
        ]

        # Sum food import and export, the tade dfs consists of export and
        #  import quantity per country
        total_export = (
            export_food_df[["Item Code", "Value"]]
            .groupby(by=["Item Code"])
            .sum()
            .reset_index()
        )
        total_import = (
            import_food_df[["Item Code", "Value"]]
            .groupby(by=["Item Code"])
            .sum()
            .reset_index()
        )
        # Remove items that are zero
        total_export = total_export[total_export["Value"] > 0]
        total_import = total_import[total_import["Value"] > 0]

        # Rename value column
        total_export = total_export.rename(columns={"Value": "export"})
        total_import = total_import.rename(columns={"Value": "import"})
        # Merge import and export and fill non matching rows with zero
        total_trade = total_export.merge(total_import, on="Item Code", how="outer")
        total_trade[["export", "import"]] = total_trade[["export", "import"]].fillna(0)

        # calculate trade fluxes
        total_trade["trade_flux"] = total_trade["import"] - total_trade["export"]
        local_trade = self.region[["Name", "land_ratio"]]

        trade_flux  = total_trade[["Item Code", "trade_flux"]]
        for _,row in local_trade.iterrows():
            local_trade_flux = trade_flux.copy()            
            local_trade_flux["trade_flux"] = trade_flux["trade_flux"] * row["land_ratio"]
        

    def _calculate_trade_fluxes(self, local_trade_flux: pd.DataFrame, region_name: str):
        for _, rows in local_trade_flux.iterrows():
            pass
            # Match the trade flux with the item in the regions gdf and add the flux to the amount


    def get_food_items(self) -> list[tuple]:
        data_cols = self.region.columns
        pattern = re.compile(r"^[A-Z ,/]+_[0-9]+$")
        other_food_cols = [name for name in data_cols if pattern.match(name)]
        return [(*col.split("_"),) for col in other_food_cols]

    def run(self) -> gpd.GeoDataFrame:
        """Run the food supply methods for adding data to the region GeoDataFrame."""
        super().run()
        return self.region
