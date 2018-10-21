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
