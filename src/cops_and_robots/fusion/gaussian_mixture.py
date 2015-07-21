#!/usr/bin/env python
from __future__ import division
"""Extends multivariate normal to a mixture of multivariate normals.



"""
__author__ = "Nick Sweet"
__copyright__ = "Copyright 2015, Cohrint"
__credits__ = ["Nick Sweet", "Nisar Ahmed"]
__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Nick Sweet"
__email__ = "nick.sweet@colorado.edu"
__status__ = "Development"

import logging
import os
import time
from copy import deepcopy

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from scipy.stats import multivariate_normal, norm
from descartes.patch import PolygonPatch
from shapely.geometry import Polygon


# <>TODO: test for greater than 2D mixtures
class GaussianMixture(object):
    """A collection of weighted multivariate normal distributions.

    A Gaussian mixture is a collection of mixands: individual multivariate 
    normals. It takes the form:

    .. math::

        f(\\mathbf{x}) = \\sum_{i=1}^n \\frac{w_i}
            {\\sqrt{(2\\pi)^d \\vert \\mathbf{P}_i \\vert}}
            \\exp{\\left[-\\frac{1}{2}(\\mathbf{x} - \\mathbf{\\mu}_i)^T
            \\mathbf{P}_i^{-1} (\\mathbf{x} - \\mathbf{\\mu}_i) \\right]}

    Where `d` is the dimensionality of the state vector `x`, and each mixand 
    `i` has weight, mean and covariances `w`, `mu` and `P`.

    Parameters
    ----------
    weights : array_like, optional
        Scaling factor for each mixand.

    Attributes
    ----------
    attr : attr_type
        attr_description

    Methods
    ----------
    attr : attr_type
        attr_description

    """

    def __init__(self, weights=1, means=0, covariances=1, ellipse_color='red',
                 max_num_mixands=20):
        self.weights = np.asarray(weights)
        self.means = np.asarray(means)
        self.covariances = np.asarray(covariances)
        self.ellipse_color = ellipse_color
        self.max_num_mixands = max_num_mixands
        self._input_check()

    def __str__(self):
        d = {}
        for i, weight in enumerate(self.weights):
            d['Mixand {}'.format(i)] = np.hstack((weight,
                                                  self.means[i],
                                                  self.covariances[i].flatten()
                                                  ))
        ind = ['Weight'] + ['Mean'] * self.ndims + ['Variance'] * self.ndims ** 2
        df = pd.DataFrame(d, index=ind)
        return '\n' + df.to_string()
            

    def pdf(self, x):
        """Probability density function at state x.

        Will return a probability distribution relative to the shape of the
        input and the dimensionality of the normal. For example, if x is 5x2 
        with a 2-dimensional normal, pdf is 5x1; if x is 5x5x2 
        with a 2-dimensional normal, pdf is 5x5.
        """

        # Ensure proper output shape
        x = np.atleast_1d(x)
        if self.ndims == x.shape[-1]:
            shape = x.shape[:-1]
        else:
            shape = x.shape

        pdf = np.zeros(shape)
        for i, weight in enumerate(self.weights):
            mean = self.means[i]
            covariance = self.covariances[i]
            gaussian_pdf = multivariate_normal.pdf(x, mean, covariance)
            # logging.info(x)
            # logging.info(x.size)
            # logging.info(mean)
            # logging.info(covariance)
            # logging.info(weight)
            pdf += weight * gaussian_pdf

        return pdf

    def rvs(self, size=1):
        """
        """
        c_weights = self.weights.cumsum()  # Cumulative weights
        c_weights = np.hstack([0, c_weights])
        r_weights = np.random.rand(size)  # Randomly sampled weights
        r_weights = np.sort(r_weights)

        if self.ndims > 1:
            rvs = np.zeros((size, self.ndims))
        else:
            rvs = np.zeros(size)
        prev_max = 0
        for i, c_weight in enumerate(c_weights):
            if i == c_weights.size - 1:
                break

            size_i = r_weights[r_weights > c_weight].size
            size_i = size_i - r_weights[r_weights > c_weights[i + 1]].size
            range_ = np.arange(size_i) + prev_max
            range_ = range_.astype(int)

            prev_max = range_[-1]
            mean = self.means[i]
            covariance = self.covariances[i]

            rvs[range_] = multivariate_normal.rvs(mean, covariance, size_i)

        return rvs

    def max_point_by_grid(self, bounds=[-5,-5,5,5], grid_spacing=0.1):
        #<>TODO: set for n-dimensional
        xx, yy = np.mgrid[bounds[0]:bounds[2]:grid_spacing,
                          bounds[1]:bounds[3]:grid_spacing]
        pos = np.empty(xx.shape + (2,))
        pos[:, :, 0] = xx
        pos[:, :, 1] = yy

        prob = self.pdf(pos)
        MAP_i = np.unravel_index(prob.argmax(), prob.shape)
        MAP_point = np.array([xx[MAP_i[0]][0], yy[0][MAP_i[1]]])
        MAP_prob = prob[MAP_i]
        return MAP_point, MAP_prob

    def copy(self):
        return deepcopy(self)

    def std_ellipses(self, num_std=1, resolution=20):
        """
        Generates `num_std` sigma error ellipses for each mixand.

        Note
        ----
        Only applies to two-dimensional Gaussian mixtures.

        Parameters
        ----------
            num_std : The ellipse size in number of standard deviations.
                Defaults to 2 standard deviations.

        Returns
        -------
            A list of Shapely ellipses.

        References
        ----------
        http://stackoverflow.com/questions/12301071/multidimensional-confidence-intervals
        http://stackoverflow.com/questions/15445546/finding-intersection-points-of-two-ellipses-python
        """
        if self.ndims != 2:
            raise ValueError("Only works for 2-dimensional Gaussian mixtures.")

        def eigsorted(cov):
            """Get 
            """
            vals, vecs = np.linalg.eigh(cov)
            order = vals.argsort()[::-1]
            return vals[order], vecs[:,order]

        ellipses = []

        # Find discrete sin/cos of t
        t = np.linspace(0, 2 * np.pi, resolution, endpoint=False)
        st = np.sin(t)
        ct = np.cos(t)

        # Generate all ellipses
        for i, mean in enumerate(self.means):

            # Use eigenvals/vects to get major/minor axes 
            eigvals, eigvects = eigsorted(self.covariances[i])
            a, b = 2 * num_std * np.sqrt(eigvals)

            # Find discrete sin/cos of theta
            theta = np.arctan2(*eigvects[:,0][::-1])
            sth = np.sin(theta)
            cth = np.cos(theta)

            # Find all ellipse points and turn into a Shapely Polygon
            ellipse_pts = np.empty((resolution, 2))
            x0, y0 = mean[0], mean[1]
            ellipse_pts[:, 0] = x0 + a * cth * ct - b * sth * st
            ellipse_pts[:, 1] = y0 + a * sth * ct + b * cth * st
            ellipse = Polygon(ellipse_pts)

            ellipses.append(ellipse)
        return ellipses

    def plot_ellipses(self, ax=None, lw=20, poly=None, **kwargs):
        if ax is None:
            ax = plt.gca()

        ellipses = self.std_ellipses(**kwargs)
        ellipse_patches = []
        for i, ellipse in enumerate(ellipses):
            if poly is not None:
                if poly.intersects(ellipse):
                    ec = 'white'
                else:
                    ec = 'black'
            else:
                ec = 'black'
            patch = PolygonPatch(ellipse, facecolor='none', edgecolor=ec,
                                 linewidth=self.weights[i] * lw,
                                 zorder=15)
            ax.add_patch(patch)
            ellipse_patches.append(patch)
        return ellipse_patches

    def entropy(self):
        """
        """
        # <>TODO: figure this out. Look at papers!
        # http://www-personal.acfr.usyd.edu.au/tbailey/papers/mfi08_huber.pdf
        pass

    def _input_check(self):
        # Check if weights sum are normalized
        try:
            new_weights = self.weights / np.sum(self.weights)
            assert np.array_equal(self.weights, new_weights)
        except AssertionError, e:
            self.weights = new_weights
            logging.debug("Weights renormalized to {}".format(self.weights))

        # Check if weights sum to 1
        try:
            a = np.sum(self.weights)
            assert np.isclose(np.ones(1), a)
        except AssertionError, e:
            logging.exception('Weights sum to {}, not 1.'.format(a))
            raise e

        # Identify dimensionality
        if self.means.ndim == 0:  # single Univariate gaussian
            self.ndims = 1
            self.weights = np.array([self.weights])
        elif self.means.ndim == 1 and self.weights.size == 1:
            # single multivariate gaussian
            self.ndims = self.means.shape[0]
            self.weights = np.array([self.weights])
        elif self.means.ndim == 1:  # multiple univariate gaussians
            self.ndims = 1
        elif self.means.ndim == 2:  # multiple multivariate gaussians
            self.ndims = self.means.shape[1]

        # Properly format means
        try:
            self.means = self.means.reshape(self.weights.size, self.ndims)
        except ValueError, e:
            logging.exception('Means and weights don\'t agree.')
            raise e

        # Properly format covariances
        try:
            self.covariances = self.covariances.reshape(self.weights.size,
                                                        self.ndims, self.ndims)
        except ValueError, e:
            logging.exception('Covariances and weights don\'t agree.')
            raise e

        # Check if means correspond to variance dimensions
        for i, mean in enumerate(self.means):
            var = self.covariances[i]
            try:
                assert mean.size == var.shape[0]
                assert mean.size == var.shape[1]
            except AssertionError, e:
                logging.exception('Mean {} doesn\'t correspond to variance:'
                                  ' \n{}'.format(mean, var))
                raise e

        # Ensure all variances are positive
        for i, var in enumerate(self.covariances):
            self.covariances[i] = np.abs(var)

        # Check if covariances are positive semidefinite
        for var in self.covariances:
            try:
                assert np.all(np.linalg.det(var) > 0)
            except AssertionError, e:
                logging.warn('Following variance is not positive '
                                  'semidefinite: \n{}'.format(var))
                var = np.eye(self.ndims) * 10 ** -3

        # Check if covariances are symmetric
        for var in self.covariances:
            try:
                tol = 10 ** -6
                a = np.ones_like(var) * tol
                assert np.less(var.T - var, a).all()
            except AssertionError, e:
                logging.exception('Following variance is not symmetric: \n{} '
                                  .format(var))
                raise e

        # Merge if necessary
        self._merge()

    def _merge(self, max_num_mixands=None):
        """
        """
        if max_num_mixands is None:
            max_num_mixands = self.max_num_mixands

        # Check if merging is useful
        num_mixands = self.weights.size
        if num_mixands <= max_num_mixands:
            logging.debug('No need to merge {} mixands.'
                          .format(num_mixands))
            return
        else:
            logging.debug('Merging {} mixands down to {}.'
                          .format(num_mixands, self.max_num_mixands))

        # Create lower-triangle of dissimilarity matrix B
        #<>TODO: this is O(n ** 2) and very slow. Speed it up! parallelize?
        B = np.zeros((num_mixands, num_mixands))
        for i in range(num_mixands):
            mix_i = (self.weights[i], self.means[i], self.covariances[i])
            for j in range(i):
                if i == j:
                    continue
                mix_j = (self.weights[j], self.means[j], self.covariances[j])
                B[i,j] = mixand_dissimilarity(mix_i, mix_j)

        # Keep merging until we get the right number of mixands
        deleted_mixands = []
        while num_mixands > max_num_mixands:
            # Find most similar mixands
            try:
                #<>TODO: replace with infinities, not 0
                min_B = B[B>0].min()
            except ValueError, e:
                logging.error('Could not find a minimum value in B: \n{}'
                              .format(B))
                raise e
            ind = np.where(B==min_B)
            i, j = ind[0][0], ind[1][0]

            # Get merged mixand
            mix_i = (self.weights[i], self.means[i], self.covariances[i])
            mix_j = (self.weights[j], self.means[j], self.covariances[j])
            w_ij, mu_ij, P_ij = merge_mixands(mix_i, mix_j)

            # Replace mixand i with merged mixand
            ij = i
            self.weights[ij] = w_ij
            self.means[ij] = mu_ij
            self.covariances[ij] = P_ij

            # Fill mixand i's B values with new mixand's B values
            mix_ij = (w_ij, mu_ij, P_ij)
            deleted_mixands.append(j)
            for k in range(B.shape[0]):
                if k == ij or k in deleted_mixands:
                    continue

                # Only fill lower triangle
                mix_k = (self.weights[k], self.means[k], self.covariances[k])
                if k < i:
                    B[ij,k] = mixand_dissimilarity(mix_k, mix_ij)
                else:
                    B[k,ij] = mixand_dissimilarity(mix_k, mix_ij)

            # Remove mixand j from B
            B[j,:] = np.inf
            B[:,j] = np.inf
            num_mixands -= 1

        # Delete removed mixands from parameter arrays
        self.weights = np.delete(self.weights, deleted_mixands, axis=0)
        self.means = np.delete(self.means, deleted_mixands, axis=0)
        self.covariances = np.delete(self.covariances, deleted_mixands, axis=0)

