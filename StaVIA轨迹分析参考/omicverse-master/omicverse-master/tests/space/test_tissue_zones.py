"""Tests for ``ov.space.nmf_tissue_zones`` — the sklearn-NMF tissue-zone
helper added as a response to omicverse/omicverse#653.

Planted-structure semantics: if we construct a known W @ H abundance
matrix with K = 3 latent zones, NMF(n_factors=3) should recover each
zone's dominant cell types into a single factor (in some order).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import anndata as ad


def _synthetic_abundance(n_spots=120, n_cell_types=8, n_zones=3, seed=0):
    """Build a cell-abundance matrix with a known 3-zone structure
    and return (adata, true_zone_membership)."""
    rng = np.random.default_rng(seed)
    W_true = rng.exponential(1.0, size=(n_spots, n_zones))
    H_true = rng.exponential(1.0, size=(n_zones, n_cell_types))
    # Zone membership: {zone_0: [0,1,2], zone_1: [3,4], zone_2: [5,6,7]}
    H_true[0, :3] *= 8;   H_true[0, 3:] *= 0.1
    H_true[1, 3:5] *= 8;  H_true[1, :3] *= 0.1;  H_true[1, 5:] *= 0.1
    H_true[2, 5:] *= 8;   H_true[2, :5] *= 0.1
    X = W_true @ H_true + rng.exponential(0.2, size=(n_spots, n_cell_types))
    adata = ad.AnnData(
        X=rng.standard_normal((n_spots, 20)),
        obs=pd.DataFrame(index=[f"s{i}" for i in range(n_spots)]),
        var=pd.DataFrame(index=[f"g{i}" for i in range(20)]),
    )
    adata.obsm["q05_cell_abundance_w_sf"] = X
    true_membership = {
        0: [0, 1, 2],   # zone 0 → cell types 0,1,2
        1: [3, 4],      # zone 1 → cell types 3,4
        2: [5, 6, 7],   # zone 2 → cell types 5,6,7
    }
    return adata, true_membership


class TestNMFTissueZones:
    def test_writes_correct_obsm_and_shape(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=0)
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, seed=0,
        )
        assert "X_tissue_zones" in adata.obsm
        assert adata.obsm["X_tissue_zones"].shape == (adata.n_obs, 3)
        assert tz.spot_activations.shape == (adata.n_obs, 3)
        assert tz.factor_loadings.shape == (8, 3)
        assert list(tz.factor_names) == ["zone_1", "zone_2", "zone_3"]

    def test_recovers_planted_zones(self):
        """For every true zone, at least one learned factor's top-3
        cell types must overlap the true membership by ≥2 types."""
        import omicverse as ov

        adata, truth = _synthetic_abundance(seed=0)
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, top_k=3, seed=0,
        )
        # For each true zone, see if any learned factor recovers ≥2 of
        # its cell types in the top-3 ranking.
        for zone_id, true_members in truth.items():
            true_names = {f"cell_type_{i}" for i in true_members}
            best_overlap = 0
            for factor, top_cts in tz.factor_top_cell_types.items():
                overlap = len(set(top_cts) & true_names)
                best_overlap = max(best_overlap, overlap)
            assert best_overlap >= 2, (
                f"Zone {zone_id} (true members {sorted(true_names)}) "
                f"not recovered; best overlap = {best_overlap}. "
                f"Learned top cell types per factor: "
                f"{tz.factor_top_cell_types}"
            )

    def test_uses_uns_factor_names_when_available(self):
        """If adata.uns already has per-obsm cell-type names (as
        cell2location writes), pick them up without requiring
        ``cell_type_names=``."""
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=1)
        custom_names = [f"ct_{ch}" for ch in "ABCDEFGH"]
        adata.uns["q05_cell_abundance_w_sf_names"] = custom_names
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, seed=0,
        )
        assert list(tz.factor_loadings.index) == custom_names

    def test_explicit_cell_type_names_override_uns(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=2)
        adata.uns["q05_cell_abundance_w_sf_names"] = ["junk"] * 8
        names = [f"explicit_{i}" for i in range(8)]
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, cell_type_names=names, seed=0,
        )
        assert list(tz.factor_loadings.index) == names

    def test_raises_on_wrong_cell_type_names_length(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=3)
        with pytest.raises(ValueError, match="cell_type_names"):
            ov.space.nmf_tissue_zones(
                adata, obsm_key="q05_cell_abundance_w_sf",
                n_factors=3, cell_type_names=["too", "short"],
            )

    def test_missing_obsm_key_raises(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=4)
        with pytest.raises(KeyError, match="q05"):
            ov.space.nmf_tissue_zones(
                adata, obsm_key="q05_missing", n_factors=3,
            )

    def test_rejects_negative_input(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=5)
        adata.obsm["q05_cell_abundance_w_sf"][:] = -1.0
        with pytest.raises(ValueError, match="negative values"):
            ov.space.nmf_tissue_zones(
                adata, obsm_key="q05_cell_abundance_w_sf", n_factors=3,
            )

    def test_reconstruction_error_finite(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=6)
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, seed=0,
        )
        assert np.isfinite(tz.reconstruction_err)
        assert tz.reconstruction_err >= 0

    def test_dataframe_obsm_infers_column_names(self):
        """When obsm[obsm_key] is a pandas DataFrame (Tangram pattern),
        cell type axis should be read from the DataFrame's columns
        rather than falling back to ``cell_type_N`` placeholders."""
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=7)
        X = adata.obsm["q05_cell_abundance_w_sf"]
        # Names that don't share a strippable common prefix — the
        # helper should pass them through as-is.
        custom_names = ["T_CD4_naive", "T_CD8", "B_mem", "FDC",
                        "Macrophages_M1", "Mast", "NK", "Endothelium"]
        adata.obsm["tangram_ct_pred"] = pd.DataFrame(
            X, index=adata.obs_names, columns=custom_names,
        )
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="tangram_ct_pred", n_factors=3, seed=0,
        )
        assert list(tz.factor_loadings.index) == custom_names, (
            f"Expected DataFrame columns to be used as cell-type "
            f"labels; got {list(tz.factor_loadings.index)[:5]}"
        )

    def test_row_normalize(self):
        """``normalize='rows'`` should feed a row-stochastic matrix to
        NMF (each spot's contribution sums to 1). Useful when obsm
        carries mapping probabilities rather than abundances."""
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=8)
        # Skew one spot to be 100x brighter so row-normalisation has
        # something concrete to flatten.
        adata.obsm["q05_cell_abundance_w_sf"][0] *= 100
        tz_raw = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, normalize=None, seed=0,
        )
        tz_norm = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, normalize="rows", seed=0,
        )
        # Under row-normalisation the loud spot can no longer
        # dominate factor 1 on its own, so the spread of activations
        # across the first factor is tighter (much smaller std vs mean).
        std_raw = np.std(tz_raw.spot_activations.iloc[:, 0])
        std_norm = np.std(tz_norm.spot_activations.iloc[:, 0])
        assert std_norm < std_raw, (
            f"Expected row-norm to reduce factor spread; "
            f"got std raw={std_raw:.3f} vs norm={std_norm:.3f}"
        )

    def test_uns_names_beat_dataframe_columns(self):
        """Cell2location writes both uns[f'{obsm_key}_names'] (clean
        cell type labels) and stores obsm as a DataFrame whose
        columns are prefixed with the obsm key. The uns copy should
        win so heatmaps get ``B_mem`` instead of
        ``q05_cell_abundance_w_sf_B_mem``."""
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=10)
        clean = [f"clean_{i}" for i in range(8)]
        ugly = [f"q05_prefix_{i}" for i in range(8)]
        adata.uns["q05_cell_abundance_w_sf_names"] = clean
        # Put an ugly-prefix DataFrame into obsm (simulates c2l's real
        # storage)
        X = adata.obsm["q05_cell_abundance_w_sf"]
        adata.obsm["q05_cell_abundance_w_sf"] = pd.DataFrame(
            X, index=adata.obs_names, columns=ugly,
        )
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, seed=0,
        )
        # Expect the clean uns names, not the prefixed DataFrame cols
        assert list(tz.factor_loadings.index) == clean, (
            f"expected uns names to win; got "
            f"{list(tz.factor_loadings.index)[:3]}..."
        )

    def test_uns_mod_factor_names_fallback(self):
        """Modern cell2location writes clean labels only to
        ``uns['mod']['factor_names']`` — no top-level uns key — and
        the DataFrame columns are verbosely prefixed. We must still
        surface the clean labels (second-priority source)."""
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=11)
        clean = [f"CT_{ch}" for ch in "ABCDEFGH"]
        ugly_prefix = "q05cell_abundance_w_sf_"
        ugly = [f"{ugly_prefix}{n}" for n in clean]
        X = adata.obsm["q05_cell_abundance_w_sf"]
        adata.obsm["q05_cell_abundance_w_sf"] = pd.DataFrame(
            X, index=adata.obs_names, columns=ugly,
        )
        adata.uns["mod"] = {"factor_names": clean}
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="q05_cell_abundance_w_sf",
            n_factors=3, seed=0,
        )
        assert list(tz.factor_loadings.index) == clean

    def test_common_prefix_stripped_from_dataframe_columns(self):
        """If no uns names are available and the DataFrame columns
        share a common prefix, we strip it so heatmap labels stay
        readable. This helps older cell2location exports where
        factor_names isn't written."""
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=12)
        ugly_prefix = "tangram_ct_pred_"
        raw = [f"{ugly_prefix}CT_{ch}" for ch in "ABCDEFGH"]
        X = adata.obsm["q05_cell_abundance_w_sf"]
        adata.obsm["tangram_ct_pred"] = pd.DataFrame(
            X, index=adata.obs_names, columns=raw,
        )
        tz = ov.space.nmf_tissue_zones(
            adata, obsm_key="tangram_ct_pred",
            n_factors=3, seed=0,
        )
        # Prefix should be stripped
        assert list(tz.factor_loadings.index) == [
            f"CT_{ch}" for ch in "ABCDEFGH"
        ], list(tz.factor_loadings.index)

    def test_rejects_unknown_normalize(self):
        import omicverse as ov

        adata, _ = _synthetic_abundance(seed=9)
        with pytest.raises(ValueError, match="normalize"):
            ov.space.nmf_tissue_zones(
                adata, obsm_key="q05_cell_abundance_w_sf",
                n_factors=3, normalize="zscore",
            )
