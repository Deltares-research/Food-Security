"""Calculate the food transfer coefficient and add it to the region."""

import geopandas as gpd
import osmnx as ox

from food_security.interface.base import FSBase


class FoodTransferCoefficient(FSBase):
    """Calculate the food transfer coefficient."""

    def __init__(self, cfg: dict, region: gpd.GeoDataFrame) -> None:
        """Instantiate the FoodTransferCoefficient class."""
        super().__init__(cfg)
        self.region = region

    def add_ftc(self) -> None:
        """Calculate the food transfer coefficient."""
        self.calculate_road_density()

    def get_roads(self) -> gpd.GeoDataFrame:
        """Retrieve road features from OMSnx."""
        # Get road features for total bounds of region
        road_features = ox.features.features_from_bbox(
            bbox=self.region.total_bounds,
            tags={"highway": True},
        )

        # Drop point geometries
        return road_features[road_features.geometry.type == "LineString"]

    def calculate_road_density(self) -> None:
        """Calculate road density and add it to the regions."""
        roads = self.get_roads()
        utm = self.region.estimate_utm_crs()
        self.region["road_length"] = 0
        for region_name in self.region["Name"].to_numpy():
            region_roads = roads.sjoin(self.region[self.region["Name"] == region_name])
            # Clip any road geoms that are sticking outside of the region polygon
            region_roads = gpd.clip(
                region_roads, self.region[self.region["Name"] == region_name],
            )
            region_roads = region_roads.to_crs(utm)
            region_roads["length"] = region_roads.length
            self.region.loc[self.region["Name"] == region_name, "road_length"] = (
                region_roads["length"].sum()
            )
        # Road density is calculated by km of roads diveded by area (km2)
        self.region["road_density"] = (self.region["road_length"] / 1000) / (
            self.region["area"] / 1e6
        )

    def run(self) -> gpd.GeoDataFrame:
        """Run the FoodTransferCoefficient workflow."""
        super().run()
        return self.region
