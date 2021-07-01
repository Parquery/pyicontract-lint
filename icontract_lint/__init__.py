"""Lint contracts defined with icontract library."""

# pylint: disable=wrong-import-position
# pylint: disable=no-name-in-module

import collections
import enum
import json
import os
import pathlib
import re
import sys
import traceback
from typing import Set, List, Optional, TextIO, cast, Tuple

if sys.version_info >= (3, 8):
    from typing import Final, TypedDict
else:
    from typing_extensions import Final, TypedDict

import astroid
import astroid.modutils
import astroid.nodes
import astroid.util
import icontract

import pyicontract_lint_meta

__title__ = pyicontract_lint_meta.__title__
__description__ = pyicontract_lint_meta.__description__
__url__ = pyicontract_lint_meta.__url__
__version__ = pyicontract_lint_meta.__version__
__author__ = pyicontract_lint_meta.__author__
__author_email__ = pyicontract_lint_meta.__author_email__
__license__ = pyicontract_lint_meta.__license__
__copyright__ = pyicontract_lint_meta.__copyright__

# noinspection PyBroadException
try:
    _ASTROID_VERSION_TUPLE = tuple(
        int(part) for part in re.split('.', astroid.__version__))  # type: Optional[Tuple[int, ...]]
except Exception:  # pylint: disable=broad-except
    _ASTROID_VERSION_TUPLE = None


class ErrorID(enum.Enum):
    """Enumerate error identifiers."""

    UNREADABLE = "unreadable"
    PRE_INVALID_ARG = "pre-invalid-arg"
    SNAPSHOT_INVALID_ARG = "snapshot-invalid-arg"
    SNAPSHOT_WO_CAPTURE = "snapshot-wo-capture"
    SNAPSHOT_WO_POST = "snapshot-wo-post"
    SNAPSHOT_WO_NAME = "snapshot-wo-name"
    POST_INVALID_ARG = "post-invalid-arg"
    POST_RESULT_NONE = "post-result-none"
    POST_RESULT_CONFLICT = "post-result-conflict"
    POST_OLD_CONFLICT = "post-old-conflict"
    INV_INVALID_ARG = "inv-invalid-arg"
    NO_CONDITION = 'no-condition'
    INVALID_SYNTAX = 'invalid-syntax'


class _ErrorMappingRequired(TypedDict):
    """Represent the required fields of an error given as a mapping."""

    identifier: str  #: identifier of the error
    description: str  #: verbose description of the error
    filename: str  #: file name of the linted module


class ErrorMapping(_ErrorMappingRequired, total=False):
    """Represent an error given as a mapping."""

    lineno: int


@icontract.invariant(lambda self: len(self.description) > 0)
@icontract.invariant(lambda self: len(self.filename) > 0)
@icontract.invariant(lambda self: self.lineno is None or self.lineno >= 1)
class Error:
    """Represent a linter error."""

    # pylint: disable=invalid-name
    identifier: Final[ErrorID]  #: identifier of the error

    #: verbose description of the error including details about the cause (*e.g.*, the name of the invalid argument)
    description: str

    filename: str  #: file name of the linted module
    lineno: Final[Optional[int]]  #: line number of the offending decorator

    # pylint: enable=invalid-name

    @icontract.require(lambda description: len(description) > 0)
    @icontract.require(lambda filename: len(filename) > 0)
    @icontract.require(lambda lineno: lineno is None or lineno >= 1)
    def __init__(self, identifier: ErrorID, description: str, filename: str, lineno: Optional[int]) -> None:
        """Initialize with the given values."""
        self.identifier = identifier
        self.description = description
        self.filename = filename
        self.lineno = lineno

    def as_mapping(self) -> ErrorMapping:
        """Transform the error to a mapping that can be converted to JSON and similar formats."""
        # yapf: disable
        result: ErrorMapping = cast(
            ErrorMapping,
            collections.OrderedDict([
                ('identifier', str(self.identifier.value)),
                ('description', self.description),
                ('filename', self.filename)
            ]))
        # yapf: enable

        if self.lineno is not None:
            result['lineno'] = self.lineno

        return result


