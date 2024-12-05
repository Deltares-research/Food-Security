"""Module for base class for food security classes."""

import geopandas as gpd


class FSBase:
    """Base class for food security classes."""

    def __init__(self, cfg: dict) -> None:
        """Instantiate a FSBase object."""
        self.cfg = cfg

    def run(self) -> gpd.GeoDataFrame:
        """Run the add data methods of a FSbase object."""
        for attr in dir(self):
            if attr.startswith("add"):
                method = getattr(self, attr)
                method()
