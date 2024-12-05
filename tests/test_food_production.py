import numpy as np
import pandas as pd
import pytest

from food_security.food_production import FoodProduction


def test_FoodProduction_add_lifestock(grid_file, regions):
    test_cfg = {"food_production": {"lifestock": {"paths": {"buffalo": grid_file}}}, "main": {"country": "Viet Nam"}}
    food_production = FoodProduction(cfg=test_cfg, region=regions)
    food_production.add_lifestock()
    assert "n_buffalo" in food_production.region.columns
    assert "buffalo_kg" in food_production.region.columns


def test_FoodProduction_add_other_crops(regions, tmp_path):
    df = pd.DataFrame()
    df["Name"] = regions["Name"]
    df["maize"] = np.random.randint(1, 100, size=(len(df["Name"]), 1))
    test_file = tmp_path / "test.csv"
    test_config = {"food_production": {"other_crops": {"paths": {"maize": test_file}}}}
    df.to_csv(test_file, index=False)

    food_production = FoodProduction(cfg=test_config, region=regions)
    food_production.add_other_crops()
    assert "maize" in food_production.region.columns
    assert (
        df[df["Name"] == "An Giang"]["maize"] * 1e6
        == food_production.region[food_production.region["Name"] == "An Giang"]["maize"]
    ).all()


def test_FoodProduction_run(regions, grid_file, mocker):
    food_production = FoodProduction(
        cfg={"main": {"country": "Viet Nam"}, "lifestock": {"paths": {"buffalo": grid_file}}},
        region=regions,
    )
    lifestock_mock_obj = mocker.patch.object(food_production, "add_lifestock")
    rice_yield_mock_obj = mocker.patch.object(food_production, "add_rice_yield")
    other_crops_mock_obj = mocker.patch.object(food_production, "add_other_crops")
    aquaculture_mock_obj = mocker.patch.object(food_production, "add_aquaculture")

    region = food_production.run()
    lifestock_mock_obj.assert_called_once()
    rice_yield_mock_obj.assert_called_once()
    other_crops_mock_obj.assert_called_once()
    aquaculture_mock_obj.assert_called_once()


@pytest.mark.local
def test_FoodProduction_add_lifestock_with_data(regions, example_config):
    food_production = FoodProduction(example_config, region=regions)
    food_production.add_lifestock()
    for animal in example_config["food_production"]["lifestock"]["paths"]:
        assert f"n_{animal}" in food_production.region.columns
        assert f"{animal}_kg" in food_production.region.columns


@pytest.mark.local
def test_FoodProduction_add_other_crops_with_data(regions, example_config):
    food_production = FoodProduction(example_config, region=regions)
    food_production.add_other_crops()
    for crop in example_config["food_production"]["other_crops"]["paths"]:
        assert crop in food_production.region.columns
