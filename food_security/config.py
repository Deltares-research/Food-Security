from pathlib import Path
import tomli
from collections.abc import MutableMapping
import logging

logger = logging.getLogger()


class ConfigReader(dict):
    def __init__(self, file: Path | str):
        with open(file, "rb") as f:
            dict.__init__(self, tomli.load(f))

        self._validate_paths()

    def _validate_paths(self):
        flattened_dict = flatten_dict(self)

        # Check paths in config
        for k in flattened_dict:
            if k.endswith(".path") and k != "output.path":
                if not Path(flattened_dict[k]).exists():
                    log_msg = f"config input {k} contains a non-existing path"
                    logger.warning(log_msg)


def _flatten_dict_gen(d, parent_key, sep):
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            yield from flatten_dict(v, new_key, sep=sep).items()
        else:
            yield new_key, v


def flatten_dict(d: MutableMapping, parent_key: str = "", sep: str = "."):
    """Flatten a dictionary.

    Thanks to this post:
    (https://www.freecodecamp.org/news/how-to-flatten-a-dictionary-in-python-in-4-different-ways/).
    """
    return dict(_flatten_dict_gen(d, parent_key, sep))
