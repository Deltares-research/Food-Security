"""Module for the ConfigReader class."""
from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path

import tomli

logger = logging.getLogger()


class ConfigReader(dict):
    """Reader class for reading TOML config files."""

    def __init__(self, file: Path | str, root: Path | str | None = None):
        with open(file, "rb") as f:
            dict.__init__(self, tomli.load(f))
        root = root if root else self["main"].get("root", None)
        if root:
            ConfigReader._make_paths_absolute(self, root)
        self._validate_paths()

    def _validate_paths(self):
        flattened_dict = ConfigReader.flatten_dict(self)

        # Check paths in config
        for k in flattened_dict:
            if (
                k.endswith(".path")
                and k != "output.path"
                and not Path(flattened_dict[k]).exists()
            ):
                log_msg = f"config input {k} contains a non-existing path"
                logger.warning(log_msg)

    @staticmethod
    def _flatten_dict_gen(d, parent_key, sep):
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, MutableMapping):
                yield from ConfigReader.flatten_dict(v, new_key, sep=sep).items()
            else:
                yield new_key, v

    @staticmethod
    def flatten_dict(d: MutableMapping, parent_key: str = "", sep: str = ".") -> dict:
        """Flatten a dictionary."""
        return dict(ConfigReader._flatten_dict_gen(d, parent_key, sep))

    @staticmethod
    def _make_paths_absolute(d: dict, root: str | Path) -> None:
        for key, value in d.items():
            if isinstance(value, dict):
                ConfigReader._make_paths_absolute(value, root)
            elif (
                isinstance(key, str) and key.endswith("path") and isinstance(value, str)
            ):
                d[key] = Path(root) / value
