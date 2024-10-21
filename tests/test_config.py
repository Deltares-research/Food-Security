from food_security.config import ConfigReader
import logging


def test_config_reader(caplog):
    caplog.set_level(logging.WARNING)
    cfg = ConfigReader(file="examples/food_security.toml")

    assert "config input region.path contains a non-existing path"
