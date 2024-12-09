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
