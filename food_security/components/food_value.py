"""Module containing the FoodValue class."""

import re

import geopandas as gpd
import pandas as pd

from food_security.interface.base import FSBase
from food_security.utils import _prep_conversion_table


class FoodValue(FSBase):
    """Food value class for calculating caloric value."""

    def calc_caloric_value_per_crop(
        self,
        row: gpd.GeoSeries,
        calories_table: pd.DataFrame,
        pattern: re.Pattern,
    ) -> None:
        """Calculate caloric value for crops row-wise."""
        # Calculate caloric value for crops from FAO
        for col in row.index:
            if pattern.match(col):
                item_code = col.split("_")[-1]
                if item_code in calories_table["Item Code"].to_numpy():
                    row[col] = (
                        row[col]
                        * calories_table.loc[
                            calories_table["Item Code"] == item_code,
                            "CALORIES kcal",
                        ].to_numpy()[0]
                        * 10000  # 100 gr to tonnes
                    )
        # Calculate caloric value for modelled crops
        for crop in self.cfg["food_production"]["modelled_crops"]["crops"]:
            row[crop] = (
                row[crop]
                * self.cfg["food_production"]["modelled_crops"][crop]["calories"]
                * 10000
            )

        return row

    def get_population(self) -> None:
        """Add region population."""
        pop_df = pd.read_csv(self.cfg["main"]["population"]["path"])
        if "Name" not in pop_df.columns:
            err_msg = (
                "Name column in population dataset not present, "
                "necessary for merging population data with region data."
            )
            raise ValueError(err_msg)
        self.region = self.region.merge(pop_df, on="Name")

    def get_per_capita_per_day_calories(self) -> None:
        """Add per capita per day calories."""
        non_food_cols = [
            "Code",
            "Name",
            "area",
            "perimeter",
            "area [ha]",
            "rice",
            "land_ratio",
            "geometry",
            "population",
            "year",
        ]

        food_cols = [
            food_col
            for food_col in self.region.columns
            if food_col not in non_food_cols
        ]

        food_df = self.region[food_cols]

        self.region["total_cals"] = food_df.sum(axis=1)
        self.region["cal_per_capita_per_day"] = (
            self.region["total_cals"] / self.region["population"] / 365
        )

    def add_food_value(self) -> None:
        """Add caloric value to modelled and other crops."""
        calories_table = pd.read_csv(
            self.cfg["food_production"]["fao"]["conversion_table"]["path"],
        )
        calories_table = _prep_conversion_table(calories_table)
        pattern = re.compile(r"^[A-Z ,/]+_[0-9]+$")
        self.region = self.region.apply(
            self.calc_caloric_value_per_crop,
            axis=1,
            args=(
                calories_table,
                pattern,
            ),
        )
        self.get_population()
        self.get_per_capita_per_day_calories()
