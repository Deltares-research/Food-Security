import pytest

from food_security.food_supply import FoodSupply


@pytest.mark.local
def test_FoodSupply_with_data(example_config: dict):
    fs = FoodSupply(cfg=example_config)
    fs.get_export()


def test_FoodSupply_get_export(data_dir):
    cfg = {"food_supply": {"import_export_table": {"path": data_dir / "FAOSTAT_data_en_11-18-2024"}}}
    fs = FoodSupply(cfg=cfg)
    fs.get_export()


@pytest.mark.local
def test_FoodSupply_calculate_export_ratio(regions, example_config):
    fs = FoodSupply(cfg=example_config, region=regions)
    food_items = ["chicken", "buffalo", "sugar_cane"]
    export_ratios = fs._calculate_export_ratio(food_items=food_items)
