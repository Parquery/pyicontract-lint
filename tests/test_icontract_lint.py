#!/usr/bin/env python3

# pylint: disable=missing-docstring
import io
import os
import pathlib
import tempfile
import textwrap
import unittest
import unittest.mock
from typing import List, cast, TextIO

import icontract_lint
import tests.common


class TestCheckUnreadableFile(unittest.TestCase):
    def test_read_failure(self) -> None:
        # pylint: disable=no-self-use
        class MockPath:
            def read_text(self) -> str:
                raise Exception("dummy exception")

            def is_file(self) -> bool:
                return True

            def __str__(self) -> str:
                return "some-path"

        pth = cast(pathlib.Path, MockPath())
        errors = icontract_lint.check_file(path=pth)

        self.assertEqual(1, len(errors))
        self.assertDictEqual({
            'identifier': 'unreadable',
            'description': 'dummy exception',
            'filename': str(pth),
        }, errors[0].as_mapping())  # type: ignore

    def test_parse_failure(self) -> None:
        # pylint: disable=no-self-use
        class MockPath:
            def read_text(self) -> str:
                return "dummy content"

            def is_file(self) -> bool:
                return True

            def __str__(self) -> str:
                return "some-path"

        pth = cast(pathlib.Path, MockPath())

        with unittest.mock.patch('astroid.parse') as astroid_parse:

            def blow_up(*args, **kwargs) -> None:
                raise Exception("dummy exception")

            astroid_parse.side_effect = blow_up

            errors = icontract_lint.check_file(path=pth)

            self.assertEqual(1, len(errors))
            self.assertEqual('unreadable', errors[0].identifier.value)
            self.assertTrue(errors[0].description.startswith("Astroid failed to parse the file: dummy exception ("))
            self.assertEqual(str(pth), errors[0].filename)


class TestUninferrableDecorator(unittest.TestCase):
    def test_astroid_name_inference_error(self):
        text = textwrap.dedent("""\
                @some_uninferrable_decorator
                def some_func(x: int) -> int:
                    pass
                """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_astroid_inferrence_error(self):
        # This example was adapted from the issue https://github.com/Parquery/pyicontract-lint/issues/27.
        text = textwrap.dedent("""\
                class RuleTable:
                    @classinstancemethod
                    def insert_rule(cls, index, rule_):
                        pass
        
                    @insert_rule.instancemethod
                    def insert_rule(self, index, rule_):
                        pass
                """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)


class TestCheckFile(unittest.TestCase):
    def test_wo_contracts(self):
        text = textwrap.dedent("""\
                def some_func(x: int) -> int:
                    pass
                    
                class SomeClass:
                    def some_method(self, x: int) -> int:
                        pass
                        
                    @classmethod
                    def some_class_method(self, x: int) -> int:
                        pass
                        
                    @staticmethod
                    def some_static_method(self, x: int) -> int:
                        pass
                """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_linter_disabled(self):
        text = textwrap.dedent("""\
            from icontract import require
            
            # pyicontract-lint: disabled
            
            @require(lambda x: x > 0, enabled=False)
            def some_func(y: int) -> int:
                return y
            """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)

                self.assertListEqual([], errors)

    def test_syntax_error(self):
        text = textwrap.dedent("""\
                from icontract import require

                @require(lambda x:int: x > 3)
                def some_func(x: int) -> int:
                    return x
                """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'invalid-syntax',
                    'description': 'invalid syntax',
                    'filename': str(pth),
                    'lineno': 3
                }, err.as_mapping())


class TestCheckPaths(unittest.TestCase):
    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            errs = icontract_lint.check_paths(paths=[tmp_path])
            self.assertListEqual([], errs)

    def test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            text = textwrap.dedent("""\
                from icontract import require

                @require(lambda x:int: x > 3)
                def some_func(x: int) -> int:
                    return x
                """)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_paths(paths=[pth])
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'invalid-syntax',
                    'description': 'invalid syntax',
                    'filename': str(pth),
                    'lineno': 3
                }, err.as_mapping())

    def test_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            text = textwrap.dedent("""\
                from icontract import require

                @require(lambda x:int: x > 3)
                def some_func(x: int) -> int:
                    return x
                """)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_paths(paths=[tmp_path])
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'invalid-syntax',
                    'description': 'invalid syntax',
                    'filename': str(pth),
                    'lineno': 3
                }, err.as_mapping())


class TestOutputVerbose(unittest.TestCase):
    def test_empty(self):
        buf = io.StringIO()
        stream = cast(TextIO, buf)

        errs = []  # type: List[icontract_lint.Error]
        icontract_lint.output_verbose(errors=errs, stream=stream)

        self.assertEqual('', buf.getvalue())

    def test_errors(self):
        buf = io.StringIO()
        stream = cast(TextIO, buf)

        errs = [
            icontract_lint.Error(
                identifier=icontract_lint.ErrorID.NO_CONDITION,
                description='The contract decorator lacks the condition.',
                filename='/path/to/some/file.py',
                lineno=123)
        ]

        icontract_lint.output_verbose(errors=errs, stream=stream)

        self.assertEqual(
            '/path/to/some/file.py:123: The contract decorator lacks the condition. (no-condition){}'.format(
                os.linesep), buf.getvalue())


class TestOutputJson(unittest.TestCase):
    def test_empty(self):
        buf = io.StringIO()
        stream = cast(TextIO, buf)

        errs = []  # type: List[icontract_lint.Error]
        icontract_lint.output_json(errors=errs, stream=stream)

        self.assertEqual('[]', buf.getvalue())

    def test_errors(self):
        buf = io.StringIO()
        stream = cast(TextIO, buf)

        errs = [
            icontract_lint.Error(
                identifier=icontract_lint.ErrorID.NO_CONDITION,
                description='The contract decorator lacks the condition.',
                filename='/path/to/some/file.py',
                lineno=123)
        ]

        icontract_lint.output_json(errors=errs, stream=stream)

        self.assertEqual(
            textwrap.dedent("""\
                [
                  {
                    "identifier": "no-condition",
                    "description": "The contract decorator lacks the condition.",
                    "filename": "/path/to/some/file.py",
                    "lineno": 123
                  }
                ]"""), buf.getvalue())


if __name__ == '__main__':
    unittest.main()
