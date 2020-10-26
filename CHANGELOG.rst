2.1.1
=====
* Started ignoring Astroid inference errors in decorators.

  This is critical so that files can be processed even though Astroid
  fails to correctly infer all the decorators.

2.1.0
=====
* Made handling of paths platform-dependent
* Introduced graceful handling of read and parse failures
* Added output on no errors if verbose

2.0.1
=====
* Replaced scripts with entry points (in order to support Windows)
* Upgraded pylint and mypy to latest versions
  (more issues detected, fixed broken dependencies)
* Added support for Python 3.7 and 3.8

2.0.0
=====
* Updated to icontract 2.0.0

1.2.1
=====
* Updated to icontract 1.7.1 due to refactoring of tight coupling with icontract internals

1.2.0
=====
* Added support for ``icontract.snapshot``'s

1.1.1
=====
* ``ImportError`` is ignored if module of the file could not be figured out (*e.g.* when the ``__init__.py`` is
  missing in the directory which is often the case for the scripts).

1.1.0
=====
* Ignore files with ``# pyicontract-lint=disabled``

1.0.2
=====
* Added ``--version`` command-line argument

1.0.1
=====
* Added building PEX to tox
* Refactored the main routine to a module

1.0.0
=====
* Initial version
