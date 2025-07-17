import geopandas as gpd
import numpy as np

from food_security.components import FoodValue


def test_food_value(config_dict, test_data_dir):
    regions = gpd.read_file(test_data_dir / "food_production_results.fgb")
    fv = FoodValue(year=2016, cfg=config_dict, region=regions.iloc[[0]])
    rice = np.float64(fv.region["rice"].to_numpy()[0])
    fv.add_food_value()
    rice_calories = (
        rice
        * config_dict["food_production"]["modelled_crops"]["rice"]["calories"]
        * 10000
    )
    assert fv.region["rice"].to_numpy()[0] == rice_calories
    assert "population" in fv.region.columns
    assert "total_cals" in fv.region.columns
    assert "cal_per_capita_per_day" in fv.region.columns
    assert not fv.region["total_cals"].isna().all()
    assert not fv.region["cal_per_capita_per_day"].isna().all()