def merge_mixands(mix_i, mix_j):
    """Use moment-preserving merge (0th, 1st, 2nd moments) to combine mixands.
    """
    # Unpack mixands
    w_i, mu_i, P_i = mix_i
    w_j, mu_j, P_j = mix_j

    # Merge weights
    w_ij = w_i + w_j
    w_i_ij = w_i / (w_i + w_j)
    w_j_ij = w_j / (w_i + w_j)

    # Merge means
    mu_ij = w_i_ij * mu_i + w_j_ij * mu_j

    # Merge covariances
    P_ij = w_i_ij * P_i + w_j_ij * P_j + \
        w_i_ij * w_j_ij * np.outer(mu_i - mu_j, mu_i - mu_j)

    return w_ij, mu_ij, P_ij


def mixand_dissimilarity(mix_i, mix_j):
    """Calculate KL descriminiation-based dissimilarity between mixands.
    """
    # Get covariance of moment-preserving merge
    w_i, mu_i, P_i = mix_i
    w_j, mu_j, P_j = mix_j
    _, _, P_ij = merge_mixands(mix_i, mix_j)

    # Use slogdet to prevent over/underflow
    _, logdet_P_ij = np.linalg.slogdet(P_ij)
    _, logdet_P_i = np.linalg.slogdet(P_i)
    _, logdet_P_j = np.linalg.slogdet(P_j)
    
    # <>TODO: check to see if anything's happening upstream
    if np.isinf(logdet_P_ij):
        logdet_P_ij = 0
    if np.isinf(logdet_P_i):
        logdet_P_i = 0
    if np.isinf(logdet_P_j):
        logdet_P_j = 0

    b = 0.5 * ((w_i + w_j) * logdet_P_ij - w_i * logdet_P_i - w_j * logdet_P_j)
    return b


