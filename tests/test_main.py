#!/usr/bin/env python3
"""Test the main routine."""
import io
import pathlib
import sys
import textwrap
import unittest
from typing import TextIO, cast

import temppathlib

import icontract_lint.main

# pylint: disable=missing-docstring


class TestParseArgs(unittest.TestCase):
    def test_single_path(self):
        args = icontract_lint.main.parse_args(sys_argv=['some-executable.py', '/path/to/some/file.py'])
        self.assertListEqual([pathlib.Path('/path/to/some/file.py')], args.paths)

    def test_multiple_paths(self):
        args = icontract_lint.main.parse_args(
            sys_argv=['some-executable.py', '/path/to/some/file.py', '/path/to/another/file.py'])
        self.assertListEqual([
            pathlib.Path('/path/to/some/file.py'),
            pathlib.Path('/path/to/another/file.py'),
        ], args.paths)

    def test_panic(self):
        args = icontract_lint.main.parse_args(sys_argv=['some-executable.py', '/path/to/some/file.py'])
        self.assertFalse(args.dont_panic)

    def test_dont_panic(self):
        args = icontract_lint.main.parse_args(sys_argv=['some-executable.py', '/path/to/some/file.py', '--dont_panic'])
        self.assertTrue(args.dont_panic)

    def test_format(self):
        args = icontract_lint.main.parse_args(
            sys_argv=['some-executable.py', '/path/to/some/file.py', "--format", "json"])
        self.assertEqual("json", args.format)


class sys_path_with:  # pylint: disable=invalid-name,duplicate-code
    """Add the path to the sys.path in the context."""

    def __init__(self, path: pathlib.Path) -> None:
        """Set property with the given argument."""
        self.path = path

    def __enter__(self):
        """Add the path to the ``sys.path``."""
        sys.path.insert(0, self.path.as_posix())

    def __exit__(self, exc_type, exc_value, traceback):
        """Remove the path from the ``sys.path``."""
        sys.path.remove(self.path.as_posix())


class TestMain(unittest.TestCase):
    # pylint: disable=protected-access
    TEXT = textwrap.dedent("""\
                from icontract import pre

                @pre(lambda x: x > 0)
                def some_func(y: int) -> int:
                    return y
                """)

    def test_json(self):
        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(TestMain.TEXT)

            with sys_path_with(tmp.path):
                buf = io.StringIO()
                stream = cast(TextIO, buf)
                args = icontract_lint.main.parse_args(
                    sys_argv=["some-executable.py", pth.as_posix(), "--format", "json"])

                retcode = icontract_lint.main._main(args=args, stream=stream)

                self.assertEqual(1, retcode)
                self.assertEqual(
                    textwrap.dedent("""\
                [
                  {{
                    "identifier": "pre-invalid-arg",
                    "description": "Condition argument(s) are missing in the function signature: x",
                    "filename": "{pth}",
                    "lineno": 3
                  }}
                ]""".format(pth=pth.as_posix())),
                    buf.getvalue())

    def test_verbose(self):
        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(TestMain.TEXT)

            with sys_path_with(tmp.path):
                buf = io.StringIO()
                stream = cast(TextIO, buf)
                args = icontract_lint.main.parse_args(sys_argv=["some-executable.py", pth.as_posix()])

                retcode = icontract_lint.main._main(args=args, stream=stream)

                self.assertEqual(1, retcode)
                self.assertEqual(
                    ("{pth}:3: Condition argument(s) are missing in "
                     "the function signature: x (pre-invalid-arg)\n").format(pth=pth.as_posix()),
                    buf.getvalue())

    def test_dont_panic(self):
        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(TestMain.TEXT)

            with sys_path_with(tmp.path):
                buf = io.StringIO()
                stream = cast(TextIO, buf)
                args = icontract_lint.main.parse_args(sys_argv=["some-executable.py", pth.as_posix(), "--dont_panic"])

                retcode = icontract_lint.main._main(args=args, stream=stream)

                self.assertEqual(0, retcode)


if __name__ == '__main__':
    unittest.main()
