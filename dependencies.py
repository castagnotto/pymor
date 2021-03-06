#!/usr/bin/env python3
# This file is part of the pyMOR project (http://www.pymor.org).
# Copyright 2013-2017 pyMOR developers and contributors. All rights reserved.
# License: BSD 2-Clause License (http://opensource.org/licenses/BSD-2-Clause)

_PYSIDE = {'2.7': 'https://pymor.github.io/wheels/PySide-1.2.2-cp27-none-linux_x86_64.whl',
           '3.3': 'https://pymor.github.io/wheels/PySide-1.2.2-cp33-cp33m-linux_x86_64.whl',
           '3.4': 'https://pymor.github.io/wheels/PySide-1.2.4-cp34-cp34m-linux_x86_64.whl'}

def _pyside(rev, marker=True):
    if marker:
        return '{} ; python_version == "{}" and "linux" in sys_platform'.format(_PYSIDE[rev], rev)
    return '{}'.format(_PYSIDE[rev])

_QT_COMMENT = 'solution visualization for builtin discretizations'
_PYTEST = 'pytest>=3.2'
tests_require = [_PYTEST, 'pytest-cov', 'envparse', 'docker']
install_requires = ['cython>=0.20.1', 'numpy>=1.8.1', 'scipy>=0.13.3', 'Sphinx>=1.4.0', 'docopt', 'qtpy>=1.3']
setup_requires = ['pytest-runner>=2.9', 'cython>=0.20.1', 'numpy>=1.8.1']
install_suggests = {'ipython>=3.0': 'an enhanced interactive python shell',
                    'ipyparallel': 'required for pymor.parallel.ipython',
                    'matplotlib': 'needed for error plots in demo scipts',
                    'pyopengl': 'fast solution visualization for builtin discretizations (PySide also required)',
                    'pyamg': 'algebraic multigrid solvers',
                    'mpi4py': 'required for pymor.tools.mpi and pymor.parallel.mpi',
                    'pyevtk>=1.1': 'writing vtk output',
                    _PYTEST: 'testing framework required to execute unit tests',
                    _pyside('3.4'): _QT_COMMENT,
                    _pyside('3.3'): _QT_COMMENT,
                    _pyside('2.7'): _QT_COMMENT,
                    'pyside; python_version < "3.5" and "linux" not in sys_platform': 'solution visualization for builtin discretizations',
                    'PyQt5 ; python_version >= "3.5"': 'solution visualization for builtin discretizations',
                    'pillow': 'image library used for bitmap data functions',
                    'psutil': 'Process management abstractions used for gui'}
doc_requires = ['sphinx>=1.5', 'cython', 'numpy']
travis_requires = ['pytest-cov', 'pytest-xdist', 'check-manifest', 'python-coveralls', 'pytest-travis-fold']
import_names = {'ipython': 'IPython',
                'pytest-cache': 'pytest_cache',
                'pytest-capturelog': 'pytest_capturelog',
                'pytest-instafail': 'pytest_instafail',
                'pytest-xdist': 'xdist',
                'pytest-cov': 'pytest_cov',
                'pytest-flakes': 'pytest_flakes',
                'pytest-pep8': 'pytest_pep8',
                'pyopengl': 'OpenGL',
                _pyside('3.4', marker=False): 'PySide',
                _pyside('3.3', marker=False): 'PySide',
                _pyside('2.7', marker=False): 'PySide',
                'pyside': 'PySide'}


def strip_markers(name):
    for m in ';<>=':
        try:
            i = name.index(m)
            name = name[:i].strip()
        except ValueError:
            continue
    return name


def extras():
    import pkg_resources
    import itertools
    def _ex(name):
        # no environment specifiers or wheel URI etc are allowed in extras
        name = strip_markers(name)
        try:
            next(pkg_resources.parse_requirements(name))
        except pkg_resources.RequirementParseError:
            name = import_names[name]
        return name

    def _candidates():
        # skip those which aren't needed in our current environment (py ver, platform)
        for pkg in set(itertools.chain(doc_requires, tests_require, install_suggests.keys())):
            try:
                marker = next(pkg_resources.parse_requirements(pkg)).marker
                if marker is None or marker.evaluate():
                    yield pkg
            except pkg_resources.RequirementParseError:
                # try to fake a package to get the marker parsed
                clean = _ex(pkg)
                stripped = strip_markers(pkg)
                fake_pkg = 'pip ' + pkg.replace(stripped, '')
                try:
                    marker = next(pkg_resources.parse_requirements(fake_pkg)).marker
                    if marker is None or marker.evaluate():
                        yield pkg
                except pkg_resources.RequirementParseError:
                    continue

    full = [_ex(f) for f in _candidates()]
    return {
        'full':  full,
        'travis':  travis_requires,
    }


def missing(names):
    for name in names:
        stripped_name = strip_markers(name)
        try:
            __import__(stripped_name)
        except ImportError:
            if stripped_name in import_names:
                try:
                    __import__(import_names[stripped_name])
                except ImportError:
                    yield name, import_names[stripped_name]
            else:
                yield name, stripped_name


if __name__ == '__main__':
    note = '# This file is autogenerated. Edit dependencies.py instead'
    print(' '.join([i for i in install_requires + list(install_suggests.keys())]))
    import os
    import itertools
    with open(os.path.join(os.path.dirname(__file__), 'requirements.txt'), 'wt') as req:
        req.write(note+'\n')
        for module in sorted(set(itertools.chain(install_requires, setup_requires))):
            req.write(module+'\n')
    with open(os.path.join(os.path.dirname(__file__), 'requirements-optional.txt'), 'wt') as req:
        req.write(note+'\n')
        req.write('-r requirements.txt\n')
        for module in sorted(set(itertools.chain(tests_require, install_suggests.keys()))):
            req.write(module+'\n')
    with open(os.path.join(os.path.dirname(__file__), 'requirements-rtd.txt'), 'wt') as req:
        rtd = '''# This file is sourced by readthedocs.org to install missing dependencies.
# We need a more recent version of Sphinx for being able to provide
# our own docutils.conf.'''
        req.write(rtd+'\n')
        req.write(note+'\n')
        for module in sorted(doc_requires):
            req.write(module+'\n')
    with open(os.path.join(os.path.dirname(__file__), 'requirements-travis.txt'), 'wt') as req:
        req.write('-r requirements.txt\n')
        req.write(note+'\n')
        for module in sorted(travis_requires):
            req.write(module+'\n')
