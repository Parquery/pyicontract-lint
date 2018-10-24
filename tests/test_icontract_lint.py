#!/usr/bin/env python3

# pylint: disable=missing-docstring
import io
import pathlib
import sys
import textwrap
import unittest
from typing import List, cast, TextIO

import temppathlib

import icontract_lint


class sys_path_with:  # pylint: disable=invalid-name
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

        with temppathlib.NamedTemporaryFile() as tmp, sys_path_with(tmp.path.parent):
            tmp.path.write_text(text)
            errors = icontract_lint.check_file(path=tmp.path)

            self.assertListEqual([], errors)

    def test_uninferrable_decorator(self):
        text = textwrap.dedent("""\
                @some_uninferrable_decorator
                def some_func(x: int) -> int:
                    pass
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_missing_condition(self):
        text = textwrap.dedent("""\
                from icontract import require

                @require(description='hello')
                def some_func(x: int) -> int:
                    pass
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(1, len(errors))
                self.assertDictEqual({
                    'identifier': 'no-condition',
                    'description': 'The contract decorator lacks the condition.',
                    'filename': pth.as_posix(),
                    'lineno': 3
                }, errors[0].as_mapping())

    def test_pre_valid(self):
        text = textwrap.dedent("""\
                from icontract import require
                
                def lt_100(x: int) -> bool: 
                    return x < 100
                
                @require(lambda x: x > 0)
                @require(condition=lambda x: x % 2 == 0)
                @require(lt_100)
                def some_func(x: int) -> int:
                    return x
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)

                self.assertListEqual([], errors)

    def test_disabled(self):
        text = textwrap.dedent("""\
                        from icontract import require
                        
                        # pyicontract-lint: disabled
                        
                        @require(lambda x: x > 0)
                        def some_func(y: int) -> int:
                            return y
                        """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)

                self.assertListEqual([], errors)

    def test_pre_invalid_arg(self):
        text = textwrap.dedent("""\
                from icontract import require

                def lt_100(x: int) -> bool: 
                    return x < 100

                @require(lambda x: x > 0)
                @require(condition=lambda x: x % 2 == 0)
                @require(lt_100)
                def some_func(y: int) -> int:
                    return y
                    
                class SomeClass:
                    @require(lambda x: x > 0)
                    def some_method(self, y: int) -> int:
                        return y
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(4, len(errors))

                for err, lineno in zip(errors, [6, 7, 8, 13]):
                    self.assertDictEqual(
                        {
                            'identifier': 'pre-invalid-arg',
                            'description': 'Precondition argument(s) are missing in the function signature: x',
                            'filename': pth.as_posix(),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_snapshot_valid(self):
        text = textwrap.dedent("""\
                from typing import List
                from icontract import ensure, snapshot

                def some_len(lst: List[int]) -> int:
                    return len(lst)

                @snapshot(lambda lst: lst[:])
                @snapshot(capture=some_len, name="len_lst")
                @ensure(lambda OLD, lst: OLD.lst + [value] == lst)
                def some_func(lst: List[int], value: int) -> None:
                    lst.append(value)
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_snapshot_invalid_arg(self):
        text = textwrap.dedent("""\
                        from typing import List
                        from icontract import ensure, snapshot

                        def some_len(another_lst: List[int]) -> int:
                            return len(another_lst)

                        @snapshot(lambda another_lst: another_lst[:])  # inconsistent with some_func
                        @snapshot(some_len)  # inconsistent with some_func
                        @ensure(lambda OLD, lst: OLD.lst + [value] == lst)
                        def some_func(lst: List[int], value: int) -> None:
                            lst.append(value)
                        """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(2, len(errors))

                for err, lineno in zip(errors, [7, 8]):
                    self.assertDictEqual(
                        {
                            'identifier': 'snapshot-invalid-arg',
                            'description': 'Snapshot argument is missing in the function signature: another_lst',
                            'filename': pth.as_posix(),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_snapshot_wo_post(self):
        text = textwrap.dedent("""\
                        from typing import List
                        from icontract import ensure, snapshot

                        @snapshot(lambda lst: lst[:])  # no postcondition defined after the snapshot 
                        def some_func(lst: List[int], value: int) -> None:
                            lst.append(value)
                        """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                for err, lineno in zip(errors, [4]):
                    self.assertDictEqual({
                        'identifier': 'snapshot-wo-post',
                        'description': 'Snapshot defined on a function without a postcondition',
                        'filename': pth.as_posix(),
                        'lineno': lineno
                    }, err.as_mapping())

    def test_uninferrable_returns(self):
        text = textwrap.dedent("""\
                        from icontract import ensure

                        @ensure(lambda result: result > 0)
                        def some_func(x: int) -> SomeUninferrableClass:
                            return x
                        """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                self.assertListEqual([], icontract_lint.check_file(path=pth))

    def test_post_valid(self):
        text = textwrap.dedent("""\
                from icontract import ensure

                def lt_100(result: int) -> bool: 
                    return result < 100

                @ensure(lambda result: result > 0)
                @ensure(condition=lambda result: result % 2 == 0)
                @ensure(lt_100)
                def some_func(x: int) -> int:
                    return x
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                self.assertListEqual([], icontract_lint.check_file(path=pth))

    def test_post_valid_without_returns(self):
        text = textwrap.dedent("""\
                from icontract import ensure

                def lt_100(result: int) -> bool: 
                    return result < 100

                @ensure(lambda result: result > 0)
                @ensure(condition=lambda result: result % 2 == 0)
                @ensure(lt_100)
                def some_func(x: int):
                    return x
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                self.assertListEqual([], icontract_lint.check_file(path=pth))

    def test_post_result_none(self):
        text = textwrap.dedent("""\
                from icontract import ensure

                def lt_100(result: int) -> bool: 
                    return result < 100

                @ensure(lambda result: result > 0)
                @ensure(condition=lambda result: result % 2 == 0)
                @ensure(lt_100)
                def some_func(x: int) -> None:
                    return x
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(3, len(errors))
                for err, lineno in zip(errors, [6, 7, 8]):
                    self.assertDictEqual(
                        {
                            'identifier': 'post-result-none',
                            'description': 'Function is annotated to return None, but postcondition expects a result.',
                            'filename': pth.as_posix(),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_post_invalid_args(self):
        text = textwrap.dedent("""\
                from icontract import ensure

                def some_other_func(x: int, result: int) -> bool: 
                    return result * x < 1000

                @ensure(lambda x, result: result > x)
                @ensure(condition=lambda x, result: result % x == 0)
                @ensure(some_other_func)
                def some_func(y: int) -> int:
                    return y
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(3, len(errors))

                for err, lineno in zip(errors, [6, 7, 8]):
                    self.assertDictEqual(
                        {
                            'identifier': 'post-invalid-arg',
                            'description': 'Postcondition argument(s) are missing in the function signature: x',
                            'filename': pth.as_posix(),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_post_result_conflict(self):
        text = textwrap.dedent("""\
                from icontract import ensure

                def some_other_func(x: int, result: int) -> bool: 
                    return result * x < 1000

                @ensure(lambda x, result: result > x)
                @ensure(condition=lambda x, result: result % x == 0)
                @ensure(some_other_func)
                def some_func(x: int, result: int) -> int:
                    return result
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(3, len(errors))

                for err, lineno in zip(errors, [6, 7, 8]):
                    self.assertDictEqual({
                        'identifier': 'post-result-conflict',
                        'description': "Function argument 'result' conflicts with the postcondition.",
                        'filename': pth.as_posix(),
                        'lineno': lineno
                    }, err.as_mapping())

    def test_post_old_conflict(self):
        text = textwrap.dedent("""\
                from typing import List

                from icontract import ensure

                @snapshot(lambda lst: lst[:])
                @ensure(lambda OLD, lst, value: OLD.lst + [value] == lst)
                def some_func(lst: List[int], value: int, OLD: int) -> int:  # OLD argument is conflicting
                    lst.append(value)
                    return value
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                for err, lineno in zip(errors, [6]):
                    self.assertDictEqual({
                        'identifier': 'post-old-conflict',
                        'description': "Function argument 'OLD' conflicts with the postcondition.",
                        'filename': pth.as_posix(),
                        'lineno': lineno
                    }, err.as_mapping())

    def test_inv_ok(self):
        text = textwrap.dedent("""\
                from icontract import invariant
                
                def lt_100(self) -> bool:
                    return self.x < 100
                
                @invariant(lambda self: self.x > 0)
                @invariant(condition=lambda self: self.x % 2 == 0)
                @invariant(lt_100)
                class SomeClass:
                    def __init__(self) -> None:
                        self.x = 22
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_inv_invalid_arg(self):
        text = textwrap.dedent("""\
                from icontract import invariant

                def lt_100(selfie) -> bool:
                    return selfie.x < 100

                @invariant(lambda selfie: selfie.x > 0)
                @invariant(condition=lambda selfie: selfie.x % 2 == 0)
                @invariant(lt_100)
                class SomeClass:
                    def __init__(self) -> None:
                        self.x = 22
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(3, len(errors))

                for err, lineno in zip(errors, [6, 7, 8]):
                    # yapf: disable
                    self.assertDictEqual({
                        'identifier': 'inv-invalid-arg',
                        'description': "An invariant expects one and only argument 'self', "
                                       "but the arguments are: ['selfie']",
                        'filename': pth.as_posix(),
                        'lineno': lineno
                    }, err.as_mapping())
                    # yapf: enable

    def test_no_condition_in_inv(self):
        text = textwrap.dedent("""\
                from icontract import invariant

                @invariant(description='hello')
                class SomeClass:
                    def __init__(self) -> None:
                        self.x = 22
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'no-condition',
                    'description': 'The contract decorator lacks the condition.',
                    'filename': pth.as_posix(),
                    'lineno': 3
                }, err.as_mapping())

    def test_syntax_error(self):
        text = textwrap.dedent("""\
                from icontract import require

                @require(lambda x:int: x > 3)
                def some_func(x: int) -> int:
                    return x
                """)

        with temppathlib.TemporaryDirectory() as tmp:
            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'invalid-syntax',
                    'description': 'invalid syntax',
                    'filename': pth.as_posix(),
                    'lineno': 3
                }, err.as_mapping())


class TestCheckPaths(unittest.TestCase):
    def test_empty(self):
        with temppathlib.TemporaryDirectory() as tmp:
            errs = icontract_lint.check_paths(paths=[tmp.path])
            self.assertListEqual([], errs)

    def test_file(self):
        with temppathlib.TemporaryDirectory() as tmp:
            text = textwrap.dedent("""\
                from icontract import require

                @require(lambda x:int: x > 3)
                def some_func(x: int) -> int:
                    return x
                """)

            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_paths(paths=[pth])
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'invalid-syntax',
                    'description': 'invalid syntax',
                    'filename': pth.as_posix(),
                    'lineno': 3
                }, err.as_mapping())

    def test_directory(self):
        with temppathlib.TemporaryDirectory() as tmp:
            text = textwrap.dedent("""\
                from icontract import require

                @require(lambda x:int: x > 3)
                def some_func(x: int) -> int:
                    return x
                """)

            pth = tmp.path / "some_module.py"
            pth.write_text(text)

            with sys_path_with(tmp.path):
                errors = icontract_lint.check_paths(paths=[tmp.path])
                self.assertEqual(1, len(errors))

                err = errors[0]

                self.assertDictEqual({
                    'identifier': 'invalid-syntax',
                    'description': 'invalid syntax',
                    'filename': pth.as_posix(),
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

        self.assertEqual('/path/to/some/file.py:123: The contract decorator lacks the condition. (no-condition)\n',
                         buf.getvalue())


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
