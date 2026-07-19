"""Regression test for the BayesPrism ThetaPost shape-mismatch bug
reported in omicverse/omicverse#612.

Before the fix, ``run_gibbs_refPhi`` passed ``self.X.columns`` (= gene
names, shape n_genes) to ``ThetaPost.new`` as the ``cell_type`` argument.
The resulting ``theta`` buffer had shape ``(n_bulk, n_genes)``, but the
Gibbs sampler returned ``theta_n`` of shape ``(n_cell_types,)`` for each
sample — producing::

    ValueError: could not broadcast input array from shape (K,) into shape (G,)

This test builds a tiny synthetic reference + pseudobulk, runs
``my_prism.run(fast_mode=False)``, and checks that the returned theta
has the right orientation (samples × cell types) and sums to 1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import anndata as ad


def _synthetic_ref_and_bulk(seed: int = 0):
    """Three cell types × 150 genes; each type has a 40-gene high-expression
    block so the reference is identifiable. Pseudobulk is
    ``sum(80 T + 60 B + 60 M)`` random ref-cells → expected proportions
    40 / 30 / 30 %."""
    rng = np.random.default_rng(seed)
    n_per = 70
    n_genes = 150
    n_bulk = 6

    cell_types = np.array(["T"] * n_per + ["B"] * n_per + ["M"] * n_per)
    X_ref = rng.poisson(4.0, size=(3 * n_per, n_genes)).astype(np.float64)
    for i, ct in enumerate(["T", "B", "M"]):
        mask = cell_types == ct
        X_ref[mask, i * 40:(i + 1) * 40] += rng.poisson(
            60, size=(mask.sum(), 40)
        )
    adata_ref = ad.AnnData(
        X=X_ref,
        obs=pd.DataFrame(
            {"celltype": cell_types},
            index=[f"c{i}" for i in range(3 * n_per)],
        ),
        var=pd.DataFrame(index=[f"g{j}" for j in range(n_genes)]),
    )

    mix = np.zeros((n_bulk, n_genes))
    for s in range(n_bulk):
        pick = np.concatenate([
            rng.choice(np.where(cell_types == "T")[0], size=80),
            rng.choice(np.where(cell_types == "B")[0], size=60),
            rng.choice(np.where(cell_types == "M")[0], size=60),
        ])
        mix[s] = X_ref[pick].sum(axis=0)
    mixture = pd.DataFrame(
        mix,
        index=[f"s{i}" for i in range(n_bulk)],
        columns=adata_ref.var_names,
    )
    return adata_ref, mixture


class TestBayesPrismThetaShape:
    def test_final_theta_is_samples_by_celltypes(self):
        """Regression for omicverse/omicverse#612: theta dataframe
        returned by BayesPrism must be indexed by bulk samples and
        columned by reference cell types, not genes."""
        from omicverse.external.bulk2single.pybayesprism.prism import Prism

        adata_ref, mixture = _synthetic_ref_and_bulk(seed=0)
        my_prism = Prism.new_anndata(
            reference_adata=adata_ref, mixture=mixture,
            cell_type_key="celltype", cell_state_key="celltype",
            key=None, outlier_cut=0.5, outlier_fraction=0.01,
        )
        bp = my_prism.run(n_cores=2, fast_mode=False)
        theta = bp.posterior_theta_f.theta

        # Dimensions: samples × cell types, not samples × genes
        assert theta.shape[0] == mixture.shape[0]
        assert theta.shape[1] == 3
        assert list(theta.columns) == ["T", "B", "M"]
        assert list(theta.index) == list(mixture.index)

        # Compositional constraint: every sample's proportions sum to ~1
        np.testing.assert_allclose(
            theta.sum(axis=1).to_numpy(), 1.0, atol=0.01,
        )

    def test_recovers_planted_proportions(self):
        """Known mix 40/30/30 should be recovered to within ±5 pp."""
        from omicverse.external.bulk2single.pybayesprism.prism import Prism

        adata_ref, mixture = _synthetic_ref_and_bulk(seed=1)
        my_prism = Prism.new_anndata(
            reference_adata=adata_ref, mixture=mixture,
            cell_type_key="celltype", cell_state_key="celltype",
            key=None, outlier_cut=0.5, outlier_fraction=0.01,
        )
        bp = my_prism.run(n_cores=2, fast_mode=False)
        theta = bp.posterior_theta_f.theta
        mean = theta.mean(axis=0)
        assert abs(mean["T"] - 0.40) < 0.05, mean
        assert abs(mean["B"] - 0.30) < 0.05, mean
        assert abs(mean["M"] - 0.30) < 0.05, mean
