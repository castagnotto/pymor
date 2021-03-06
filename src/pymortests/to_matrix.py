# This file is part of the pyMOR project (http://www.pymor.org).
# Copyright 2013-2017 pyMOR developers and contributors. All rights reserved.
# License: BSD 2-Clause License (http://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, division, print_function

import numpy as np
import scipy.linalg as spla
import scipy.sparse as sps

from pymor.algorithms.to_matrix import to_matrix
from pymor.operators.block import BlockOperator, BlockDiagonalOperator
from pymor.operators.constructions import (AdjointOperator, Concatenation, ComponentProjection, IdentityOperator,
                                           LincombOperator, VectorArrayOperator, ZeroOperator)
from pymor.operators.numpy import NumpyMatrixOperator
from pymor.vectorarrays.numpy import NumpyVectorSpace


def assert_type_and_allclose(A, Aop, default_format):
    if default_format == 'dense':
        assert isinstance(to_matrix(Aop), np.ndarray)
        assert np.allclose(A, to_matrix(Aop))
    elif default_format == 'sparse':
        assert sps.issparse(to_matrix(Aop))
        assert np.allclose(A, to_matrix(Aop).toarray())
    else:
        assert getattr(sps, 'isspmatrix_' + default_format)(to_matrix(Aop))
        assert np.allclose(A, to_matrix(Aop).toarray())

    assert isinstance(to_matrix(Aop, format='dense'), np.ndarray)
    assert np.allclose(A, to_matrix(Aop, format='dense'))

    assert sps.isspmatrix_csr(to_matrix(Aop, format='csr'))
    assert np.allclose(A, to_matrix(Aop, format='csr').toarray())


