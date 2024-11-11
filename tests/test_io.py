from pathlib import Path
from food_security.io import Grid
import geopandas as gpd

TEST_DATA_DIR = Path(__file__).absolute().parent.parent / "data"


def test_Grid_get_region_stats():
    regions = gpd.read_file(TEST_DATA_DIR / "provinces_area.gpkg")
    test_grid_file = TEST_DATA_DIR / "test_lifestock.tif"

    grid = Grid(test_grid_file)
    region_stats = grid.get_region_stats(
        regions=regions, col_name="lifestock", stats=["sum"]
    )
