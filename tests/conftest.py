from pathlib import Path

import geopandas as gpd
import pytest

from food_security.config import ConfigReader

DATA_DIR = Path(__file__).absolute().parent.parent / "data"
TEST_DATA_DIR = Path(__file__).parent / "test_data"

@pytest.fixture
def test_data_dir():
    return TEST_DATA_DIR

@pytest.fixture
def regions():
    return gpd.read_file(DATA_DIR / "provinces_area.gpkg")

@pytest.fixture
def grid_file():
    return TEST_DATA_DIR / "test_lifestock.tif"

@pytest.fixture
def example_config() -> dict:
    cfg_file = Path(__file__).parent.parent /"examples/food_security.toml"
    return ConfigReader(cfg_file)
