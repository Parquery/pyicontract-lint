#!/usr/bin/env python3
"""Run precommit checks on the repository."""
import argparse
import os
import pathlib
import platform
import subprocess
import sys


def main() -> int:
    """"
    Main routine
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--overwrite",
        help="Overwrites the unformatted source files with the well-formatted code in place. "
        "If not set, an exception is raised if any of the files do not conform to the style guide.",
        action='store_true')

    args = parser.parse_args()

    overwrite = bool(args.overwrite)

    repo_root = pathlib.Path(__file__).parent

    print("YAPF'ing...")
    if overwrite:
        subprocess.check_call(
            [
                "yapf", "--in-place", "--style=style.yapf", "--recursive", "tests", "icontract_lint", "setup.py",
                "precommit.py"
            ],
            cwd=str(repo_root))
    else:
        subprocess.check_call(
            [
                "yapf", "--diff", "--style=style.yapf", "--recursive", "tests", "icontract_lint", "setup.py",
                "precommit.py"
            ],
            cwd=str(repo_root))

    print("Mypy'ing...")
    subprocess.check_call(["mypy", "icontract_lint", "tests"], cwd=str(repo_root))

    print("Pylint'ing...")
    subprocess.check_call(["pylint", "--rcfile=pylint.rc", "tests", "icontract_lint"], cwd=str(repo_root))

    print("Pydocstyle'ing...")
    subprocess.check_call(["pydocstyle", "icontract_lint"], cwd=str(repo_root))

    print("Testing...")
    env = os.environ.copy()
    env['ICONTRACT_SLOW'] = 'true'

    # yapf: disable
    subprocess.check_call(
        ["coverage", "run",
         "--source", "icontract_lint",
         "-m", "unittest", "discover", "tests"],
        cwd=str(repo_root),
        env=env)
    # yapf: enable

    subprocess.check_call(["coverage", "report"])

    print("Doctesting...")
    if platform.system() == 'Windows':
        interpreter = 'py'
    else:
        interpreter = 'python3'

    subprocess.check_call([interpreter, "-m", "doctest", "README.rst"], cwd=str(repo_root))
    for pth in (repo_root / "icontract_lint").glob("**/*.py"):
        subprocess.check_call([interpreter, "-m", "doctest", str(pth)], cwd=str(repo_root))

    return 0


if __name__ == "__main__":
    sys.exit(main())