class _AstroidVisitor:
    """
    Abstract astroid node visitor.

    If the visit function has not been defined, ``visit_generic`` is invoked.
    """

    if _ASTROID_VERSION_TUPLE is not None and _ASTROID_VERSION_TUPLE < (2, 6, 0):
        _ALL_NODE_CLASSES = [cls.__class__.__name__ for cls in astroid.ALL_NODE_CLASSES]
    else:
        _ALL_NODE_CLASSES = [cls.__class__.__name__ for cls in astroid.nodes.ALL_NODE_CLASSES]

    assert "generic" not in _ALL_NODE_CLASSES, \
        (
            "We need ``generic`` as reserved name for the visitor (``visit_generic``). "
            "However, if there is a class in the astroid with the same name, it would break the visitor. "
            "(The version of astroid is: {}.)".format(astroid.__version__)
        )

    def visit(self, node: astroid.node_classes.NodeNG):
        """Enter the visitor."""
        func_name = "visit_" + node.__class__.__name__
        func = getattr(self, func_name, self.visit_generic)
        return func(node)

    def visit_generic(self, node: astroid.node_classes.NodeNG) -> None:
        """Propagate the visit to the children."""
        for child in node.get_children():
            self.visit(child)


class _LintVisitor(_AstroidVisitor):
    """
    Visit functions and check that the contract decorators are valid.

    :ivar errors: list of encountered errors
    :type errors: List[Error]
    """

    def __init__(self, filename: str) -> None:
        """Initialize."""
        self._filename = filename
        self.errors = []  # type: List[Error]

    @icontract.require(lambda lineno: lineno >= 1)
    def _verify_pre(self, func_arg_set: Set[str], condition_arg_set: Set[str], lineno: int) -> None:
        """
        Verify the precondition.

        :param func_arg_set: arguments of the decorated function
        :param condition_arg_set: arguments of the condition function
        :param lineno: line number of the decorator
        :return:
        """
        diff = sorted(condition_arg_set.difference(func_arg_set))
        if diff:
            self.errors.append(
                Error(
                    identifier=ErrorID.PRE_INVALID_ARG,
                    description="Precondition argument(s) are missing in the function signature: {}".format(
                        ", ".join(sorted(diff))),
                    filename=self._filename,
                    lineno=lineno))

    @icontract.require(lambda lineno: lineno >= 1)
    def _verify_post(self, func_arg_set: Set[str], func_has_result: bool, condition_arg_set: Set[str],
                     lineno: int) -> None:
        """
        Verify the postcondition.

        :param func_arg_set: arguments of the decorated function
        :param func_has_result: False if the function's result is annotated as None
        :param condition_arg_set: arguments of the condition function
        :param lineno: line number of the decorator
        :return:
        """
        if "result" in func_arg_set and "result" in condition_arg_set:
            self.errors.append(
                Error(
                    identifier=ErrorID.POST_RESULT_CONFLICT,
                    description="Function argument 'result' conflicts with the postcondition.",
                    filename=self._filename,
                    lineno=lineno))

        if 'result' in condition_arg_set and not func_has_result:
            self.errors.append(
                Error(
                    identifier=ErrorID.POST_RESULT_NONE,
                    description="Function is annotated to return None, but postcondition expects a result.",
                    filename=self._filename,
                    lineno=lineno))

        if 'OLD' in func_arg_set and 'OLD' in condition_arg_set:
            self.errors.append(
                Error(
                    identifier=ErrorID.POST_OLD_CONFLICT,
                    description="Function argument 'OLD' conflicts with the postcondition.",
                    filename=self._filename,
                    lineno=lineno))

        diff = condition_arg_set.difference(func_arg_set)

        # Allow 'result' and 'OLD' to be defined in the postcondition, but not in the function.
        # All other arguments must match between the postcondition and the function.
        if 'result' in diff:
            diff.remove('result')

        if 'OLD' in diff:
            diff.remove('OLD')

        if diff:
            self.errors.append(
                Error(
                    identifier=ErrorID.POST_INVALID_ARG,
                    description="Postcondition argument(s) are missing in the function signature: {}".format(
                        ", ".join(sorted(diff))),
                    filename=self._filename,
                    lineno=lineno))

    def _find_condition_node(self, node: astroid.nodes.Call) -> Optional[astroid.node_classes.NodeNG]:
        """Inspect the decorator call and search for the 'condition' argument."""
        # pylint: disable=no-self-use
        condition_node = None  # type: Optional[astroid.node_classes.NodeNG]
        if node.args:
            condition_node = node.args[0]
        elif node.keywords:
            for keyword_node in node.keywords:
                if keyword_node.arg == "condition":
                    condition_node = keyword_node.value
        else:
            pass

        return condition_node

    @icontract.require(lambda pytype: pytype in ['icontract._decorators.require', 'icontract._decorators.ensure'])
    def _verify_precondition_or_postcondition_decorator(self, node: astroid.nodes.Call, pytype: str,
                                                        func_arg_set: Set[str], func_has_result: bool) -> None:
        """
        Verify a precondition or a postcondition decorator.

        :param node: the decorator node
        :param pytype: inferred type of the decorator
        :param func_arg_set: arguments of the wrapped function
        :param func_has_result: False if the function's result is annotated as None
        """
        condition_node = self._find_condition_node(node=node)

        if condition_node is None:
            self.errors.append(
                Error(
                    identifier=ErrorID.NO_CONDITION,
                    description="The contract decorator lacks the condition.",
                    filename=self._filename,
                    lineno=node.lineno))
            return

        # Infer the condition so as to resolve functions by name etc.
        try:
            condition = next(condition_node.infer())
        except astroid.exceptions.NameInferenceError:
            # Ignore uninferrable conditions
            return

        assert isinstance(condition, (astroid.nodes.Lambda, astroid.nodes.FunctionDef)), \
            "Expected the inferred condition to be either a lambda or a function definition, but got: {}".format(
                condition)

        condition_arg_set = set(condition.argnames())

        # Verify
        if pytype == 'icontract._decorators.require':
            self._verify_pre(func_arg_set=func_arg_set, condition_arg_set=condition_arg_set, lineno=node.lineno)

        elif pytype == 'icontract._decorators.ensure':
            self._verify_post(
                func_arg_set=func_arg_set,
                func_has_result=func_has_result,
                condition_arg_set=condition_arg_set,
                lineno=node.lineno)
        else:
            raise NotImplementedError("Unhandled pytype: {}".format(pytype))

    def _verify_snapshot_decorator(self, node: astroid.nodes.Call, func_arg_set: Set[str]):
        """
        Verify a snapshot decorator.

        :param node: the decorator node
        :param pytype: inferred type of the decorator
        :param func_arg_set: arguments of the wrapped function
        """
        # Find the ``capture=...`` node
        capture_node = None  # type: Optional[astroid.node_classes.NodeNG]
        name_node = None  # type: Optional[astroid.node_classes.NodeNG]

        if node.args:
            if len(node.args) >= 1:
                capture_node = node.args[0]

            if len(node.args) >= 2:
                name_node = node.args[1]

        if node.keywords:
            for keyword_node in node.keywords:
                if keyword_node.arg == "capture":
                    capture_node = keyword_node.value

                if keyword_node.arg == "name":
                    name_node = keyword_node.value

        if capture_node is None:
            self.errors.append(
                Error(
                    identifier=ErrorID.SNAPSHOT_WO_CAPTURE,
                    description="The snapshot decorator lacks the capture function.",
                    filename=self._filename,
                    lineno=node.lineno))
            return

        # Infer the capture so as to resolve functions by name etc.
        assert capture_node is not None, "Expected capture_node to be set in the preceding execution paths."
        try:
            capture = next(capture_node.infer())
        except astroid.exceptions.NameInferenceError:
            # Ignore uninferrable captures
            return

        assert isinstance(capture, (astroid.nodes.Lambda, astroid.nodes.FunctionDef)), \
            "Expected the inferred capture to be either a lambda or a function definition, but got: {}".format(
                capture)

        capture_arg_set = set(capture.argnames())

        diff = capture_arg_set.difference(func_arg_set)

        if diff:
            self.errors.append(
                Error(
                    identifier=ErrorID.SNAPSHOT_INVALID_ARG,
                    description="Snapshot argument(s) are missing in the function signature: {}".format(
                        ", ".join(sorted(diff))),
                    filename=self._filename,
                    lineno=node.lineno))

        if len(capture_arg_set) > 1 and name_node is None:
            self.errors.append(
                Error(
                    identifier=ErrorID.SNAPSHOT_WO_NAME,
                    description="Snapshot involves multiple arguments, but its name has not been specified.",
                    filename=self._filename,
                    lineno=node.lineno))

    def _check_func_decorator(self, node: astroid.nodes.Call, decorator: astroid.bases.Instance, func_arg_set: Set[str],
                              func_has_result: bool) -> None:
        """
        Verify the function decorator.

        :param node: the decorator node
        :param decorator: inferred decorator instance
        :param func_arg_set: arguments of the wrapped function
        :param func_has_result: False if the function's result is annotated as None
        """
        pytype = decorator.pytype()

        # Ignore non-icontract decorators
        if pytype not in [
                "icontract._decorators.require", "icontract._decorators.snapshot", "icontract._decorators.ensure"
        ]:
            return

        if pytype in ['icontract._decorators.require', 'icontract._decorators.ensure']:
            self._verify_precondition_or_postcondition_decorator(
                node=node, pytype=pytype, func_arg_set=func_arg_set, func_has_result=func_has_result)

        elif pytype == 'icontract._decorators.snapshot':
            self._verify_snapshot_decorator(node=node, func_arg_set=func_arg_set)

        else:
            raise NotImplementedError("Unhandled pytype: {}".format(pytype))

    def visit_FunctionDef(self, node: astroid.nodes.FunctionDef) -> None:  # pylint: disable=invalid-name
        """Lint the function definition."""
        if node.decorators is None:
            return

        func_arg_set = set(node.argnames())

        # Infer optimistically that the function has a result. False only if the result is explicitly
        # annotated with None.
        func_has_result = True

        if node.returns is not None:
            try:
                inferred_returns = next(node.returns.infer())

                if isinstance(inferred_returns, astroid.nodes.Const):
                    if inferred_returns.value is None:
                        func_has_result = False

            except astroid.exceptions.NameInferenceError:
                # Ignore uninferrable returns
                pass

        # Infer the decorator instances

        def infer_decorator(a_node: astroid.nodes.Call) -> Optional[astroid.bases.Instance]:
            """
            Try to infer the decorator as instance of a class.

            :param a_node: decorator AST node
            :return: instance of the decorator or None if decorator instance could not be inferred
            """
            try:
                decorator = next(a_node.infer())
            except (astroid.exceptions.NameInferenceError, astroid.exceptions.InferenceError):
                return None

            if decorator is astroid.Uninferable:
                return None

            return decorator

        decorators = [infer_decorator(a_node=decorator_node) for decorator_node in node.decorators.nodes]

        # Check the decorators individually
        for decorator, decorator_node in zip(decorators, node.decorators.nodes):
            # Skip uninferrable decorators
            if decorator is None:
                continue

            self._check_func_decorator(
                node=decorator_node, decorator=decorator, func_arg_set=func_arg_set, func_has_result=func_has_result)

        # Check that at least one postcondition comes after a snapshot
        pytypes = [decorator.pytype() for decorator in decorators if decorator is not None]  # type: List[str]
        assert all(isinstance(pytype, str) for pytype in pytypes)

        if 'icontract._decorators.snapshot' in pytypes and 'icontract._decorators.ensure' not in pytypes:
            self.errors.append(
                Error(
                    identifier=ErrorID.SNAPSHOT_WO_POST,
                    description="Snapshot defined on a function without a postcondition",
                    filename=self._filename,
                    lineno=node.lineno))

    def _check_class_decorator(self, node: astroid.Call) -> None:
        """
        Verify the class decorator.

        :param node: the decorator node
        :return:
        """
        # Infer the decorator so that we resolve import aliases.
        try:
            decorator = next(node.infer())
        except astroid.exceptions.NameInferenceError:
            # Ignore uninferrable decorators
            return

        # Ignore decorators which could not be inferred.
        if decorator is astroid.Uninferable:
            return

        pytype = decorator.pytype()

        if pytype != 'icontract._decorators.invariant':
            return

        condition_node = self._find_condition_node(node=node)

        if condition_node is None:
            self.errors.append(
                Error(
                    identifier=ErrorID.NO_CONDITION,
                    description="The contract decorator lacks the condition.",
                    filename=self._filename,
                    lineno=node.lineno))
            return

        # Infer the condition so as to resolve functions by name etc.
        try:
            condition = next(condition_node.infer())
        except astroid.exceptions.NameInferenceError:
            # Ignore uninferrable conditions
            return

        assert isinstance(condition, (astroid.nodes.Lambda, astroid.nodes.FunctionDef)), \
            "Expected the inferred condition to be either a lambda or a function definition, but got: {}".format(
                condition)

        condition_args = condition.argnames()
        if condition_args != ['self']:
            self.errors.append(
                Error(
                    identifier=ErrorID.INV_INVALID_ARG,
                    description="An invariant expects one and only argument 'self', but the arguments are: {}".format(
                        condition_args),
                    filename=self._filename,
                    lineno=node.lineno))

    def visit_ClassDef(self, node: astroid.nodes.ClassDef) -> None:  # pylint: disable=invalid-name
        """Lint the class definition."""
        if node.decorators is not None:
            # Check the decorators
            for decorator_node in node.decorators.nodes:
                self._check_class_decorator(node=decorator_node)

        for child in node.body:
            self.visit(child)


