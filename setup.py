"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""
import os
import sys

from setuptools import setup, find_packages

import pyicontract_lint_meta

# pylint: disable=redefined-builtin

here = os.path.abspath(os.path.dirname(__file__))  # pylint: disable=invalid-name

with open(os.path.join(here, 'README.rst'), encoding='utf-8') as fid:
    long_description = fid.read()  # pylint: disable=invalid-name

# yapf: disable
install_requires = [
    'icontract>=2.0.0,<3',
    'astroid>=2.4.2,<3'
]

if sys.version_info < (3, 8):
    # We need to install typing-extensions for TypedDict's, Final's *etc.*
    install_requires.append('typing-extensions')

setup(
    name=pyicontract_lint_meta.__title__,
    version=pyicontract_lint_meta.__version__,
    description=pyicontract_lint_meta.__description__,
    long_description=long_description,
    url=pyicontract_lint_meta.__url__,
    author=pyicontract_lint_meta.__author__,
    author_email=pyicontract_lint_meta.__author_email__,
    classifiers=[
        # yapf: disable
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX'
        # yapf: enable
    ],
    license='License :: OSI Approved :: MIT License',
    keywords='design-by-contract precondition postcondition validation lint',
    packages=find_packages(exclude=['tests']),
    install_requires=install_requires,
    extras_require={
        'dev': [
            # yapf: disable
            'mypy==0.910',
            'pylint==2.9.2',
            'yapf==0.20.2',
            'tox>=3.0.0',
            'pydocstyle>=2.1.1,<3',
            'coverage>=4.5.1,<5'
            # yapf: enable
        ],
    },
    entry_points={"console_scripts": ["pyicontract-lint = icontract_lint.main:main"]},
    py_modules=['icontract_lint', 'pyicontract_lint_meta'],
    include_package_data=True,
    package_data={
        "packagery": ["py.typed"],
        '': ['LICENSE.txt', 'README.rst'],
    })
