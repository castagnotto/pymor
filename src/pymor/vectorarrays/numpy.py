# -*- coding: utf-8 -*-
# This file is part of the pyMOR project (http://www.pymor.org).
# Copyright 2013-2016 pyMOR developers and contributors. All rights reserved.
# License: BSD 2-Clause License (http://opensource.org/licenses/BSD-2-Clause)

from numbers import Number

import numpy as np
from scipy.sparse import issparse

from pymor.core import NUMPY_INDEX_QUIRK
from pymor.vectorarrays.interfaces import VectorArrayInterface, VectorSpace, _INDEXTYPES


class NumpyVectorArray(VectorArrayInterface):
    """|VectorArray| implementation via |NumPy arrays|.

    This is the default |VectorArray| type used by all |Operators|
    in pyMOR's discretization toolkit. Moreover, all reduced |Operators|
    are based on |NumpyVectorArray|.

    Note that this class is just a thin wrapper around the underlying
    |NumPy array|. Thus, while operations like
    :meth:`~pymor.vectorarrays.interfaces.VectorArrayInterface.axpy` or
    :meth:`~pymor.vectorarrays.interfaces.VectorArrayInterface.dot`
    will be quite efficient, removing or appending vectors will
    be costly.
    """

    def __init__(self, instance, dtype=None, copy=False, order=None, subok=False):
        assert not isinstance(instance, np.matrixlib.defmatrix.matrix)
        if isinstance(instance, np.ndarray):
            if copy:
                self._array = instance.copy()
            else:
                self._array = instance
        elif issparse(instance):
            self._array = instance.toarray()
        elif hasattr(instance, 'data'):
            self._array = instance.data
            if copy:
                self._array = self._array.copy()
        else:
            self._array = np.array(instance, dtype=dtype, copy=copy, order=order, subok=subok, ndmin=2)
        if self._array.ndim != 2:
            assert self._array.ndim == 1
            self._array = np.reshape(self._array, (1, -1))
        self._len = len(self._array)
        self._refcount = [1]

    @classmethod
    def from_data(cls, data, subtype):
        return cls(data)

    @classmethod
    def from_file(cls, path, key=None, single_vector=False, transpose=False):
        assert not (single_vector and transpose)
        from pymor.tools.io import load_matrix
        array = load_matrix(path, key=key)
        assert isinstance(array, np.ndarray)
        assert array.ndim <= 2
        if array.ndim == 1:
            array = array.reshape((1, -1))
        if single_vector:
            assert array.shape[0] == 1 or array.shape[1] == 1
            array = array.reshape((1, -1))
        if transpose:
            array = array.T
        return cls(array)

    @classmethod
    def make_array(cls, subtype=None, count=0, reserve=0):
        assert isinstance(subtype, _INDEXTYPES)
        assert count >= 0
        assert reserve >= 0
        va = cls(np.empty((0, 0)))
        va._array = np.zeros((max(count, reserve), subtype))
        va._len = count
        return va

    @property
    def data(self):
        return self._array[:self._len]

    @property
    def real(self):
        return NumpyVectorArray(self._array[:self._len].real, copy=True)

    @property
    def imag(self):
        return NumpyVectorArray(self._array[:self._len].imag, copy=True)

    def __len__(self):
        return self._len

    @property
    def subtype(self):
        return self._array.shape[1]

    @property
    def dim(self):
        return self._array.shape[1]

    def copy(self, ind=None, deep=False):
        assert self.check_ind(ind)

        if not deep and ind is None:
            c = NumpyVectorArray(self._array, copy=False)
            c._len = self._len
            c._refcount = self._refcount
            self._refcount[0] += 1
            return c

        if NUMPY_INDEX_QUIRK and self._len == 0:
            return NumpyVectorArray(self._array[:0], copy=True)

        if ind is None:
            return NumpyVectorArray(self._array[:self._len], copy=True)
        else:
            C = NumpyVectorArray(self._array[ind], copy=False)
            if not C._array.flags['OWNDATA']:
                C._array = np.array(C._array)
            return C

    __getitem__ = copy

    def append(self, other, remove_from_other=False):
        assert self.dim == other.dim
        assert other is not self or not remove_from_other

        if self._refcount[0] > 1:
            self._deep_copy()
        if remove_from_other and other._refcount[0] > 1:
            other._deep_copy()

        len_other = other._len
        if len_other <= self._array.shape[0] - self._len:
            if self._array.dtype != other._array.dtype:
                self._array = self._array.astype(np.promote_types(self._array.dtype, other._array.dtype))
            self._array[self._len:self._len + len_other] = other._array[:len_other]
        else:
            self._array = np.vstack((self._array[:self._len], other._array[:len_other]))
        self._len += len_other
        if remove_from_other:
            other.remove()

    def remove(self, ind=None):
        assert self.check_ind(ind)

        if self._refcount[0] > 1:
            self._deep_copy()

        if ind is None:
            self._array = np.zeros((0, self.dim))
            self._len = 0
        else:
            if hasattr(ind, '__len__'):
                if len(ind) == 0:
                    return
                remaining = sorted(set(range(len(self))) - set(ind))
                self._array = self._array[remaining]
            else:
                assert -self._len < ind < self._len
                self._array = self._array[list(range(ind)) + list(range(ind + 1, self._len))]
            self._len = self._array.shape[0]
        if not self._array.flags['OWNDATA']:
            self._array = self._array.copy()

    __delitem__ = remove

    def scal(self, alpha, *, ind=None):
        assert self.check_ind_unique(ind)
        assert isinstance(alpha, _INDEXTYPES) \
            or isinstance(alpha, np.ndarray) and alpha.shape == (self.len_ind(ind),)

        if self._refcount[0] > 1:
            self._deep_copy()

        if NUMPY_INDEX_QUIRK and self._len == 0:
            return

        if isinstance(alpha, np.ndarray) and not isinstance(ind, Number):
            alpha = alpha[:, np.newaxis]

        alpha_type = type(alpha)
        alpha_dtype = alpha.dtype if alpha_type is np.ndarray else alpha_type
        if self._array.dtype != alpha_dtype:
            self._array = self._array.astype(np.promote_types(self._array.dtype, alpha_dtype))

        if ind is None:
            self._array[:self._len] *= alpha
        else:
            self._array[ind] *= alpha

    def axpy(self, alpha, x, *, ind=None):
        assert self.check_ind_unique(ind)
        assert self.dim == x.dim
        assert self.len_ind(ind) == len(x) or len(x) == 1
        assert isinstance(alpha, _INDEXTYPES) \
            or isinstance(alpha, np.ndarray) and alpha.shape == (self.len_ind(ind),)

        if self._refcount[0] > 1:
            self._deep_copy()

        if NUMPY_INDEX_QUIRK:
            if self._len == 0 and hasattr(ind, '__len__'):
                ind = None

        if np.all(alpha == 0):
            return

        B = x._array[:x._len]

        alpha_type = type(alpha)
        alpha_dtype = alpha.dtype if alpha_type is np.ndarray else alpha_type
        if self._array.dtype != alpha_dtype or self._array.dtype != B.dtype:
            dtype = np.promote_types(self._array.dtype, alpha_dtype)
            dtype = np.promote_types(dtype, B.dtype)
            self._array = self._array.astype(dtype)

        if np.all(alpha == 1):
            if ind is None:
                self._array[:self._len] += B
            elif isinstance(ind, Number) and B.ndim == 2:
                self._array[ind] += B.reshape((B.shape[1],))
            else:
                self._array[ind] += B
        elif np.all(alpha == -1):
            if ind is None:
                self._array[:self._len] -= B
            elif isinstance(ind, Number) and B.ndim == 2:
                self._array[ind] -= B.reshape((B.shape[1],))
            else:
                self._array[ind] -= B
        else:
            if isinstance(alpha, np.ndarray):
                alpha = alpha[:, np.newaxis]
            if ind is None:
                self._array[:self._len] += (B * alpha)
            elif isinstance(ind, Number):
                self._array[ind] += (B * alpha).reshape((-1,))
            else:
                self._array[ind] += (B * alpha)

    def dot(self, other):
        assert self.dim == other.dim

        A = self._array[:self._len]
        B = other._array[:other._len]

        if B.dtype in _complex_dtypes:
            return A.dot(B.conj().T)
        else:
            return A.dot(B.T)

    def pairwise_dot(self, other):
        assert self.dim == other.dim
        assert len(self) == len(other)

        A = self._array[:self._len]
        B = other._array[:other._len]

        if B.dtype in _complex_dtypes:
            return np.sum(A * B.conj(), axis=1)
        else:
            return np.sum(A * B, axis=1)

    def lincomb(self, coefficients):
        assert 1 <= coefficients.ndim <= 2
        if coefficients.ndim == 1:
            coefficients = coefficients[np.newaxis, ...]
        assert coefficients.shape[1] == len(self)

        return NumpyVectorArray(coefficients.dot(self._array[:self._len]), copy=False)

    def l1_norm(self):
        return np.linalg.norm(self._array[:self._len], ord=1, axis=1)

    def l2_norm(self):
        return np.linalg.norm(self._array[:self._len], axis=1)

    def l2_norm2(self):
        A = self._array[:self._len]
        return np.sum((A * A.conj()).real, axis=1)

    def components(self, component_indices):
        assert isinstance(component_indices, list) and (len(component_indices) == 0 or min(component_indices) >= 0) \
            or (isinstance(component_indices, np.ndarray) and component_indices.ndim == 1
                and (len(component_indices) == 0 or np.min(component_indices) >= 0))
        # NumPy 1.9 is quite permissive when indexing arrays of size 0, so we have to add the
        # following check:
        assert self._len > 0 \
            or (isinstance(component_indices, list)
                and (len(component_indices) == 0 or max(component_indices) < self.dim)) \
            or (isinstance(component_indices, np.ndarray) and component_indices.ndim == 1
                and (len(component_indices) == 0 or np.max(component_indices) < self.dim))

        if NUMPY_INDEX_QUIRK and (self._len == 0 or self.dim == 0):
            assert isinstance(component_indices, list) \
                and (len(component_indices) == 0 or max(component_indices) < self.dim) \
                or isinstance(component_indices, np.ndarray) \
                and component_indices.ndim == 1 \
                and (len(component_indices) == 0 or np.max(component_indices) < self.dim)
            return np.zeros((0, len(component_indices)))

        return self._array[:self._len, component_indices]

    def amax(self):
        assert self.dim > 0

        if self._array.shape[1] == 0:
            l = len(self)
            return np.ones(l) * -1, np.zeros(l)

        A = self._array[:self._len]
        A = np.abs(A)
        max_ind = np.argmax(A, axis=1)
        max_val = A[np.arange(len(A)), max_ind]
        return max_ind, max_val

    def __str__(self):
        return self._array[:self._len].__str__()

    def __repr__(self):
        return 'NumpyVectorArray({})'.format(self._array[:self._len].__str__())

    def __del__(self):
        self._refcount[0] -= 1

    def _deep_copy(self):
        self._array = self._array.copy()  # copy the array data
        self._refcount[0] -= 1            # decrease refcount for original array
        self._refcount = [1]              # create new reference counter


def NumpyVectorSpace(dim):
    """Shorthand for |VectorSpace| `(NumpyVectorArray, dim)`."""
    return VectorSpace(NumpyVectorArray, dim)


_complex_dtypes = (np.complex64, np.complex128)