def test_to_matrix_NumpyMatrixOperator():
    np.random.seed(0)
    A = np.random.randn(2, 2)

    Aop = NumpyMatrixOperator(A)
    assert_type_and_allclose(A, Aop, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    assert_type_and_allclose(A, Aop, 'csc')


def test_to_matrix_BlockOperator():
    np.random.seed(0)
    A11 = np.random.randn(2, 2)
    A12 = np.random.randn(2, 3)
    A21 = np.random.randn(3, 2)
    A22 = np.random.randn(3, 3)
    B = np.asarray(np.bmat([[A11, A12], [A21, A22]]))

    A11op = NumpyMatrixOperator(A11)
    A12op = NumpyMatrixOperator(A12)
    A21op = NumpyMatrixOperator(A21)
    A22op = NumpyMatrixOperator(A22)
    Bop = BlockOperator([[A11op, A12op], [A21op, A22op]])
    assert_type_and_allclose(B, Bop, 'dense')

    A11op = NumpyMatrixOperator(sps.csc_matrix(A11))
    A12op = NumpyMatrixOperator(A12)
    A21op = NumpyMatrixOperator(A21)
    A22op = NumpyMatrixOperator(A22)
    Bop = BlockOperator([[A11op, A12op], [A21op, A22op]])
    assert_type_and_allclose(B, Bop, 'sparse')


def test_to_matrix_BlockDiagonalOperator():
    np.random.seed(0)
    A1 = np.random.randn(2, 2)
    A2 = np.random.randn(3, 3)
    B = np.asarray(np.bmat([[A1, np.zeros((2, 3))],
                            [np.zeros((3, 2)), A2]]))

    A1op = NumpyMatrixOperator(A1)
    A2op = NumpyMatrixOperator(A2)
    Bop = BlockDiagonalOperator([A1op, A2op])
    assert_type_and_allclose(B, Bop, 'sparse')

    A1op = NumpyMatrixOperator(sps.csc_matrix(A1))
    A2op = NumpyMatrixOperator(A2)
    Bop = BlockDiagonalOperator([A1op, A2op])
    assert_type_and_allclose(B, Bop, 'sparse')


def test_to_matrix_AdjointOperator():
    np.random.seed(0)
    A = np.random.randn(2, 2)
    S = np.random.randn(2, 2)
    S = S.dot(S.T)
    R = np.random.randn(2, 2)
    R = R.dot(R.T)

    Aop = NumpyMatrixOperator(A)
    Aadj = AdjointOperator(Aop)
    assert_type_and_allclose(A.T, Aadj, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Aadj = AdjointOperator(Aop)
    assert_type_and_allclose(A.T, Aadj, 'sparse')

    Aop = NumpyMatrixOperator(A)
    Sop = NumpyMatrixOperator(S)
    Rop = NumpyMatrixOperator(R)
    Aadj = AdjointOperator(Aop, source_product=Sop, range_product=Rop)
    assert_type_and_allclose(spla.solve(S, A.T.dot(R)), Aadj, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Sop = NumpyMatrixOperator(S)
    Rop = NumpyMatrixOperator(R)
    Aadj = AdjointOperator(Aop, source_product=Sop, range_product=Rop)
    assert_type_and_allclose(spla.solve(S, A.T.dot(R)), Aadj, 'dense')

    Aop = NumpyMatrixOperator(A)
    Sop = NumpyMatrixOperator(S)
    Rop = NumpyMatrixOperator(sps.csc_matrix(R))
    Aadj = AdjointOperator(Aop, source_product=Sop, range_product=Rop)
    assert_type_and_allclose(spla.solve(S, A.T.dot(R)), Aadj, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Sop = NumpyMatrixOperator(sps.csc_matrix(S))
    Rop = NumpyMatrixOperator(sps.csc_matrix(R))
    Aadj = AdjointOperator(Aop, source_product=Sop, range_product=Rop)
    assert_type_and_allclose(spla.solve(S, A.T.dot(R)), Aadj, 'sparse')


def test_to_matrix_ComponentProjection():
    components = np.array([0, 1, 2, 4, 8])
    n = 10
    A = np.zeros((len(components), n))
    A[range(len(components)), components] = 1

    source = NumpyVectorSpace(n)
    Aop = ComponentProjection(components, source)
    assert_type_and_allclose(A, Aop, 'sparse')


def test_to_matrix_Concatenation():
    np.random.seed(0)
    A = np.random.randn(2, 3)
    B = np.random.randn(3, 4)
    C = A.dot(B)

    Aop = NumpyMatrixOperator(A)
    Bop = NumpyMatrixOperator(B)
    Cop = Concatenation(Aop, Bop)
    assert_type_and_allclose(C, Cop, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Bop = NumpyMatrixOperator(B)
    Cop = Concatenation(Aop, Bop)
    assert_type_and_allclose(C, Cop, 'dense')

    Aop = NumpyMatrixOperator(A)
    Bop = NumpyMatrixOperator(sps.csc_matrix(B))
    Cop = Concatenation(Aop, Bop)
    assert_type_and_allclose(C, Cop, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Bop = NumpyMatrixOperator(sps.csc_matrix(B))
    Cop = Concatenation(Aop, Bop)
    assert_type_and_allclose(A, Aop, 'sparse')


def test_to_matrix_IdentityOperator():
    n = 3
    I = np.eye(n)

    Iop = IdentityOperator(NumpyVectorSpace(n))
    assert_type_and_allclose(I, Iop, 'sparse')


def test_to_matrix_LincombOperator():
    np.random.seed(0)
    A = np.random.randn(3, 3)
    B = np.random.randn(3, 2)
    a = np.random.randn()
    b = np.random.randn()
    C = a * A + b * B.dot(B.T)

    Aop = NumpyMatrixOperator(A)
    Bop = NumpyMatrixOperator(B)
    Cop = LincombOperator([Aop, Concatenation(Bop, Bop.T)], [a, b])
    assert_type_and_allclose(C, Cop, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Bop = NumpyMatrixOperator(B)
    Cop = LincombOperator([Aop, Concatenation(Bop, Bop.T)], [a, b])
    assert_type_and_allclose(C, Cop, 'dense')

    Aop = NumpyMatrixOperator(A)
    Bop = NumpyMatrixOperator(sps.csc_matrix(B))
    Cop = LincombOperator([Aop, Concatenation(Bop, Bop.T)], [a, b])
    assert_type_and_allclose(C, Cop, 'dense')

    Aop = NumpyMatrixOperator(sps.csc_matrix(A))
    Bop = NumpyMatrixOperator(sps.csc_matrix(B))
    Cop = LincombOperator([Aop, Concatenation(Bop, Bop.T)], [a, b])
    assert_type_and_allclose(C, Cop, 'sparse')


def test_to_matrix_VectorArrayOperator():
    np.random.seed(0)
    V = np.random.randn(10, 2)

    Vva = NumpyVectorSpace.make_array(V.T)
    Vop = VectorArrayOperator(Vva)
    assert_type_and_allclose(V, Vop, 'dense')

    Vop = VectorArrayOperator(Vva, transposed=True)
    assert_type_and_allclose(V.T, Vop, 'dense')


def test_to_matrix_ZeroOperator():
    n = 3
    m = 4
    Z = np.zeros((n, m))

    Zop = ZeroOperator(NumpyVectorSpace(m), NumpyVectorSpace(n))
    assert_type_and_allclose(Z, Zop, 'sparse')
