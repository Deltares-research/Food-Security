import pytest
from pathlib import Path
from food_security.food_production import FoodProduction
from food_security.config import ConfigReader


def test_FoodProduction_get_lifestock(grid_file, regions):
    test_cfg = {"area": "Viet Nam", "lifestock": {"paths": {"buffalo":grid_file}}}
    food_production = FoodProduction(cfg=test_cfg)
    result = food_production.get_lifestock(region=regions)
    assert "n_buffalo" in result.columns
    assert "buffalo_kg_ha" in result.columns

@pytest.mark.local
def test_FoodProduction_get_lifestock_with_data(regions):
    cfg_file = Path(__file__).parent.parent /"examples/food_security.toml"
    cfg = ConfigReader(cfg_file)
    food_production = FoodProduction(cfg)
    regions = food_production.get_lifestock(region=regions)
    for animal in cfg["food_production"]["lifestock"]["paths"]:
        assert f"n_{animal}" in regions.columns
        assert f"{animal}_kg_ha" in regions.columns


    