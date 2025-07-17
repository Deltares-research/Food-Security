from food_security.components.food_supply import FoodSupply


def test_FoodSupply(food_production_data):
    cfg = {"main": {"country": "Viet Nam", "year": 2016}}
    region = food_production_data.copy(deep=True)
    fs = FoodSupply(year=2016,cfg=cfg, region=food_production_data)
    food_items = fs.get_food_items
    food_cols = [food_item[0] + "_" + food_item[1] for food_item in food_items]
    trade_flux = fs.get_food_trade_fluxes()
    changed_food_cols = trade_flux["Item Code"].to_numpy()
    fs.add_food_supply()
    for food_col in food_cols:
        if any(food_col.endswith(c) for c in changed_food_cols):
            assert not fs.region[food_col].equals(region[food_col])
