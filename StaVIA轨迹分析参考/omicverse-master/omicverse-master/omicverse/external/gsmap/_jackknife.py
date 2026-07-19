from __future__ import annotations

import numpy as np


def _check_shape(x, y):
    """Check that x and y have the correct shapes."""

    if len(x.shape) != 2 or len(y.shape) != 2:
        raise ValueError("x and y must be 2D arrays.")
    if x.shape[0] != y.shape[0]:
        raise ValueError("Number of datapoints in x != number of datapoints in y.")
    if y.shape[1] != 1:
        raise ValueError("y must have shape (n_snp, 1)")
    n_row, n_col = x.shape
    if n_col > n_row:
        raise ValueError("More dimensions than datapoints.")
    return n_row, n_col


class Jackknife:
    """Base class for block jackknife objects."""

    def __init__(self, x, y, n_blocks=None, separators=None):
        self.n_row, self.n_col = _check_shape(x, y)
        if separators is not None:
            self.separators = sorted(separators)
            self.n_blocks = len(separators) - 1
        elif n_blocks is not None:
            self.n_blocks = n_blocks
            self.separators = self.get_separators(self.n_row, self.n_blocks)
        else:
            raise ValueError("Must specify either n_blocks are separators.")

        if self.n_blocks > self.n_row:
            raise ValueError("More blocks than data points.")

    @classmethod
    def jknife(cls, pseudovalues):
        """Convert pseudovalues to jackknife estimates."""

        n_blocks = pseudovalues.shape[0]
        jknife_cov = np.atleast_2d(np.cov(pseudovalues.T, ddof=1) / n_blocks)
        jknife_var = np.atleast_2d(np.diag(jknife_cov))
        jknife_se = np.atleast_2d(np.sqrt(jknife_var))
        jknife_est = np.atleast_2d(np.mean(pseudovalues, axis=0))
        return jknife_est, jknife_var, jknife_se, jknife_cov

    @classmethod
    def delete_values_to_pseudovalues(cls, delete_values, est):
        """Convert whole-data estimate and delete values to pseudovalues."""

        n_blocks, n_col = delete_values.shape
        if est.shape != (1, n_col):
            raise ValueError("Different number of parameters in delete_values than in est.")
        return n_blocks * est - (n_blocks - 1) * delete_values

    @classmethod
    def get_separators(cls, n_row, n_blocks):
        """Define evenly spaced block boundaries."""

        return np.floor(np.linspace(0, n_row, n_blocks + 1)).astype(int)


class LstsqJackknifeFast(Jackknife):
    """Fast linear-regression block jackknife."""

    def __init__(self, x, y, n_blocks=None, separators=None):
        # Numerical failures are meaningful for the jackknife calculation, but
        # must not alter NumPy's process-wide error policy when this module is
        # imported by an application or test suite.
        with np.errstate(divide="raise", invalid="raise"):
            super().__init__(x, y, n_blocks=n_blocks, separators=separators)
            xty_block_values, xtx_block_values = self.block_values(x, y, self.separators)
            self.est = self.block_values_to_est(xty_block_values, xtx_block_values)
            self.delete_values = self.block_values_to_delete_values(xty_block_values, xtx_block_values)
            self.pseudovalues = self.delete_values_to_pseudovalues(self.delete_values, self.est)
            (self.jknife_est, self.jknife_var, self.jknife_se, self.jknife_cov) = self.jknife(
                self.pseudovalues
            )

    @classmethod
    def block_values(cls, x, y, separators):
        """Compute per-block xty and xtx values."""

        n_blocks = len(separators) - 1
        n_col = x.shape[1]
        xty_block_values = np.zeros((n_blocks, n_col))
        xtx_block_values = np.zeros((n_blocks, n_col, n_col))
        for block_index in range(n_blocks):
            start = separators[block_index]
            end = separators[block_index + 1]
            x_block = x[start:end]
            y_block = y[start:end]
            xty_block_values[block_index] = np.dot(x_block.T, y_block).reshape(-1)
            xtx_block_values[block_index] = np.dot(x_block.T, x_block)
        return xty_block_values, xtx_block_values

    @classmethod
    def block_values_to_est(cls, xty_block_values, xtx_block_values):
        """Estimate coefficients from summed block values."""

        xty_tot = xty_block_values.sum(axis=0)
        xtx_tot = xtx_block_values.sum(axis=0)
        return np.atleast_2d(np.linalg.solve(xtx_tot, xty_tot)).reshape(1, -1)

    @classmethod
    def block_values_to_delete_values(cls, xty_block_values, xtx_block_values):
        """Compute delete-one-block coefficient estimates."""

        xty_tot = xty_block_values.sum(axis=0)
        xtx_tot = xtx_block_values.sum(axis=0)
        delete_values = np.zeros_like(xty_block_values)
        for block_index in range(xty_block_values.shape[0]):
            xty_delete = xty_tot - xty_block_values[block_index]
            xtx_delete = xtx_tot - xtx_block_values[block_index]
            delete_values[block_index] = np.linalg.solve(xtx_delete, xty_delete)
        return delete_values
