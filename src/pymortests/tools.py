# This file is part of the pyMOR project (http://www.pymor.org).
# Copyright 2013-2016 pyMOR developers and contributors. All rights reserved.
# License: BSD 2-Clause License (http://opensource.org/licenses/BSD-2-Clause)

from math import sin, pi, exp
import numpy as np
import pytest
import itertools
from tempfile import NamedTemporaryFile
import os.path
from pkg_resources import resource_filename
import subprocess

from pymortests.base import TestInterface, runmodule
from pymortests.fixtures.grid import rect_or_tria_grid, rect_grid, tria_grid
from pymortests.base import polynomials
from pymor.tools.deprecated import Deprecated
from pymor.tools.quadratures import GaussQuadratures
from pymor.tools.floatcmp import float_cmp, float_cmp_all
from pymor.tools.vtkio import write_vtk
from pymor.vectorarrays.numpy import NumpyVectorSpace
from pymor.tools import timing


FUNCTIONS = (('sin(2x pi)', lambda x: sin(2 * x * pi), 0),
             ('e^x', lambda x: exp(x), exp(1) - exp(0)))


class TestGaussQuadrature(TestInterface):

    def test_polynomials(self):
        for n, function, _, integral in polynomials(GaussQuadratures.orders[-1]):
            name = 'x^{}'.format(n)
            for order in GaussQuadratures.orders:
                if n > order / 2:
                    continue
                Q = GaussQuadratures.iter_quadrature(order)
                ret = sum([function(p) * w for (p, w) in Q])
                assert float_cmp(ret, integral), '{} integral wrong: {} vs {} (quadrature order {})'.format(
                    name, integral, ret, order)

    def test_other_functions(self):
        order = GaussQuadratures.orders[-1]
        for name, function, integral in FUNCTIONS:
            Q = GaussQuadratures.iter_quadrature(order)
            ret = sum([function(p) * w for (p, w) in Q])
            assert float_cmp(ret, integral), '{} integral wrong: {} vs {} (quadrature order {})'.format(
                name, integral, ret, order)

    def test_weights(self):
        for order in GaussQuadratures.orders:
            _, W = GaussQuadratures.quadrature(order)
            assert float_cmp(sum(W), 1)

    def test_points(self):
        for order in GaussQuadratures.orders:
            P, _ = GaussQuadratures.quadrature(order)
            assert float_cmp_all(P, np.sort(P))
            assert 0.0 < P[0]
            assert P[-1] < 1.0


class TestCmp(TestInterface):

    def test_props(self):
        tol_range = [0.0, 1e-8, 1]
        nan = float('nan')
        inf = float('inf')
        for (rtol, atol) in itertools.product(tol_range, tol_range):
            msg = 'rtol: {} | atol {}'.format(rtol, atol)
            assert float_cmp(0., 0., rtol, atol), msg
            assert float_cmp(-0., -0., rtol, atol), msg
            assert float_cmp(-1., -1., rtol, atol), msg
            assert float_cmp(0., -0., rtol, atol), msg
            assert not float_cmp(2., -2., rtol, atol), msg

            assert not float_cmp(nan, nan, rtol, atol), msg
            assert nan != nan
            assert not (nan == nan)
            assert not float_cmp(-nan, nan, rtol, atol), msg

            assert not float_cmp(inf, inf, rtol, atol), msg
            assert not (inf != inf)
            assert inf == inf
            if rtol > 0:
                assert float_cmp(-inf, inf, rtol, atol), msg
            else:
                assert not float_cmp(-inf, inf, rtol, atol), msg


def _check_vtk_file(path):
    try:
        # this check will current fail if no python2 is available
        # it needs to be a seperate process since there are no py3 bindings for paraview
        script = resource_filename('pymortests', 'paraview_file_check.py')
        out = subprocess.check_output([script, path], stderr=subprocess.STDOUT, universal_newlines=True)
    except subprocess.CalledProcessError as cpe:
        assert cpe.returncode == 77  #no paraview bindings, special hardcoded magic value :|
    else:
        # paraview bindings to not raise an Exception for unreadable files. (Or ANY unrecoverable error afaict)
        assert 'Error' not in out

def test_vtkio(rect_or_tria_grid):
    grid = rect_or_tria_grid
    steps = 1
    for codim, data in enumerate((NumpyVectorSpace.from_data(np.zeros((steps, grid.size(c)))) for c in range(grid.dim+1))):
        with NamedTemporaryFile('wb', delete=False) as out:
            if codim == 1:
                with pytest.raises(NotImplementedError):
                    write_vtk(grid, data, out.name, codim=codim)
            else:
                files = write_vtk(grid, data, out.name, codim=codim)
                for f in files:
                    _check_vtk_file(f)


class TestTiming(TestInterface):

    def testTimingContext(self):
        with timing.Timer('busywait', self.logger):
            timing.busywait(100)
        with timing.Timer('defaultlog'):
            timing.busywait(100)

    @timing.Timer('busywait_decorator', TestInterface.logger)
    def wait(self):
        timing.busywait(1000)

    def testTimingDecorator(self):
        self.wait()

    def testTiming(self):
        timer = timing.Timer('busywait', self.logger)
        timer.start()
        timing.busywait(1000)
        timer.stop()
        self.logger.info('plain timing took %s seconds', timer.dt)


def testDeprecated():
    @Deprecated('use other stuff instead')
    def deprecated_function():
        pass
    # Cause all warnings to always be triggered.
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Trigger a warning.
        deprecated_function()
        # Verify some things
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)
        assert "DeprecationWarning" in str(w[-1].message)


if __name__ == "__main__":
    runmodule(filename=__file__)
