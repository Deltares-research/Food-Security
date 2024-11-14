from pathlib import Path
from pytest import fixture
import geopandas as gpd


DATA_DIR = Path(__file__).absolute().parent.parent / "data"
TEST_DATA_DIR = Path(__file__).parent / "test_data"

@fixture
def test_data_dir():
    return TEST_DATA_DIR

@fixture
def regions():
    return gpd.read_file(DATA_DIR / "provinces_area.gpkg")

@fixture
def grid_file():
    return TEST_DATA_DIR / "test_lifestock.tif"