def pdf_test():
    fig = plt.figure()

    # Setup spaces
    x = np.linspace(-5, 5, 100)
    xx, yy = np.mgrid[-5:5:1 / 100,
                      -5:5:1 / 100]
    pos = np.empty(xx.shape + (2,))
    pos[:, :, 0] = xx
    pos[:, :, 1] = yy

    # 1D Gaussian
    gauss_1d = GaussianMixture(1, 3, 0.4)
    ax = fig.add_subplot(221)
    ax.plot(x, gauss_1d.pdf(x), lw=2)
    ax.fill_between(x, 0, gauss_1d.pdf(x), alpha=0.2)
    ax.set_title('1D Gaussian PDF')

    # 2D Gaussian
    gauss_2d = GaussianMixture(weights=1,
                               means=[3, 2],
                               covariances=[[[0.4, 0.3],
                                             [0.3, 0.4]
                                             ],
                                            ])
    ax = fig.add_subplot(222)

    # 2D Gaussian probs
    states = [[0,0],[1,1],[3,3],[4,4]]

    levels = np.linspace(0, np.max(gauss_2d.pdf(pos)), 50)
    ax.contourf(xx, yy, gauss_2d.pdf(pos), levels=levels, cmap=plt.get_cmap('jet'))
    ax.set_title('2D Gaussian PDF')

    # 1D Gaussian Mixutre
    gm_1d = GaussianMixture(weights=[1, 4, 5],
                            means=[3, -3, 1],
                            covariances=[0.4, 0.3, 0.5],
                            )
    ax = fig.add_subplot(223)
    ax.plot(x, gm_1d.pdf(x), lw=2)
    ax.fill_between(x, 0, gm_1d.pdf(x), alpha=0.2,)
    ax.set_title('1D Gaussian Mixture PDF')

    # 2D Gaussian Mixutre
    gm_2d = GaussianMixture(weights=[1, 4, 5],
                            means=[[3, 2],  # GM1 mean
                                   [-3, 4],  # GM2 mean
                                   [1, -1],  # GM3 mean
                                   ],
                            covariances=[[[0.4, 0.3],  # GM1 mean
                                          [0.3, 0.4]
                                          ],
                                         [[0.3, 0.1],  # GM2 mean
                                          [0.1, 0.3]
                                          ],
                                         [[0.5, 0.4],  # GM3 mean
                                          [0.4, 0.5]],
                                         ])
    ax = fig.add_subplot(224)
    levels = np.linspace(0, np.max(gm_2d.pdf(pos)), 50)
    ax.contourf(xx, yy, gm_2d.pdf(pos), levels=levels, cmap=plt.get_cmap('jet'))
    ax.set_title('2D Gaussian Mixture PDF')

    plt.tight_layout()
    plt.show()


