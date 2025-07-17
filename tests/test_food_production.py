import logging

import geopandas as gpd

from food_security.components.food_production import FoodProduction


def test_FoodProduction(regions: gpd.GeoDataFrame, config_dict ,caplog):
    caplog.set_level(logging.INFO)
    fp = FoodProduction(year=2016, cfg=config_dict, region=regions)
    fp.add_modelled_crops()
    assert "rice" in fp.region.columns
    assert "Parsing rice yield from file" in caplog.text
    assert "Adding modelled rice production to regions" in caplog.text

    fp.add_other_crops()
    assert len(fp.region.columns) == 74
    assert "No other crop file found. Pulling other crop data from FAO" in caplog.text
