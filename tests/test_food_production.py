import logging

import geopandas as gpd

from food_security.components.food_production import FoodProduction


def test_FoodProduction(regions: gpd.GeoDataFrame, his_file, conversion_table, caplog):
    caplog.set_level(logging.INFO)
    cfg = {
        "main": {"year": 2016, "country": "Viet Nam", "country_area": 313000},
        "food_production": {
            "modelled_crops": {"rice": his_file},
            "fao": {"conversion_table": conversion_table},
            "other_crops": {"path": ""},
        },
    }
    fp = FoodProduction(cfg=cfg, region=regions)
    fp.add_modelled_crops()
    assert "rice" in fp.region.columns
    assert "Parsing rice data from file" in caplog.text
    assert "Adding modelled rice production to regions" in caplog.text

    fp.add_other_crops()
    assert len(fp.region.columns) == 74
    assert "No other crop file found. Pulling other crop data from FAO" in caplog.text
