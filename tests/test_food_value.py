import geopandas as gpd
import numpy as np

from food_security.food_value import FoodValue


def test_food_value(example_config, data_dir, test_data_dir):
    region = gpd.read_file(test_data_dir / "food_production_results.fgb").iloc[[0]]
    example_config["food_production"]["fao"]["conversion_table"] = (
        data_dir / "conversion_table.csv"
    )
    fv = FoodValue(cfg=example_config, region=region)
    rice = np.float64(fv.region["rice"].to_numpy()[0])
    fv.add_food_value()
    rice_calories = (
        rice
        * example_config["food_production"]["modelled_crops"]["rice"]["calories"]
        * 10000
    )
    assert fv.region["rice"].to_numpy()[0] == rice_calories
