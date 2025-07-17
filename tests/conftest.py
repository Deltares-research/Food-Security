from pathlib import Path

import geopandas as gpd
import pytest

from food_security.config import ConfigReader

DATA_DIR = Path(__file__).absolute().parent.parent / "data"
TEST_DATA_DIR = Path(__file__).parent / "test_data"


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture
def test_data_dir() -> Path:
    return TEST_DATA_DIR


@pytest.fixture
def regions(test_data_dir) -> gpd.GeoDataFrame:
    return gpd.read_file(test_data_dir/ "aoi.gpkg")


@pytest.fixture
def his_file() -> Path:
    return TEST_DATA_DIR / "RIB_CULT_prod.his"


@pytest.fixture
def conversion_table(test_data_dir) -> Path:
    return test_data_dir / "conversion_table.csv"


@pytest.fixture
def food_production_data() -> gpd.GeoDataFrame:
    return gpd.read_file(TEST_DATA_DIR / "food_production_results.fgb")


@pytest.fixture
def config_toml_file(test_data_dir) -> Path:
    return test_data_dir / "test_food_security.toml"


@pytest.fixture
def config_dict(config_toml_file) -> dict:
    return ConfigReader(config_toml_file)
