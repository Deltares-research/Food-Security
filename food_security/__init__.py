"""A Python package for calculating a food security index for river delta's."""

from pathlib import Path

from .main import FoodSecurity

__version__ = "0.0.1"

DATA_DIR = Path(__file__).parent.parent / "data"

__all__ = ["FoodSecurity"]
