"""Run salinity correction from a TOML config using FAOSTAT credentials in .env."""

import argparse
import sys
from pathlib import Path

import dotenv

from food_security.fao_api import FAOClient
from food_security.salinity_correction import generate_crop_yield_csv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "examples" / "salinity_correction_vietnam_stac.toml"


def main(config_path: Path = DEFAULT_CONFIG) -> None:
    env = dotenv.dotenv_values(REPO_ROOT / ".env")
    username = env.get("FAOSTAT_USERNAME", "")
    password = env.get("FAOSTAT_PASSWORD", "")

    if not username or not password:
        print(
            "Missing FAOSTAT credentials. Set FAOSTAT_USERNAME and "
            "FAOSTAT_PASSWORD in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    fao_client = FAOClient(username=username, password=password)
    generate_crop_yield_csv(config_path, fao_client=fao_client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run salinity crop-yield correction")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(DEFAULT_CONFIG),
        help=f"Path to TOML config (default: {DEFAULT_CONFIG.name})",
    )
    args = parser.parse_args()
    main(Path(args.config))
