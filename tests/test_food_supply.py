import pytest

from food_security.food_supply import FoodSupply


@pytest.mark.local
def test_FoodSupply_with_data(example_config: dict):
    fs = FoodSupply(cfg=example_config)
    fs.get_export()