def rv_test():
    fig = plt.figure()
    samps_1d = 10000
    samps_2d = 1000000

    # 1D Gaussian
    gauss_1d = GaussianMixture(1, 3, 0.4)
    rvs = gauss_1d.rvs(samps_1d)
    ax = fig.add_subplot(221)
    ax.hist(rvs, histtype='stepfilled', normed=True, alpha=0.2, bins=100)
    ax.set_title('1D Gaussian Samples')

    # 2D Gaussian
    gauss_2d = GaussianMixture(weights=1,
                               means=[3, 2],
                               covariances=[[[0.4, 0.3],
                                             [0.3, 0.4]
                                             ],
                                            ])
    ax = fig.add_subplot(222)
    rvs = gauss_2d.rvs(samps_2d)
    ax.hist2d(rvs[:, 0], rvs[:, 1], bins=50)
    ax.set_title('2D Gaussian Samples')

    # 1D Gaussian Mixutre
    gm_1d = GaussianMixture(weights=[1, 4, 5],
                            means=[3, -3, 1],
                            covariances=[0.4, 0.3, 0.5],
                            )
    rvs = gm_1d.rvs(samps_1d)
    ax = fig.add_subplot(223)
    ax.hist(rvs, histtype='stepfilled', normed=True, alpha=0.2, bins=100)
    ax.set_title('1D Gaussian Mixture Samples')

    # 2D Gaussian Mixutre
    gm_2d = GaussianMixture(weights=[1, 4, 5],
                            means=[[3, 2],  # GM1 mean
                                   [-3, 4],  # GM2 mean
                                   [1, -1],  # GM3 mean
                                   ],
                            covariances=[[[0.4, 0.3],  # GM1 mean
                                          [0.3, 0.4]
                                          ],
                                         [[0.3, 0.1],  # GM2 mean
                                          [0.1, 0.3]
                                          ],
                                         [[0.5, 0.4],  # GM3 mean
                                          [0.4, 0.5]],
                                         ])
    ax = fig.add_subplot(224)
    rvs = gm_2d.rvs(samps_2d)
    ax.hist2d(rvs[:, 0], rvs[:, 1], bins=50)
    ax.set_title('2D Gaussian Mixture Samples')

    plt.tight_layout()
    plt.show()


