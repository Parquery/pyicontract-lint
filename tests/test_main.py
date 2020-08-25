#!/usr/bin/env python3
"""Test the main routine."""
import io
import os
import pathlib
import sys
import tempfile
import textwrap
import unittest
from typing import TextIO, cast

import icontract_lint.main

# pylint: disable=missing-docstring
import pyicontract_lint_meta


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
        sys.path.insert(0, str(self.path))

    def __exit__(self, exc_type, exc_value, traceback):
        """Remove the path from the ``sys.path``."""
        sys.path.remove(str(self.path))


class TestMain(unittest.TestCase):
    # pylint: disable=protected-access
    TEXT = textwrap.dedent("""\
                from icontract import require

                @require(lambda x: x > 0)
                def some_func(y: int) -> int:
                    return y
                """)

    def test_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some_module.py"
            pth.write_text(TestMain.TEXT)

            with sys_path_with(tmp_path):
                buf = io.StringIO()
                stream = cast(TextIO, buf)
                args = icontract_lint.main.parse_args(sys_argv=["some-executable.py", str(pth), "--format", "json"])

                retcode = icontract_lint.main._main(args=args, stream=stream)

                self.assertEqual(1, retcode)
                self.assertEqual(
                    textwrap.dedent("""\
                [
                  {{
                    "identifier": "pre-invalid-arg",
                    "description": "Precondition argument(s) are missing in the function signature: x",
                    "filename": "{pth}",
                    "lineno": 3
                  }}
                ]""".format(pth=str(pth).replace("\\", "\\\\"))),
                    buf.getvalue())

    def test_verbose_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some-executable.py"
            pth.write_text('"""all ok"""')

            buf = io.StringIO()
            stream = cast(TextIO, buf)
            args = icontract_lint.main.parse_args(sys_argv=[str(pth)])
            retcode = icontract_lint.main._main(args=args, stream=stream)

            self.assertEqual(0, retcode)
            self.assertEqual(("No errors detected.{}").format(os.linesep), buf.getvalue())

    def test_verbose(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some_module.py"
            pth.write_text(TestMain.TEXT)

            with sys_path_with(tmp_path):
                buf = io.StringIO()
                stream = cast(TextIO, buf)
                args = icontract_lint.main.parse_args(sys_argv=["some-executable.py", str(pth)])

                retcode = icontract_lint.main._main(args=args, stream=stream)

                self.assertEqual(1, retcode)
                self.assertEqual(("{}:3: Precondition argument(s) are missing in "
                                  "the function signature: x (pre-invalid-arg){}").format(str(pth), os.linesep),
                                 buf.getvalue())

    def test_dont_panic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some_module.py"
            pth.write_text(TestMain.TEXT)

            with sys_path_with(tmp_path):
                buf = io.StringIO()
                stream = cast(TextIO, buf)
                args = icontract_lint.main.parse_args(sys_argv=["some-executable.py", str(pth), "--dont_panic"])

                retcode = icontract_lint.main._main(args=args, stream=stream)

                self.assertEqual(0, retcode)

    def test_version(self):
        buf = io.StringIO()
        stream = cast(TextIO, buf)
        args = icontract_lint.main.parse_args(sys_argv=["some-executable.py", "--version"])

        retcode = icontract_lint.main._main(args=args, stream=stream)
        self.assertEqual(0, retcode)
        self.assertEqual('{}{}'.format(pyicontract_lint_meta.__version__, os.linesep), buf.getvalue())


if __name__ == '__main__':
    unittest.main()
