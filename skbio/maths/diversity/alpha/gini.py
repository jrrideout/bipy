#!/usr/bin/env python
from __future__ import division

# ----------------------------------------------------------------------------
# Copyright (c) 2013--, scikit-bio development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import numpy as np

from .base import _validate


def gini_index(data, method='rectangles'):
    """Calculate the Gini index.

    Formula is ``G = A/(A+B)`` where ``A`` is the area between ``y=x`` and the
    Lorenz curve and ``B`` is the area under the Lorenz curve. Simplifies to
    ``1-2B`` since ``A+B=0.5``.

    Parameters
    ----------
    data : (N,) array_like
        Vector of counts, abundances, proportions, etc. All entries must be
        non-negative.
    method : {'rectangles', 'trapezoids'}
        Method for calculating the area under the Lorenz curve. If
        ``'rectangles'``, connects the Lorenz curve points by lines parallel to
        the x axis. This is the correct method (in our opinion) though
        trapezoids might be desirable in some circumstances. Forumla is:
        ``dx(sum(i=1,i=n,h_i))``.
        If ``'trapezoids'``, connects the Lorenz curve points by linear
        segments between them. Basically assumes that the given sampling is
        accurate and that more features of given data would fall on linear
        gradients between the values of this data. Formula is:
        ``dx[(h_0+h_n)/2 + sum(i=1,i=n-1,h_i)]``.

    Returns
    -------
    double
        Gini index.

    Raises
    ------
    ValueError
        If `method` isn't one of the supported methods for calculating the area
        under the curve.

    Notes
    -----
    The Gini index was introduced in [1]_.

    References
    ----------
    .. [1] Gini, C. (1912). "Variability and Mutability", C. Cuppini, Bologna,
       156 pages. Reprinted in Memorie di metodologica statistica (Ed. Pizetti
       E, Salvemini, T). Rome: Libreria Eredi Virgilio Veschi (1955).

    """
    # Suppress cast to int because this method supports ints and floats.
    data = _validate(data, suppress_cast=True)
    lorenz_points = _lorenz_curve(data)
    B = _lorenz_curve_integrator(lorenz_points, method)
    return 1 - 2 * B


def _lorenz_curve(data):
    """Calculate the Lorenz curve for input data.

    Notes
    -----
    Formula available on wikipedia.

    """
    sorted_data = np.sort(data)
    Sn = sorted_data.sum()
    n = sorted_data.shape[0]
    return np.arange(1, n + 1) / n, sorted_data.cumsum() / Sn


def _lorenz_curve_integrator(lc_pts, method):
    """Calculates the area under a Lorenz curve.

    Notes
    -----
    Could be utilized for integrating other simple, non-pathological
    "functions" where width of the trapezoids is constant.

    """
    x, y = lc_pts

    # each point differs by 1/n
    dx = 1 / x.shape[0]

    if method == 'trapezoids':
        # 0 percent of the population has zero percent of the goods
        h_0 = 0.0
        h_n = y[-1]
        # the 0th entry is at x=1/n
        sum_hs = y[:-1].sum()
        return dx * ((h_0 + h_n) / 2 + sum_hs)
    elif method == 'rectangles':
        return dx * y.sum()
    else:
        raise ValueError("Method '%s' not implemented. Available methods: "
                         "'rectangles', 'trapezoids'." % method)