def ellipses_test(num_std=2):
    # 2D Gaussian
    gauss_2d = GaussianMixture(weights=[32,
                                        14,
                                        15,
                                        14,
                                        14,
                                        14],
                                means=[[-5.5, 2],  # Kitchen
                                       [2, 2],  # Billiard Room
                                       [-4, -0.5],  # Hallway
                                       [-9, -2.5],  # Dining Room
                                       [-4, -2.5],  # Study
                                       [1.5, -2.5],  # Library
                                       ],
                                covariances=[[[5.0, 0.0],  # Kitchen
                                              [0.0, 2.0]
                                              ],
                                             [[1.0, 0.0],  # Billiard Rooom
                                              [0.0, 2.0]
                                              ],
                                             [[7.5, 0.0],  # Hallway
                                              [0.0, 0.5]
                                              ],
                                             [[2.0, 0.0],  # Dining Room
                                              [0.0, 1.0]
                                              ],
                                             [[2.0, 0.0],  # Study
                                              [0.0, 1.0]
                                              ],
                                             [[2.0, 0.0],  # Library
                                              [0.0, 1.0]
                                              ],
                                             ])

    ellipses = gauss_2d.std_ellipses(num_std)

    fig = plt.figure()
    ax = fig.add_subplot(111)

    for i, ellipse in enumerate(ellipses):
        patch = PolygonPatch(ellipse, facecolor=gauss_2d.ellipse_color,
                             alpha=gauss_2d.weights[i])
        ax.add_patch(patch)

    ax.set_xlim([-15, 5])
    ax.set_ylim([-5, 5])
    plt.show()


