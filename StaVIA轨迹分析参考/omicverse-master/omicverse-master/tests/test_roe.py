"""Tests for ov.utils.roe — Ro/e (observed/expected) tissue-preference analysis.

Covers the fixed implementation:
- Ro/e = observed / chi-square-expected (Zhang 2018 / Startrac formula).
- The full Ro/e matrix is ALWAYS returned (the global p-value is a QC flag,
  not a gate).
- Results stored in adata.uns['roe'] (dict) + back-compat keys
  adata.uns['roe_results'] / adata.uns['expected_values'].
- Symbolic schemes: 'anchored' (default, breakpoints 0.2 / 1 / 3) and
  'legacy' (breakpoints 0.2 / 0.8 / 1).
- Empty cell types / samples are dropped before the chi-square test.
"""

import contextlib
import io

import numpy as np
import pandas as pd
import anndata as ad
import pytest
from scipy.stats import chi2_contingency

import omicverse as ov


class TestROE:
    """Test suite for ov.utils.roe."""

    @pytest.fixture
    def sample_adata_large(self):
        """1000 cells, 4 samples × 5 cell types — large expected frequencies."""
        rng = np.random.default_rng(42)
        n_cells = 1000
        obs = pd.DataFrame({
            "sample": rng.choice([f"sample_{i}" for i in range(4)], n_cells),
            "celltype": rng.choice([f"celltype_{i}" for i in range(5)], n_cells),
        })
        return ad.AnnData(rng.standard_normal((n_cells, 100)), obs=obs)

    @pytest.fixture
    def sample_adata_2x2(self):
        """A 2×2 table with small expected counts → Fisher fallback."""
        obs = pd.DataFrame({
            "sample": ["A"] * 8 + ["B"] * 12,
            "celltype": ["type1"] * 3 + ["type2"] * 5 + ["type1"] * 2 + ["type2"] * 10,
        })
        return ad.AnnData(np.random.randn(20, 10), obs=obs)

    @pytest.fixture
    def balanced_adata(self):
        """Perfectly balanced data — every Ro/e value must equal 1."""
        obs = pd.DataFrame({
            "sample": ["A"] * 50 + ["B"] * 50,
            "celltype": (["type1"] * 25 + ["type2"] * 25) * 2,
        })
        return ad.AnnData(np.random.randn(100, 10), obs=obs)

    # ---- core behaviour ----------------------------------------------------

    def test_returns_dataframe(self, sample_adata_large):
        result = ov.utils.roe(sample_adata_large, "sample", "celltype")
        assert isinstance(result, pd.DataFrame)
        assert result.index.name == "cluster"
        assert result.shape == (5, 4)

    def test_uns_roe_dict(self, sample_adata_large):
        adata = sample_adata_large.copy()
        ov.utils.roe(adata, "sample", "celltype")
        meta = adata.uns["roe"]
        assert isinstance(meta, dict)
        for key in ("roe", "observed", "expected", "chi2", "dof",
                    "pvalue", "test", "significant", "low_expected"):
            assert key in meta, f"missing adata.uns['roe'][{key!r}]"
        # back-compat keys
        assert "roe_results" in adata.uns
        assert "expected_values" in adata.uns

    def test_expected_matches_chi2(self, sample_adata_large):
        adata = sample_adata_large.copy()
        ov.utils.roe(adata, "sample", "celltype")
        contingency = pd.crosstab(adata.obs["celltype"], adata.obs["sample"])
        _, _, _, expected_manual = chi2_contingency(contingency)
        np.testing.assert_array_almost_equal(
            adata.uns["roe"]["expected"].values, expected_manual
        )

    def test_roe_is_observed_over_expected(self, sample_adata_large):
        adata = sample_adata_large.copy()
        roe = ov.utils.roe(adata, "sample", "celltype")
        observed = adata.uns["roe"]["observed"]
        expected = adata.uns["roe"]["expected"]
        np.testing.assert_array_almost_equal(roe.values, (observed / expected).values)

    def test_balanced_data_gives_one(self, balanced_adata):
        roe = ov.utils.roe(balanced_adata, "sample", "celltype")
        np.testing.assert_array_almost_equal(roe.values, 1.0, decimal=10)

    def test_always_returns_matrix_even_when_not_significant(self, balanced_adata):
        # Balanced data → global chi-square is non-significant, but the Ro/e
        # matrix must still be returned (p-value is a QC flag, not a gate).
        roe = ov.utils.roe(balanced_adata, "sample", "celltype", pval_threshold=1e-9)
        assert isinstance(roe, pd.DataFrame)
        assert roe.shape == (2, 2)
        assert balanced_adata.uns["roe"]["significant"] is False

    # ---- chi-square / Fisher ----------------------------------------------

    def test_fisher_fallback_for_2x2(self, sample_adata_2x2):
        adata = sample_adata_2x2.copy()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ov.utils.roe(adata, "sample", "celltype")
        assert "Fisher" in buf.getvalue()
        assert adata.uns["roe"]["test"] == "fisher"
        assert adata.uns["roe"]["low_expected"] is True

    # ---- column ordering ---------------------------------------------------

    def test_order_as_list(self, sample_adata_large):
        adata = sample_adata_large.copy()
        wanted = sorted(adata.obs["sample"].unique(), reverse=True)
        roe = ov.utils.roe(adata, "sample", "celltype", order=wanted)
        assert list(roe.columns) == wanted

    def test_order_as_comma_string_backcompat(self, sample_adata_large):
        adata = sample_adata_large.copy()
        wanted = sorted(adata.obs["sample"].unique(), reverse=True)
        roe = ov.utils.roe(adata, "sample", "celltype", order=",".join(wanted))
        assert list(roe.columns) == wanted

    def test_order_unknown_sample_raises(self, sample_adata_large):
        with pytest.raises(ValueError):
            ov.utils.roe(sample_adata_large, "sample", "celltype",
                         order=["sample_0", "does_not_exist"])

    # ---- empty cell types / samples ---------------------------------------

    def test_drops_empty_categorical_levels(self):
        # 'ghost' is a declared categorical level with zero cells — must be
        # dropped before chi2_contingency (which errors on a zero marginal).
        obs = pd.DataFrame({
            "sample": ["A"] * 30 + ["B"] * 30,
            "celltype": pd.Categorical(
                (["t1"] * 15 + ["t2"] * 15) * 2,
                categories=["t1", "t2", "ghost"],
            ),
        })
        adata = ad.AnnData(np.random.randn(60, 5), obs=obs)
        roe = ov.utils.roe(adata, "sample", "celltype")
        assert "ghost" not in roe.index
        assert roe.shape == (2, 2)

    def test_too_few_groups_raises(self):
        obs = pd.DataFrame({"sample": ["A"] * 10, "celltype": ["t1"] * 5 + ["t2"] * 5})
        adata = ad.AnnData(np.random.randn(10, 5), obs=obs)
        with pytest.raises(ValueError):          # only 1 sample
            ov.utils.roe(adata, "sample", "celltype")

    # ---- symbolic categories ----------------------------------------------

    def test_transform_anchored_scheme(self):
        from omicverse.utils._roe import transform_roe_values
        test = pd.DataFrame({
            "s1": [0.0, 0.1, 0.2, 1.0, 2.5, 4.0],
        }, index=[f"c{i}" for i in range(6)])
        # anchored: − (0) | +/− (0,0.2) | + [0.2,1] | ++ (1,3] | +++ (>3)
        expected = pd.DataFrame({
            "s1": ["−", "+/−", "+", "+", "++", "+++"],
        }, index=[f"c{i}" for i in range(6)])
        pd.testing.assert_frame_equal(transform_roe_values(test), expected)

    def test_transform_legacy_scheme(self):
        from omicverse.utils._roe import transform_roe_values
        test = pd.DataFrame({
            "s1": [0.0, 0.1, 0.3, 0.9, 1.2],
        }, index=[f"c{i}" for i in range(5)])
        # legacy: − (0) | +/− (0,0.2) | + [0.2,0.8] | ++ (0.8,1] | +++ (>1)
        expected = pd.DataFrame({
            "s1": ["−", "+/−", "+", "++", "+++"],
        }, index=[f"c{i}" for i in range(5)])
        pd.testing.assert_frame_equal(
            transform_roe_values(test, scheme="legacy"), expected
        )

    def test_transform_unknown_scheme_raises(self):
        from omicverse.utils._roe import transform_roe_values
        with pytest.raises(ValueError):
            transform_roe_values(pd.DataFrame({"s": [1.0]}), scheme="bogus")

    # ---- plotting ----------------------------------------------------------

    def test_plot_heatmap_runs(self, sample_adata_large):
        import matplotlib
        matplotlib.use("Agg")
        adata = sample_adata_large.copy()
        ov.utils.roe(adata, "sample", "celltype")
        ov.utils.roe_plot_heatmap(adata, display_numbers=True)
        ov.utils.roe_plot_heatmap(adata, display_numbers=False, scheme="anchored")
        ov.utils.roe_plot_heatmap(adata, display_numbers=False, scheme="legacy")

    def test_plot_heatmap_without_results_raises(self):
        adata = ad.AnnData(np.random.randn(10, 5))
        with pytest.raises(KeyError):
            ov.utils.roe_plot_heatmap(adata)

    # ---- edge cases --------------------------------------------------------

    def test_missing_obs_key_raises(self):
        adata = ad.AnnData(np.random.randn(10, 5))
        adata.obs = pd.DataFrame({"sample": ["A"] * 10})
        with pytest.raises(KeyError):
            ov.utils.roe(adata, "sample", "missing_celltype")


if __name__ == "__main__":
    pytest.main([__file__])
