"""Lint contracts defined with icontract library."""
import collections
import enum
import json
import pathlib
import re
from typing import Set, List, Mapping, Optional, TextIO, Any

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


class ErrorID(enum.Enum):
    """Enumerate error identifiers."""

    PRE_INVALID_ARG = "pre-invalid-arg"
    SNAPSHOT_INVALID_ARG = "snapshot-invalid-arg"
    SNAPSHOT_WO_CAPTURE = "snapshot-wo-capture"
    SNAPSHOT_WO_POST = "snapshot-wo-post"
    POST_INVALID_ARG = "post-invalid-arg"
    POST_RESULT_NONE = "post-result-none"
    POST_RESULT_CONFLICT = "post-result-conflict"
    POST_OLD_CONFLICT = "post-old-conflict"
    INV_INVALID_ARG = "inv-invalid-arg"
    NO_CONDITION = 'no-condition'
    INVALID_SYNTAX = 'invalid-syntax'


@icontract.inv(lambda self: len(self.description) > 0)
@icontract.inv(lambda self: len(self.filename) > 0)
@icontract.inv(lambda self: self.lineno >= 1)
class Error:
    """
    Represent a linter error.

    :ivar identifier: identifier of the error
    :vartype identifier: ErrorID

    :ivar description:
        verbose description of the error including details about the cause (*e.g.*, the name of the invalid argument)
    :vartype description: str

    :ivar filename: file name of the linted module
    :vartype filename: str

    :ivar lineno: line number of the offending decorator
    :vartype lineno: int

    """

    @icontract.pre(lambda description: len(description) > 0)
    @icontract.pre(lambda filename: len(filename) > 0)
    @icontract.pre(lambda lineno: lineno >= 1)
    def __init__(self, identifier: ErrorID, description: str, filename: str, lineno: int) -> None:
        """Initialize with the given properties."""
        self.identifier = identifier
        self.description = description
        self.filename = filename
        self.lineno = lineno

    def as_mapping(self) -> Mapping[str, Any]:
        """Transform the error to a mapping that can be converted to JSON and similar formats."""
        return collections.OrderedDict([("identifier", self.identifier.value), ("description", str(self.description)),
                                        ("filename", self.filename), ("lineno", self.lineno)])


class _AstroidVisitor:
    """
    Abstract astroid node visitor.

    If the visit function has not been defined, ``visit_generic`` is invoked.
    """

    assert "generic" not in [cls.__class__.__name__ for cls in astroid.ALL_NODE_CLASSES]

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

    @icontract.pre(lambda lineno: lineno >= 1)
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

    @icontract.pre(lambda lineno: lineno >= 1)
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

    @icontract.pre(lambda pytype: pytype in ['icontract.pre', 'icontract.post'])
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
        if pytype == 'icontract.pre':
            self._verify_pre(func_arg_set=func_arg_set, condition_arg_set=condition_arg_set, lineno=node.lineno)

        elif pytype == 'icontract.post':
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
        if node.args:
            capture_node = node.args[0]
        elif node.keywords:
            for keyword_node in node.keywords:
                if keyword_node.arg == "capture":
                    capture_node = keyword_node.value
        else:
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

        capture_args = capture.argnames()

        if len(capture_args) > 1:
            self.errors.append(
                Error(
                    identifier=ErrorID.SNAPSHOT_INVALID_ARG,
                    description="Snapshot capture function expects at most one argument, but got: {}".format(
                        capture_args),
                    filename=self._filename,
                    lineno=node.lineno))
            return

        if len(capture_args) == 1 and capture_args[0] not in func_arg_set:
            self.errors.append(
                Error(
                    identifier=ErrorID.SNAPSHOT_INVALID_ARG,
                    description="Snapshot argument is missing in the function signature: {}".format(capture_args[0]),
                    filename=self._filename,
                    lineno=node.lineno))
            return

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
        if pytype not in ["icontract.pre", "icontract.snapshot", "icontract.post"]:
            return

        if pytype in ['icontract.pre', 'icontract.post']:
            self._verify_precondition_or_postcondition_decorator(
                node=node, pytype=pytype, func_arg_set=func_arg_set, func_has_result=func_has_result)

        elif pytype == 'icontract.snapshot':
            self._verify_snapshot_decorator(node=node, func_arg_set=func_arg_set)

    def _infer_decorator(self, node: astroid.nodes.Call) -> Optional[astroid.bases.Instance]:
        """
        Try to infer the decorator as instance of a class.

        :param node: decorator AST node
        :return: instance of the decorator or None if decorator instance could not be inferred
        """
        # While this function does not use ``self``, keep it close to the usage to improve the readability.
        # pylint: disable=no-self-use
        try:
            decorator = next(node.infer())
        except astroid.exceptions.NameInferenceError:
            return None

        if decorator is astroid.Uninferable:
            return None

        return decorator

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
        decorators = [self._infer_decorator(node=decorator_node) for decorator_node in node.decorators.nodes]

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

        if 'icontract.snapshot' in pytypes and 'icontract.post' not in pytypes:
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

        if pytype != 'icontract.inv':
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


@icontract.pre(lambda path: path.is_file())
def check_file(path: pathlib.Path) -> List[Error]:
    """
    Parse the given file as Python code and lint its contracts.

    :param path: path to the file
    :return: list of lint errors
    """
    text = path.read_text()

    for line in text.splitlines():
        if _DISABLED_DIRECTIVE_RE.match(line):
            return []

    try:
        modname = ".".join(astroid.modutils.modpath_from_file(filename=path.as_posix()))
    except ImportError:
        modname = '<unknown module>'

    try:
        tree = astroid.parse(code=text, module_name=modname, path=path.as_posix())
    except astroid.exceptions.AstroidSyntaxError as err:
        cause = err.__cause__
        assert isinstance(cause, SyntaxError)

        return [
            Error(
                identifier=ErrorID.INVALID_SYNTAX,
                description=cause.msg,  # pylint: disable=no-member
                filename=path.as_posix(),
                lineno=cause.lineno)  # pylint: disable=no-member
        ]

    lint_visitor = _LintVisitor(filename=path.as_posix())
    lint_visitor.visit(node=tree)

    return lint_visitor.errors


@icontract.pre(lambda path: path.is_dir())
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


@icontract.post(lambda paths, result: len(paths) > 0 or len(result) == 0, "no paths implies no errors")
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
        stream.write("{}:{}: {} ({})\n".format(err.filename, err.lineno, err.description, err.identifier.value))


def output_json(errors: List[Error], stream: TextIO) -> None:
    """
    Output errors in a JSON format to the ``stream``.

    :param errors: list of lint errors
    :param stream: output stream
    :return:
    """
    json.dump(obj=[err.as_mapping() for err in errors], fp=stream, indent=2)
