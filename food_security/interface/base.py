"""Module for base class for food security classes."""

import geopandas as gpd
from food_security.fao_api import FAOClient


class FSBase:
    """Base class for food security classes."""

    def __init__(
        self,
        year: int,
        cfg: dict,
        region: gpd.GeoDataFrame,
        fao_username: str = None,
        fao_password: str = None,
        fao_token: str = None,
    ) -> None:
        """Instantiate a FSBase object."""
        self.year = year
        self.cfg = cfg
        self.region = region
        self.fao_client = FAOClient(
            username=fao_username, password=fao_password, token=fao_token
        )

    def run(self) -> gpd.GeoDataFrame:
        """Run the add data methods of a FSbase object."""
        for attr in dir(self):
            if attr.startswith("add"):
                method = getattr(self, attr)
                method()
        return self.region
