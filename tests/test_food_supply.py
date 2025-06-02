import pytest

from food_security.food_supply import FoodSupply


def test_FoodSupply(food_production_data):
    cfg = {"main": {"country": "Viet Nam", "year": 2016}}
    fs = FoodSupply(cfg=cfg, region=food_production_data)

    fs.get_food_trade_fluxes()
    assert fs
