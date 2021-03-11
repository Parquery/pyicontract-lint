# pylint: disable=missing-docstring
import pathlib
import tempfile
import textwrap
import unittest

import icontract_lint
import tests.common


class TestInvariant(unittest.TestCase):
    def test_valid(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_invalid_arg(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(3, len(errors))

                for err, lineno in zip(errors, [6, 7, 8]):
                    # yapf: disable
                    self.assertDictEqual({
                        'identifier': 'inv-invalid-arg',
                        'description': "An invariant expects one and only argument 'self', "
                                       "but the arguments are: ['selfie']",
                        'filename': str(pth),
                        'lineno': lineno
                    }, err.as_mapping())
                    # yapf: enable

    def test_no_condition(self):
        text = textwrap.dedent("""\
            from icontract import invariant

            @invariant(description='hello')
            class SomeClass:
                def __init__(self) -> None:
                    self.x = 22
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
                    'identifier': 'no-condition',
                    'description': 'The contract decorator lacks the condition.',
                    'filename': str(pth),
                    'lineno': 3
                }, err.as_mapping())


if __name__ == '__main__':
    unittest.main()
