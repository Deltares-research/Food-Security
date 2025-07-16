from pathlib import Path

import geopandas as gpd

from food_security.main import FoodSecurity


def test_food_security(config_toml_file, tmp_path):
    tmp_path = tmp_path / "results.gpkg"
    root = Path(__file__).parent.parent
    fs = FoodSecurity(cfg_path=config_toml_file, output_path=tmp_path, root=root)
    fs.run()
    gdf = gpd.read_file(tmp_path)
    assert len(gdf.columns) == 77

