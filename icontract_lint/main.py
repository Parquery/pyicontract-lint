#!/usr/bin/env python3
"""Lint contracts defined with icontract library."""

# This file is necessary so that we can specify the entry point for pex.

import argparse
import pathlib
import sys
from typing import List, Any, TextIO

import icontract_lint
import pyicontract_lint_meta


class Args:
    """Represent parsed command-line arguments."""

    def __init__(self, args: Any) -> None:
        """Initialize with arguments parsed with ``argparse``."""
        assert isinstance(args.paths, list)
        assert all(isinstance(pth, str) for pth in args.paths)

        self.dont_panic = bool(args.dont_panic)
        self.format = str(args.format)
        self.version = bool(args.version)
        self.paths = [pathlib.Path(pth) for pth in args.paths]


def parse_args(sys_argv: List[str]) -> Args:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dont_panic", help="Retrun a zero code even if there were errors.", action='store_true')
    parser.add_argument("--format", help="Specify the output format.", default='verbose', choices=['verbose', 'json'])
    parser.add_argument("--version", help="Display the version and return immediately", action='store_true')
    parser.add_argument("paths", help="Specify paths to check (directories and files).", nargs="*")

    args = parser.parse_args(sys_argv[1:])

    return Args(args=args)


def _main(args: Args, stream: TextIO) -> int:
    """Execute the main routine."""
    if args.version:
        stream.write("{}\n".format(pyicontract_lint_meta.__version__))
        return 0

    errors = icontract_lint.check_paths(paths=args.paths)

    if args.format == 'verbose':
        icontract_lint.output_verbose(errors=errors, stream=stream)
    elif args.format == 'json':
        icontract_lint.output_json(errors=errors, stream=stream)
    else:
        raise NotImplementedError("Unhandled format: {}".format(args.format))

    if not args.dont_panic and errors:
        return 1

    return 0


def main() -> None:
    """Wrap the main routine so that it can be tested."""
    args = parse_args(sys_argv=sys.argv)
    sys.exit(_main(args=args, stream=sys.stdout))
