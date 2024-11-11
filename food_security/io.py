from pathlib import Path
import geopandas as gpd
import rasterio
from rasterstats import zonal_stats


class Grid:
    def __init__(self, fp: Path | str):
        self.dataset = rasterio.open(fp)
        self.affine = self.dataset.transform
        self.data = self.dataset.read(1)

    def get_region_stats(
        self, regions: gpd.GeoDataFrame, col_name: str, stats: list[str]
    ) -> gpd.GeoDataFrame:
        stats = zonal_stats(regions, self.data, affine=self.affine, stats=stats)
        for stat in stats:
            pass
