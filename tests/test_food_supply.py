from food_security.food_supply import FoodSupply
import pytest

@pytest.mark.locak
def test_FoodSupply_with_data(example_config: dict):
    fs = FoodSupply(cfg=example_config)
    fs.get_export()