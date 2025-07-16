"""Script for demoing FoodSecurity class."""

from pathlib import Path

from food_security import FoodSecurity

if __name__ == "__main__":
    root = Path(__file__).parent.parent
    config_path = root / "tests/test_data/test_food_security.toml"
    output_path = root / "scripts/results/output.gpkg"
    fs = FoodSecurity(cfg_path=config_path, root=root, output_path=output_path)
    fs.run()
