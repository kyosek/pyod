"""Copula Based Outlier Detector (COPOD)
"""
# Author: Zheng Li <jk_zhengli@hotmail.com>
# License: BSD 2 clause

from __future__ import division
from __future__ import print_function

import numpy as np
import pandas as pd
from pyod.models.base import BaseDetector
from statsmodels.distributions.empirical_distribution import ECDF
from scipy.stats import skew
from sklearn.utils import check_array
import matplotlib.pyplot as plt

class COPOD(BaseDetector):
    """COPOD class for Copula Based Outlier Detector.
    COPOD is a parameter-free, highly interpretable outlier detection algorithm
    based on empirical copula models.
    See :cite:`li2020copod` for details.

    Parameters
    ----------
    contamination : float in (0., 0.5), optional (default=0.1)
        The amount of contamination of the data set, i.e.
        the proportion of outliers in the data set. Used when fitting to
        define the threshold on the decision function.

    Attributes
    ----------
    decision_scores_ : numpy array of shape (n_samples,)
        The outlier scores of the training data.
        The higher, the more abnormal. Outliers tend to have higher
        scores. This value is available once the detector is
        fitted.
    threshold_ : float
        The threshold is based on ``contamination``. It is the
        ``n_samples * contamination`` most abnormal samples in
        ``decision_scores_``. The threshold is calculated for generating
        binary outlier labels.
    labels_ : int, either 0 or 1
        The binary labels of the training data. 0 stands for inliers
        and 1 for outliers/anomalies. It is generated by applying
        ``threshold_`` on ``decision_scores_``.
    """

    def __init__(self, contamination=0.1):
        super(COPOD, self).__init__(contamination=contamination)

    def ecdf(self, X):
        """Calculated the empirical CDF of a given dataset.
        Parameters
        ----------
        X : numpy array of shape (n_samples, n_features)
            The training dataset.
        Returns
        -------
        ecdf(X) : float
            Empirical CDF of X
        """
        ecdf = ECDF(X)
        return ecdf(X)

    def fit(self, X, y=None):
        """Fit detector. y is ignored in unsupervised methods.
        Parameters
        ----------
        X : numpy array of shape (n_samples, n_features)
            The input samples.
        y : Ignored
            Not used, present for API consistency by convention.
        Returns
        -------
        self : object
            Fitted estimator.
        """
        X = check_array(X)
        self._set_n_classes(y=None)
        self.X_train = X
        self.decision_function(X)

    def decision_function(self, X):
        """Predict raw anomaly score of X using the fitted detector.
         For consistency, outliers are assigned with larger anomaly scores.
        Parameters
        ----------
        X : numpy array of shape (n_samples, n_features)
            The training input samples. Sparse matrices are accepted only
            if they are supported by the base estimator.
        Returns
        -------
        anomaly_scores : numpy array of shape (n_samples,)
            The anomaly score of the input samples.
        """

        if hasattr(self, 'X_train'):
            original_size = X.shape[0]
            X = np.concatenate((self.X_train, X), axis=0)
        size = X.shape[0]
        dim = X.shape[1]
        self.U_l = pd.DataFrame(-1*np.log(np.apply_along_axis(self.ecdf, 0, X)))
        self.U_r = pd.DataFrame(-1*np.log(np.apply_along_axis(self.ecdf, 0, -X)))
        skewness = np.sign(np.apply_along_axis(skew, 0, X))
        self.U_skew = self.U_l * -1*np.sign(skewness - 1) + self.U_r * np.sign(skewness + 1)
        self.O = np.maximum(self.U_skew, np.add(self.U_l, self.U_r)/2)
        if hasattr(self, 'X_train'):
            self.decision_scores_ = self.O.sum(axis=1).to_numpy()[-original_size:]
        else:
            self.decision_scores_ = self.O.sum(axis=1).to_numpy()
        self.threshold_ = np.percentile(self.decision_scores_, (1-self.contamination)*100)
        self.labels_ = np.zeros(len(self.decision_scores_))
        for i in range(len(self.decision_scores_)):
            self.labels_[i] = 1 if self.decision_scores_[i] >= self.threshold_ else 0
        return self.decision_scores_

    def explain_outlier(self, ind, cutoffs=None):
        """Plot dimensional outlier graph for a given data
            point within the dataset.
        Parameters
        ----------
        ind : int
            The index of the data point one wishes to obtain
            a dimensional outlier graph for.
        
        cutoffs : list of floats in (0., 1), optional (default=[0.95, 0.99])
            The significance cutoff bands of the dimensional outlier graph.
        
        Returns
        -------
        Plot : matplotlib plot
            The dimensional outlier graph for data point with index ind.
        """
        cutoffs = [1-self.contamination, 0.99] if cutoffs is None else cutoffs
        plt.plot(range(1, self.O.shape[1] + 1), self.O.iloc[ind], label='Outlier Score')
        for i in cutoffs:
            plt.plot(range(1, self.O.shape[1] + 1), self.O.quantile(q=i, axis=0), '-', label='{percentile} Cutoff Band'.format(percentile=i))
        plt.xlim([1, self.O.shape[1] + 1])
        plt.ylim([0, int(self.O.max().max()) + 1])
        plt.ylabel('Dimensional Outlier Score')
        plt.xlabel('Dimension')
        plt.xticks(range(1, self.O.shape[1] + 1))
        plt.yticks(range(0, int(self.O.max().max()) + 1))
        label = 'Outlier' if self.labels_[ind] == 1 else 'Inlier'
        plt.title('Outlier Score Breakdown for Data #{index} ({label})'.format(index=ind+1, label=label))
        plt.legend()
        plt.show()
        return self.O.iloc[ind], self.O.quantile(q=cutoffs[0], axis=0), self.O.quantile(q=cutoffs[1], axis=0)