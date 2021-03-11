# pylint: disable=missing-docstring
import pathlib
import tempfile
import textwrap
import unittest

import icontract_lint
import tests.common


class TestPostcondition(unittest.TestCase):
    def test_uninferrable_returns_are_ok(self):
        text = textwrap.dedent("""\
            from icontract import ensure

            @ensure(lambda result: result > 0)
            def some_func(x: int) -> SomeUninferrableClass:
                return x
            """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                self.assertListEqual([], icontract_lint.check_file(path=pth))

    def test_valid(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                self.assertListEqual([], icontract_lint.check_file(path=pth))

    def test_valid_without_returns(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                self.assertListEqual([], icontract_lint.check_file(path=pth))

    def test_result_none(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(3, len(errors))
                for err, lineno in zip(errors, [6, 7, 8]):
                    self.assertDictEqual(
                        {
                            'identifier': 'post-result-none',
                            'description': 'Function is annotated to return None, but postcondition expects a result.',
                            'filename': str(pth),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_invalid_args(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(3, len(errors))

                for err, lineno in zip(errors, [6, 7, 8]):
                    self.assertDictEqual(
                        {
                            'identifier': 'post-invalid-arg',
                            'description': 'Postcondition argument(s) are missing in the function signature: x',
                            'filename': str(pth),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_result_conflict(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(3, len(errors))

                for err, lineno in zip(errors, [6, 7, 8]):
                    self.assertDictEqual({
                        'identifier': 'post-result-conflict',
                        'description': "Function argument 'result' conflicts with the postcondition.",
                        'filename': str(pth),
                        'lineno': lineno
                    }, err.as_mapping())

    def test_old_conflict(self):
        text = textwrap.dedent("""\
            from typing import List

            from icontract import ensure

            @snapshot(lambda lst: lst[:])
            @ensure(lambda OLD, lst, value: OLD.lst + [value] == lst)
            def some_func(lst: List[int], value: int, OLD: int) -> int:  # OLD argument is conflicting
                lst.append(value)
                return value
            """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                for err, lineno in zip(errors, [6]):
                    self.assertDictEqual({
                        'identifier': 'post-old-conflict',
                        'description': "Function argument 'OLD' conflicts with the postcondition.",
                        'filename': str(pth),
                        'lineno': lineno
                    }, err.as_mapping())

    def test_no_condition(self):
        text = textwrap.dedent("""\
            from icontract import ensure

            @ensure(description="I am a contract without condition.")
            def some_func(y: int) -> int:
                return y
            """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(1, len(errors))

                self.assertDictEqual({
                    'identifier': 'no-condition',
                    'description': 'The contract decorator lacks the condition.',
                    'filename': str(pth),
                    'lineno': 3
                }, errors[0].as_mapping())


if __name__ == '__main__':
    unittest.main()
