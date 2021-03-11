# pylint: disable=missing-docstring
import pathlib
import tempfile
import textwrap
import unittest

import icontract_lint
import tests.common


class TestSnapshot(unittest.TestCase):
    def test_valid(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertListEqual([], errors)

    def test_invalid_arg(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(2, len(errors))

                for err, lineno in zip(errors, [7, 8]):
                    self.assertDictEqual(
                        {
                            'identifier': 'snapshot-invalid-arg',
                            'description': 'Snapshot argument is missing in the function signature: another_lst',
                            'filename': str(pth),
                            'lineno': lineno
                        }, err.as_mapping())

    def test_without_post(self):
        text = textwrap.dedent("""\
            from typing import List
            from icontract import ensure, snapshot

            @snapshot(lambda lst: lst[:])  # no postcondition defined after the snapshot 
            def some_func(lst: List[int], value: int) -> None:
                lst.append(value)
            """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)
                self.assertEqual(1, len(errors))

                for err, lineno in zip(errors, [4]):
                    self.assertDictEqual({
                        'identifier': 'snapshot-wo-post',
                        'description': 'Snapshot defined on a function without a postcondition',
                        'filename': str(pth),
                        'lineno': lineno
                    }, err.as_mapping())

    def test_without_capture(self) -> None:
        text = textwrap.dedent("""\
            from typing import List
            from icontract import ensure, snapshot

            @snapshot(name="some_value_without_capture")
            @ensure(lambda OLD, lst: OLD.some_value_without_capture + [value] == lst)
            def some_func(lst: List[int], value: int) -> None:
                lst.append(value)
            """)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)

            pth = tmp_path / "some_module.py"
            pth.write_text(text)

            with tests.common.sys_path_with(tmp_path):
                errors = icontract_lint.check_file(path=pth)

                self.assertEqual(1, len(errors))

                self.assertDictEqual({
                    'identifier': 'snapshot-wo-capture',
                    'description': 'The snapshot decorator lacks the capture function.',
                    'filename': str(pth),
                    'lineno': 4
                }, errors[0].as_mapping())  # type: ignore


if __name__ == '__main__':
    unittest.main()