_DISABLED_DIRECTIVE_RE = re.compile(r'^\s*#\s*pyicontract-lint\s*:\s*disabled\s*$')


@icontract.require(lambda path: path.is_file())
def check_file(path: pathlib.Path) -> List[Error]:
    """
    Parse the given file as Python code and lint its contracts.

    :param path: path to the file
    :return: list of lint errors
    """
    try:
        text = path.read_text()
    except Exception as err:  # pylint: disable=broad-except
        return [Error(identifier=ErrorID.UNREADABLE, description=str(err), filename=str(path), lineno=None)]

    for line in text.splitlines():
        if _DISABLED_DIRECTIVE_RE.match(line):
            return []

    try:
        modname = ".".join(astroid.modutils.modpath_from_file(filename=str(path)))
    except ImportError:
        modname = '<unknown module>'

    try:
        tree = astroid.parse(code=text, module_name=modname, path=str(path))
    except astroid.exceptions.AstroidSyntaxError as err:
        cause = err.__cause__
        assert isinstance(cause, SyntaxError)

        return [
            Error(
                identifier=ErrorID.INVALID_SYNTAX,
                description=cause.msg,  # pylint: disable=no-member
                filename=str(path),
                lineno=cause.lineno)  # pylint: disable=no-member
        ]
    except Exception as err:  # pylint: disable=broad-except
        stack_summary = traceback.extract_tb(sys.exc_info()[2])
        if len(stack_summary) == 0:
            raise AssertionError("Expected at least one element in the traceback") from err

        last_frame = stack_summary[-1]  # type: traceback.FrameSummary

        return [
            Error(
                identifier=ErrorID.UNREADABLE,
                description="Astroid failed to parse the file: {} ({} at line {} in {})".format(
                    err, last_frame.filename, last_frame.lineno, last_frame.name),
                filename=str(path),
                lineno=None)
        ]

    lint_visitor = _LintVisitor(filename=str(path))
    lint_visitor.visit(node=tree)

    return lint_visitor.errors