def fleming_prior():
    return GaussianMixture(weights=[32,
                                        14,
                                        15,
                                        14,
                                        14,
                                        14],
                                means=[[-5.5, 2],  # Kitchen
                                       [2, 2],  # Billiard Room
                                       [-4, -0.5],  # Hallway
                                       [-9, -2.5],  # Dining Room
                                       [-4, -2.5],  # Study
                                       [1.5, -2.5],  # Library
                                       ],
                                covariances=[[[5.0, 0.0],  # Kitchen
                                              [0.0, 2.0]
                                              ],
                                             [[1.0, 0.0],  # Billiard Rooom
                                              [0.0, 2.0]
                                              ],
                                             [[7.5, 0.0],  # Hallway
                                              [0.0, 0.5]
                                              ],
                                             [[2.0, 0.0],  # Dining Room
                                              [0.0, 1.0]
                                              ],
                                             [[2.0, 0.0],  # Study
                                              [0.0, 1.0]
                                              ],
                                             [[2.0, 0.0],  # Library
                                              [0.0, 1.0]
                                              ],
                                             ])


def uniform_prior(num_mixands=10, bounds=None):
    if bounds is None:
        bounds = [-5, -5, 5, 5]

    n = np.int(np.sqrt(num_mixands))
    num_mixands = n ** 2
    weights = np.ones(num_mixands)
    mu_x = np.linspace(bounds[0], bounds[2], num=n)
    mu_y = np.linspace(bounds[1], bounds[3], num=n)
    mu_xx, mu_yy = np.meshgrid(mu_x, mu_y)
    means = np.dstack((mu_xx, mu_yy)).reshape(-1,2)
    covariances = np.ones((num_mixands,2,2)) * 1000
    for i, cov in enumerate(covariances):
        covariances[i] = cov - np.roll(np.eye(2), 1, axis=0) * 1000

    return GaussianMixture(weights, means, covariances)


def fleming_prior_test():
    fig = plt.figure()

    bounds = [-12.5, -3.5, 2.5, 3.5]
    # Setup spaces
    res = 1/100
    xx, yy = np.mgrid[bounds[0]:bounds[2]:res,
                      bounds[1]:bounds[3]:res,
                      ]
    pos = np.empty(xx.shape + (2,))
    pos[:, :, 0] = xx
    pos[:, :, 1] = yy

    # 2D Gaussian
    gauss_2d = fleming_prior()
    ax = fig.add_subplot(111)
    levels = np.linspace(0, np.max(gauss_2d.pdf(pos)), 50)
    cax = ax.contourf(xx, yy, gauss_2d.pdf(pos), levels=levels, cmap=plt.get_cmap('jet'))
    ax.set_title('2D Gaussian PDF')
    fig.colorbar(cax)

    plt.axis('scaled')
    ax.set_xlim(bounds[0:3:2])
    ax.set_ylim(bounds[1:4:2])
    plt.show()
    print os.system("say '{}'".format(gauss_2d))


def uniform_prior_test(num_mixands=10, bounds=None):
    if bounds is None:
        bounds = [-5, -5, 5, 5]

    fig = plt.figure()
    ax = fig.add_subplot(111)

    # Setup spaces
    res = 1/100
    xx, yy = np.mgrid[bounds[0]:bounds[2]:res,
                      bounds[1]:bounds[3]:res,
                      ]
    pos = np.empty(xx.shape + (2,))
    pos[:, :, 0] = xx
    pos[:, :, 1] = yy

    gauss_2d = uniform_prior()
    levels = np.linspace(0, np.max(gauss_2d.pdf(pos)), 50)
    cax = ax.contourf(xx, yy, gauss_2d.pdf(pos), levels=levels, cmap=plt.get_cmap('jet'))
    ax.set_title('2D Gaussian PDF')
    fig.colorbar(cax)

    plt.axis('scaled')
    ax.set_xlim(bounds[0:3:2])
    ax.set_ylim(bounds[1:4:2])
    plt.show()


