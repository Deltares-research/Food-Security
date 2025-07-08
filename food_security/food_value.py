"""Module containing the FoodValue class."""

import re

import geopandas as gpd
import pandas as pd

from food_security.base import FSBase
from food_security.utils import _prep_conversion_table


class FoodValue(FSBase):
    """Food value class for calculating caloric value."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        """Initialize FoodValue object."""
        super().__init__(cfg=cfg)
        self.region = region

    def get_population(self, geometry: gpd.GeoDataFrame) -> None:
        pass

    def calc_caloric_value_per_crop(
        self, row: gpd.GeoSeries, calories_table: pd.DataFrame, pattern: re.Pattern,
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
                            calories_table["Item Code"] == item_code, "CALORIES kcal",
                        ].to_numpy()[0] * 10000 # 100 gr to tonnes
                    )
        # Calculate caloric value for modelled crops
        for crop, crop_dict in self.cfg["food_production"]["modelled_crops"].items():
            row[crop] = row[crop] * crop_dict["calories"] * 10000

        return row

    def add_food_value(self) -> None:
        """Add caloric value to modelled and other crops."""
        calories_table = pd.read_csv(
            self.cfg["food_production"]["fao"]["conversion_table"],
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