@icontract.require(lambda path: path.is_dir())
def check_recursively(path: pathlib.Path) -> List[Error]:
    """
    Lint all ``*.py`` files beneath the directory (including subdirectories).

    :param path: path to the directory.
    :return: list of lint errors
    """
    errs = []  # type: List[Error]
    for pth in sorted(path.glob("**/*.py")):
        errs.extend(check_file(pth))

    return errs


@icontract.ensure(lambda paths, result: len(paths) > 0 or len(result) == 0, "no paths implies no errors")
def check_paths(paths: List[pathlib.Path]) -> List[Error]:
    """
    Lint the given paths.

    The directories are recursively linted for ``*.py`` files.

    :param paths: paths to lint
    :return: list of lint errors
    """
    errs = []  # type: List[Error]
    for pth in paths:
        if pth.is_file():
            errs.extend(check_file(path=pth))
        elif pth.is_dir():
            errs.extend(check_recursively(path=pth))
        else:
            raise ValueError("Not a file nore a directory: {}".format(pth))

    return errs


def output_verbose(errors: List[Error], stream: TextIO) -> None:
    """
    Output errors in a verbose, human-readable format to the ``stream``.

    :param errors: list of lint errors
    :param stream: output stream
    :return:
    """
    for err in errors:
        if err.lineno is not None:
            stream.write("{}:{}: {} ({}){}".format(err.filename, err.lineno, err.description, err.identifier.value,
                                                   os.linesep))
        else:
            stream.write("{}: {} ({}){}".format(err.filename, err.description, err.identifier.value, os.linesep))


def output_json(errors: List[Error], stream: TextIO) -> None:
    """
    Output errors in a JSON format to the ``stream``.

    :param errors: list of lint errors
    :param stream: output stream
    :return:
    """
    json.dump(obj=[err.as_mapping() for err in errors], fp=stream, indent=2)
