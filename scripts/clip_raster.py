import rasterio
from rasterio.mask import mask
import geopandas as gpd
from pathlib import Path

if __name__ == "__main__":
    data_dir = Path(__file__).absolute().parent.parent / "data"
    in_shp = data_dir / "provinces_area.gpkg"
    in_ras = "P:/wflow_global/hydromt/socio_economic/glw/5_Bf_2010_Da.tif"
    out_ras = data_dir / "test_livestock.tif"

    Vector = gpd.read_file(in_shp)

    with rasterio.open(in_ras) as src:
        Vector = Vector.to_crs(src.crs)
        out_image, out_transform = mask(src, Vector.geometry, crop=True)
        out_meta = src.meta.copy()  # copy the metadata of the source DEM

    out_meta.update(
        {
            "driver": "Gtiff",
            "height": out_image.shape[1],  # height starts with shape[1]
            "width": out_image.shape[2],  # width starts with shape[2]
            "transform": out_transform,
        }
    )

    with rasterio.open(out_ras, "w", **out_meta) as dst:
        dst.write(out_image)
