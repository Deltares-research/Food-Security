"""Module containing the FoodSupply class."""

import logging
import re

import pandas as pd

from food_security.fao_api import get_trade_matrix_df
from food_security.interface.base import FSBase

logger = logging.getLogger(__name__)


class FoodSupply(FSBase):
    """Calculate the total food supply based on trade and food production."""

    def add_food_supply(self) -> None:
        """Calculate food supply for regions."""
        trade_flux = self.get_food_trade_fluxes()
        self.region = self.region.apply(
            self._calculate_trade_fluxes, axis=1, args=(trade_flux,),
        )

    def get_food_trade_fluxes(self) -> pd.DataFrame:
        """Retrieve import and export of food items and calculate the flux."""
        food_items = self.get_food_items
        trade_matrix_df = get_trade_matrix_df(
            country_name=self.cfg["main"]["country"],
            year=self.year,
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

        return total_trade[["Item Code", "trade_flux"]]

    @staticmethod
    def _calculate_trade_fluxes(row: pd.Series, trade_flux: pd.DataFrame) -> pd.Series:
        # Use regex pattern to check if col is <item>_<item code> col
        pattern = re.compile(r"^[A-Z ,/]+_[0-9]+$")
        for col in row.index:
            if pattern.match(col):
                item_code = col.split("_")[-1]
                # If item is in trade flux df calculate the supply of that item
                # based on the land ratio and the trade flux
                if item_code in trade_flux["Item Code"].to_numpy():
                    row[col] = row[col] + (
                        trade_flux.loc[
                            trade_flux["Item Code"] == item_code,
                            "trade_flux",
                        ].to_numpy()[0]
                        * row["land_ratio"]
                    )
        return row

    @property
    def get_food_items(self) -> list[tuple]:
        """Return food item with item code from dataframe."""
        data_cols = self.region.columns
        pattern = re.compile(r"^[A-Z ,/]+_[0-9]+$")
        other_food_cols = [name for name in data_cols if pattern.match(name)]
        return [(*col.split("_"),) for col in other_food_cols]