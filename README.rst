pyicontract-lint
================

.. image:: https://github.com/Parquery/pyicontract-lint/actions/workflows/ci.yml/badge.svg
    :target: https://github.com/Parquery/pyicontract-lint/actions/workflows/ci.yml
    :alt: Continuous integration

.. image:: https://coveralls.io/repos/github/Parquery/pyicontract-lint/badge.svg?branch=master
    :target: https://coveralls.io/github/Parquery/pyicontract-lint
    :alt: Test coverage

.. image:: https://readthedocs.org/projects/pyicontract-lint/badge/?version=latest
    :target: https://pyicontract-lint.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation status

.. image:: https://badge.fury.io/py/pyicontract-lint.svg
    :target: https://badge.fury.io/py/pyicontract-lint
    :alt: PyPI - version

.. image:: https://img.shields.io/pypi/pyversions/pyicontract-lint.svg
    :alt: PyPI - Python Version

pyicontract-lint lints contracts in Python code defined with
`icontract library <https://github.com/Parquery/icontract>`_.

The following checks are performed:

+---------------------------------------------------------------------------------------+----------------------+
| Description                                                                           | Identifier           |
+=======================================================================================+======================+
| File should be read and decoded correctly.                                            | unreadable           |
+---------------------------------------------------------------------------------------+----------------------+
| A preconditions expects a subset of function's arguments.                             | pre-invalid-arg      |
+---------------------------------------------------------------------------------------+----------------------+
| A snapshot expects at most an argument element of the function's arguments.           | snapshot-invalid-arg |
+---------------------------------------------------------------------------------------+----------------------+
| If a snapshot is defined on a function, a postcondition must be defined as well.      | snapshot-wo-post     |
+---------------------------------------------------------------------------------------+----------------------+
| A ``capture`` function must be defined in the contract.                               | snapshot-wo-capture  |
+---------------------------------------------------------------------------------------+----------------------+
| A postcondition expects a subset of function's arguments.                             | post-invalid-arg     |
+---------------------------------------------------------------------------------------+----------------------+
| If a function returns None, a postcondition should not expect ``result`` as argument. | post-result-none     |
+---------------------------------------------------------------------------------------+----------------------+
| If a postcondition expects ``result`` argument, the function should not expect it.    | post-result-conflict |
+---------------------------------------------------------------------------------------+----------------------+
| If a postcondition expects ``OLD`` argument, the function should not expect it.       | post-old-conflict    |
+---------------------------------------------------------------------------------------+----------------------+
| An invariant should only expect ``self`` argument.                                    | inv-invalid-arg      |
+---------------------------------------------------------------------------------------+----------------------+
| A ``condition`` must be defined in the contract.                                      | no-condition         |
+---------------------------------------------------------------------------------------+----------------------+
| File must be valid Python code.                                                       | invalid-syntax       |
+---------------------------------------------------------------------------------------+----------------------+

Usage
=====
Pyicontract-lint parses the code and tries to infer the imported modules and functions using
`astroid library <https://github.com/PyCQA/astroid>`_. Hence you need to make sure that imported modules are on your
``PYTHONPATH`` before you invoke pyicontract-lint.

Once you set up the environment, invoke pyicontract-lint with a list of positional arguments as paths:

.. code-block:: bash

    pyicontract-lint \
        /path/to/some/directory/some-file.py \
        /path/to/some/directory/another-file.py

You can also invoke it on directories. Pyicontract-lint will recursively search for ``*.py`` files (including the
subdirectories) and verify the files:

.. code-block:: bash

    pyicontract-lint \
        /path/to/some/directory

By default, pyicontract-lint outputs the errors in a verbose, human-readable format. If you prefer JSON, supply it
``--format`` argument:

.. code-block:: bash

    pyicontract-lint \
        --format json \
        /path/to/some/directory

If one or more checks fail, the return code will be non-zero. You can specify ``--dont_panic`` argument if you want
to have a zero return code even though one or more checks failed:

.. code-block:: bash

    pyicontract-lint \
        --dont_panic \
        /path/to/some/directory

To disable any pyicontract-lint checks on a file, add ``# pyicontract-lint: disabled`` on a separate line to the file.
This is useful when you recursively lint files in a directory and want to exclude certain files.

Module ``icontract_lint``
-------------------------
The API is provided in the ``icontract_lint`` module if you want to use pycontract-lint programmatically.

The main points of entry in ``icontract_line`` module are:

* ``check_file(...)``: lint a single file,
* ``check_recursively(...)``: lint a directory and
* ``check_paths(...)``: lint files and directories.

The output is produced by functions ``output_verbose(...)`` and ``output_json(...)``.

Here is an example code that lints a list of given paths and produces a verbose output:

.. code-block:: python

    import pathlib
    import sys

    import icontract_lint

    errors = icontract_lint.check_paths(paths=[
        pathlib.Path('/some/directory/file.py'),
        pathlib.Path('/yet/yet/another/directory'),
        pathlib.Path('/another/directory/another_file.py'),
        pathlib.Path('/yet/another/directory'),
    ])

    output_verbose(errors=errors, stream=sys.stdout)

The full documentation of the module is available on
`readthedocs <https://pyicontract-lint.readthedocs.io/en/latest/>`_.

Installation
============

* Install pyicontract-lint with pip:

.. code-block:: bash

    pip3 install pyicontract-lint

Development
===========

* Check out the repository.

* In the repository root, create the virtual environment:

.. code-block:: bash

    python3 -m venv venv3

* Activate the virtual environment:

.. code-block:: bash

    source venv3/bin/activate

* Install the development dependencies:

.. code-block:: bash

    pip3 install -e .[dev]

* We use tox for testing and packaging the distribution. Run:

.. code-block:: bash

    tox

* We also provide a set of pre-commit checks that lint and check code for formatting. Run them locally from an activated
  virtual environment with development dependencies:

.. code-block:: bash

    ./precommit.py

* The pre-commit script can also automatically format the code:

.. code-block:: bash

    ./precommit.py  --overwrite

Versioning
==========
We follow `Semantic Versioning <http://semver.org/spec/v1.0.0.html>`_. The version X.Y.Z indicates:

* X is the major version (backward-incompatible),
* Y is the minor version (backward-compatible), and
* Z is the patch version (backward-compatible bug fix).
