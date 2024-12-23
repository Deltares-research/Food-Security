import logging
from pathlib import Path

import geopandas as gpd

from food_security.data_reader import Grid, HisFile, read_and_transform_rice_yield_table


def test_Grid_get_region_stat(regions, grid_file):
    grid = Grid(fp=grid_file)
    region_stats = grid.get_region_stat(
        regions=regions,
        col_name="lifestock",
        stat="sum",
    )
    assert isinstance(region_stats, gpd.GeoDataFrame)
    assert "lifestock" in region_stats.columns


def test_Grid_get_region_stats(regions, grid_file):
    grid = Grid(fp=grid_file)
    region_stats = grid.get_region_stats(regions=regions, cols={"lifestock_sum": "sum", "lifestock_mean": "mean"})
    assert isinstance(region_stats, gpd.GeoDataFrame)
    assert "lifestock_sum" in region_stats.columns
    assert "lifestock_mean" in region_stats.columns


def test_read_and_transform_rice_yield_data(rice_yield_data, caplog):
    df = read_and_transform_rice_yield_table(rice_yield_data, year=2014)
    assert "Can Tho" in df.Name.to_numpy()
    assert "Hau Giang" in df.Name.to_numpy()
    caplog.set_level(logging.WARNING)
    df = read_and_transform_rice_yield_table(rice_yield_data, year=2020)
    assert "No rice data found for year 2020" in caplog.text
    assert df is None


def test_HisFile_read(his_file):
    his_reader = HisFile(his_file)
    his_reader.read()
    assert "Actual farm gate pr_2" in his_reader.ds.data_vars
    assert len(his_reader.ds.data_vars) == 23


def test_HisFile_to_table(his_file: Path):
    his_reader = HisFile(his_file)
    his_reader.read()
    df = his_reader.to_table(year=2014)
    assert len(df) == 12
