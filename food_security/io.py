from pathlib import Path
import geopandas as gpd
import rasterio


class GridReader:
    def __init__(self, fp: Path | str):
        self.dataset = rasterio.open(fp)
        self.affine = self.dataset.transform
        self.data = self.dataset.read(1)

    def get_zonal_stat(
        self, regions: gpd.GeoDataFrame, col_name: str, stat: str
    ) -> gpd.GeoDataFrame:
        geometries = regions.geometry
