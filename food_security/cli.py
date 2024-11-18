"""A lightweight CLI for the food security module."""
import argparse
import logging
from pathlib import Path

from food_security.main import FoodSecurity

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("path", help="Path to config file")

if __name__ == "__main__":
    args = parser.parse_args()
    config_file = Path(args[0])
    if not config_file.exists():
        err_msg = "Config file not found"
        raise FileNotFoundError(err_msg)
    if config_file.suffix != ".toml":
        err_msg = f"Expected a TOML file configuration, but got {config_file}"
        raise ValueError(err_msg)

    fs = FoodSecurity(cfg_path=config_file)
    fs.run()

