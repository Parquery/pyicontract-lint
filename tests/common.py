"""Provide common functionality for the tests."""
import pathlib
import sys


class sys_path_with:  # pylint: disable=invalid-name
    """Add the path to the sys.path in the context."""

    def __init__(self, path: pathlib.Path) -> None:
        """Set property with the given argument."""
        self.path = path

    def __enter__(self):
        """Add the path to the ``sys.path``."""
        sys.path.insert(0, str(self.path))

    def __exit__(self, exc_type, exc_value, traceback):
        """Remove the path from the ``sys.path``."""
        sys.path.remove(str(self.path))