def merge_test(num_mixands=10, max_num_mixands=None, spread=4, speak=False):
    if max_num_mixands is None:
        animate = True
        max_num_mixands = num_mixands
    else:
        animate = False

    weights = np.random.uniform(size=num_mixands)
    means = np.random.randn(num_mixands, 2) * spread
    covariances = np.abs(np.random.randn(num_mixands,2, 2))
    for i, covariance in enumerate(covariances):
        s = np.sort(covariance, axis=None)
        covariance[0,1] = s[0]
        covariance[1,0] = s[1]
        if int(s[3] * 100000) % 2:
            covariance[0,0] = s[3]
            covariance[1,1] = s[2]
        else:
            covariance[0,0] = s[2]
            covariance[1,1] = s[3]
        covariances[i] = (covariance + covariance.T)/2

    unmerged_gauss_2d = GaussianMixture(weights, means, covariances,
                                        max_num_mixands=len(weights))
    merged_gauss_2d = GaussianMixture(weights, means, covariances,
                                      max_num_mixands=max_num_mixands)

    # Setup spaces
    xx, yy = np.mgrid[-10:10:1 / 10,
                      -10:10:1 / 10]
    pos = np.empty(xx.shape + (2,))
    pos[:, :, 0] = xx
    pos[:, :, 1] = yy

    fig = plt.figure(figsize=(14,6))
    ax = fig.add_subplot(121)
    max_prob = np.maximum(np.max(unmerged_gauss_2d.pdf(pos)),
                          np.max(merged_gauss_2d.pdf(pos)))

    levels = np.linspace(0, max_prob * 1.2, 50)
    c = ax.contourf(xx, yy, unmerged_gauss_2d.pdf(pos), levels=levels, cmap=plt.get_cmap('jet'))
    ax.set_title('Unmerged GM ({} mixands)'.format(unmerged_gauss_2d.weights.size))

    fig.subplots_adjust(right=0.85)
    cbar_ax = fig.add_axes([0.875, 0.1, 0.025, 0.8])
    fig.colorbar(c, cax=cbar_ax)

    class merged_gm(object):
        """docstring for merged_gm"""
        def __init__(self, ax, max_num_mixands, xx, yy, pos, levels,
                     weights,means,covariances, rate=2, speak=False):
            self.ax = ax
            self.xx = xx
            self.yy = yy
            self.pos = pos
            self.levels = levels
            self.max_num_mixands = max_num_mixands
            self.num_mixands = 1
            self.weights = weights
            self.means = means
            self.covariances = covariances
            self.rate = rate
            self.speak = speak
    
        def update(self,i=0):
            self.gm = GaussianMixture(self.weights, self.means, self.covariances,
                                 max_num_mixands=self.num_mixands)
            self.remove()
            if self.speak:
                os.system("say '{}'".format(self.num_mixands))
            self.plot()
            
            if self.num_mixands == self.max_num_mixands:
                self.num_mixands = 1
            elif np.int(self.num_mixands * self.rate) < self.max_num_mixands:
                self.num_mixands = np.int(self.num_mixands * self.rate)
            else:
                self.num_mixands = self.max_num_mixands

        def plot(self):
            self.contourf = self.ax.contourf(self.xx, self.yy,
                                               self.gm.pdf(pos),
                                               levels=self.levels,
                                               cmap=plt.get_cmap('jet')
                                               )
            self.ax.set_title('Merged GM ({} mixands)'
                              .format(self.num_mixands))

        def remove(self):
            if hasattr(self,'contourf'):
                for collection in self.contourf.collections:
                    collection.remove()
                del self.contourf

    if animate:
        ax = fig.add_subplot(122)
        gm = merged_gm(ax, max_num_mixands, xx, yy, pos, levels,
                       weights,means,covariances,speak=speak)
        ani = animation.FuncAnimation(fig, gm.update, 
            interval=1,
            repeat=True,
            blit=False,
            )
    else:
        ax = fig.add_subplot(122)
        gm = merged_gm(ax, max_num_mixands, xx, yy, pos, levels,
                       weights,means,covariances,speak=False)
        gm.update()
        gm.plot()

    plt.show()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # pdf_test()
    # rv_test()
    # fleming_prior_test()
    
    # fp = fleming_prior()
    # new_fp = fp.copy()
    # new_fp.weights = np.ones(6)
    # print fp
    # ellipses_test(2)
    merge_test(120, speak=False)
    # uniform_prior_test()
