import logging

from food_security.config import ConfigReader


def test_config_reader(caplog):
    caplog.set_level(logging.WARNING)
    cfg = ConfigReader(file="examples/food_security.toml")
    assert isinstance(cfg, dict)
