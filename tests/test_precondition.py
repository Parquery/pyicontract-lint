# pylint: disable=missing-docstring
import pathlib
import tempfile
import textwrap
import unittest

import icontract_lint
import tests.common


class TestPrecondition(unittest.TestCase):
    def test_valid(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)

                self.assertListEqual([], errors)

    def test_invalid_arg(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(4, len(errors))

                for err, lineno in zip(errors, [6, 7, 8, 13]):
                    self.assertDictEqual(
                        {
                            'identifier': 'pre-invalid-arg',
                            'description': 'Precondition argument(s) are missing in the function signature: x',
                            'filename': str(pth),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_no_condition(self):
        text = textwrap.dedent("""\
            from icontract import require

            @require(description="I am a contract without condition.")
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
