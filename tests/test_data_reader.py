from food_security.data_reader import Grid
import geopandas as gpd


def test_Grid_get_region_stat(regions, grid_file):
    grid = Grid(fp=grid_file)
    region_stats = grid.get_region_stat(
        regions=regions, col_name="lifestock", stat="sum"
    )
    assert isinstance(region_stats, gpd.GeoDataFrame)
    assert "lifestock" in region_stats.columns

def test_Grid_get_region_stats(regions, grid_file):
    grid = Grid(fp=grid_file)
    region_stats = grid.get_region_stats(regions=regions, cols={"lifestock_sum": "sum", "lifestock_mean": "mean"})
    assert isinstance(region_stats, gpd.GeoDataFrame)
    assert "lifestock_sum" in region_stats.columns
    assert "lifestock_mean" in region_stats.columns




