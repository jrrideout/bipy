#!/usr/bin/env python
from __future__ import division

#-----------------------------------------------------------------------------
# Copyright (c) 2013, The BiPy Developers.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import csv
from copy import deepcopy
from itertools import izip
from StringIO import StringIO

import numpy as np
from scipy.spatial.distance import is_valid_dm, squareform

class DistanceMatrixError(Exception):
    pass

class MissingSampleIDError(Exception):
    pass

class DistanceMatrixFormatError(Exception):
    pass

class SampleIDMismatchError(Exception):
    def __init__(self):
        self.args = ("Encountered mismatched sample IDs while parsing the "
                     "distance matrix file. Please ensure that the sample IDs "
                     "match between the distance matrix header (first row) "
                     "and the row labels (first column).",)

class MissingHeaderError(Exception):
    def __init__(self):
        self.args = ("Could not find a header line containing sample IDs in "
                     "the distance matrix file. Please verify that the file "
                     "is not empty.",)

class DistanceMatrix(object):

    @classmethod
    def from_file(cls, dm_f, delimiter='\t'):
        # We aren't using np.loadtxt because it uses *way* too much memory
        # (e.g, a 2GB matrix eats up 10GB, which then isn't freed after parsing
        # has finished). See:
        # http://mail.scipy.org/pipermail/numpy-tickets/2012-August/006749.html

        # Strategy:
        #     - find the header
        #     - initialize an empty ndarray
        #     - for each row of data in the input file:
        #         - initialize a row vector of zeros
        #         - fill in only lower-triangular values (exclude the diagonal)
        #         - populate the corresponding row in the ndarray
        #     - fill in the upper triangle based on the lower triangle
        sids = None
        for line_idx, line in enumerate(dm_f):
            tokens = map(lambda e: e.strip(), line.strip().split(delimiter))

            if line_idx == 0:
                # We're at the header (sample IDs).
                sids = tokens
                num_sids = len(sids)
                data = np.empty((num_sids, num_sids))
            elif line_idx <= num_sids:
                if len(tokens) != num_sids + 1:
                    raise DistanceMatrixFormatError("The number of values in "
                            "row number %d is not equal to the number of "
                            "sample IDs in the header." % line_idx)

                row_idx = line_idx - 1

                if tokens[0] == sids[row_idx]:
                    row_data = np.zeros(num_sids)

                    for col_idx in range(row_idx):
                        row_data[col_idx] = float(tokens[col_idx + 1])

                    data[row_idx,:] = row_data
                else:
                    raise SampleIDMismatchError
            else:
                if ''.join(tokens):
                    # If it isn't a blank line, raise an error because we
                    # shouldn't ignore extra data.
                    raise DistanceMatrixFormatError("Encountered extra rows "
                            "without corresponding sample IDs in the header.")

        if sids is None:
            raise MissingHeaderError

        data += data.T

        return cls(data, sids)

    def __init__(self, data, sample_ids):
        data = np.asarray(data, dtype='float')
        sample_ids = tuple(sample_ids)
        self._validate(data, sample_ids)

        self._data = data
        self._sample_ids = sample_ids
        self._sample_index = self._index_list(self._sample_ids)

    @property
    def data(self):
        return self._data

    @property
    def sample_ids(self):
        return self._sample_ids

    @sample_ids.setter
    def sample_ids(self, sample_ids_):
        sample_ids_ = tuple(sample_ids_)
        self._validate(self.data, sample_ids_)
        self._sample_ids = sample_ids_
        self._sample_index = self._index_list(self._sample_ids)

    @property
    def dtype(self):
        return self.data.dtype

    @property
    def shape(self):
        return self.data.shape

    @property
    def num_samples(self):
        """Returns the number of samples (i.e. number of rows or columns)."""
        return len(self.sample_ids)

    @property
    def size(self):
        return self.data.size

    @property
    def T(self):
        return self.transpose()

    def transpose(self):
        return self

    def condensed_form(self):
        return squareform(self.data, force='tovector')

    def redundant_form(self):
        return self.data

    def copy(self):
        # We deepcopy sample IDs in case the tuple contains mutable objects at
        # some point in the future.
        return self.__class__(self.data.copy(), deepcopy(self.sample_ids))

    def __str__(self):
        return '%dx%d distance matrix\nSample IDs:\n%s\nData:\n' % (
                self.shape[0], self.shape[1],
                self._pprint_sample_ids()) + str(self.data)

    def __eq__(self, other):
        eq = True

        # The order these checks are performed in is important to be as
        # efficient as possible. The check for shape equality is not strictly
        # necessary as it should be taken care of in np.array_equal, but I'd
        # rather explicitly bail before comparing IDs or data. Use array_equal
        # instead of (a == b).all() because of this issue:
        #     http://stackoverflow.com/a/10582030
        if not isinstance(other, self.__class__):
            eq = False
        elif self.shape != other.shape:
            eq = False
        elif self.sample_ids != other.sample_ids:
            eq = False
        elif not np.array_equal(self.data, other.data):
            eq = False

        return eq

    def __ne__(self, other):
        return not (self == other)

    def __getitem__(self, sample_id):
        if sample_id in self._sample_index:
            return self.data[self._sample_index[sample_id]]
        else:
            raise MissingSampleIDError("The sample ID '%s' is not in the "
                                       "distance matrix." % sample_id)

    def to_file(self, out_f, delimiter='\t', conserve_memory=False):
        formatted_sids = self._format_sample_ids(delimiter)
        out_f.write(formatted_sids)
        out_f.write('\n')

        if conserve_memory:
            for sid, vals in izip(self.sample_ids, self.data):
                out_f.write(delimiter.join([sid] + map(str, vals)))
                out_f.write('\n')
        else:
            temp_f = StringIO()
            np.savetxt(temp_f, self.data, delimiter=delimiter, fmt='%s')
            temp_f.seek(0)

            for sid, line in izip(self.sample_ids, temp_f):
                out_f.write(sid)
                out_f.write(delimiter)
                out_f.write(line)
            temp_f.close()

    def _validate(self, data, sample_ids):
        # Accepts arguments instead of inspecting instance attributes because
        # we don't want to create an invalid distance matrix before raising an
        # error (because then it could be used after the exception is caught).
        num_sids = len(sample_ids)

        if num_sids != len(set(sample_ids)):
            raise DistanceMatrixError("Sample IDs must be unique.")
        elif not is_valid_dm(data):
            raise DistanceMatrixError("Data must be an array that is "
                    "2-dimensional, square, symmetric, hollow, and contains "
                    "only floating point values.")
        elif num_sids != data.shape[0]:
            raise DistanceMatrixError("The number of sample IDs must match "
                    "the number of rows/columns in the data.")

    def _index_list(self, l):
        return dict([(id_, idx) for idx, id_ in enumerate(l)])

    def _format_sample_ids(self, delimiter):
        return delimiter.join([''] + list(self.sample_ids))

    def _pprint_sample_ids(self, max_chars=80, delimiter=', ', suffix='...',):
        """Adapted from http://stackoverflow.com/a/250373"""
        sids_str = delimiter.join(self.sample_ids)

        if len(sids_str) > max_chars:
            truncated = sids_str[:max_chars + 1].split(delimiter)[0:-1]
            sids_str = delimiter.join(truncated) + delimiter + suffix

        return sids_str