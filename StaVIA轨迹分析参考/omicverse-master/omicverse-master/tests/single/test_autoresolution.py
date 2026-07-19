"""Tests for the redesigned ``ov.single.auto_resolution`` (Lange et al. 2004
null-adjusted bootstrap-ARI; lives in ``omicverse/single/_autoresolution.py``).

Builds small synthetic AnnData with 3 well-separated Gaussian blobs and
verifies that the chosen resolution lands near 3 clusters; checks the
``uns['autoResolution']`` payload, temp-column cleanup, error paths,
and the @tracked provenance hookup.
"""
from __future__ import annotations

import os

import anndata as ad
import numpy as np
import pandas as pd
import pytest


def _three_blob_adata(n_per_blob: int = 100, n_genes: int = 50,
                       seed: int = 0) -> ad.AnnData:
    """Three well-separated blobs in gene space → leiden picks ~3 clusters."""
    rng = np.random.default_rng(seed)
    centers = np.zeros((3, n_genes))
    centers[0, :n_genes // 3] = 5
    centers[1, n_genes // 3:2 * n_genes // 3] = 5
    centers[2, 2 * n_genes // 3:] = 5
    X = np.vstack([
        centers[0] + rng.normal(0, 0.5, size=(n_per_blob, n_genes)),
        centers[1] + rng.normal(0, 0.5, size=(n_per_blob, n_genes)),
        centers[2] + rng.normal(0, 0.5, size=(n_per_blob, n_genes)),
    ]).astype(np.float32)
    obs = pd.DataFrame({
        "true_label": np.repeat(["A", "B", "C"], n_per_blob),
    }, index=[f"c{i}" for i in range(3 * n_per_blob)])
    var = pd.DataFrame(index=[f"g{i}" for i in range(n_genes)])
    return ad.AnnData(X=X, obs=obs, var=var)


@pytest.fixture(scope="module")
def adata_with_neighbors():
    """Synthetic AnnData with 3 well-separated clusters + neighbor graph."""
    os.environ.setdefault("OMICVERSE_DISABLE_LLM", "1")
    import scanpy as sc

    a = _three_blob_adata(n_per_blob=120, n_genes=60, seed=0)
    sc.pp.pca(a, n_comps=10)
    sc.pp.neighbors(a, n_neighbors=15, use_rep="X_pca")
    return a


# ─────────────────────────── happy paths ──────────────────────────────────────


def test_autoresolution_picks_three_clusters_with_null_correction(
    adata_with_neighbors,
):
    """Three well-separated blobs → null-adjusted stability picks
    a resolution that recovers ~3 clusters."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    _, best, df = ov.single.auto_resolution(
        a, resolutions=[0.1, 0.3, 0.5, 0.8, 1.2],
        n_subsamples=3, n_null_subsamples=2,
        random_state=0, verbose=False,
    )
    assert best in [0.1, 0.3, 0.5, 0.8, 1.2]
    # On three well-separated blobs the chosen resolution should land
    # near three clusters (allow 2-4 for noise / leiden tie-breaks).
    assert 2 <= int(df.loc[best, "n_clusters"]) <= 4
    # excess_stability should be the column the argmax was taken on.
    assert df["excess_stability"].idxmax() == best


def test_uns_payload_carries_lange_method_label(adata_with_neighbors):
    import omicverse as ov

    a = adata_with_neighbors.copy()
    ov.single.auto_resolution(
        a, resolutions=[0.3, 0.6], n_subsamples=2, n_null_subsamples=2,
        random_state=0, key_added="leiden_auto", verbose=False,
    )
    payload = a.uns["autoResolution"]
    assert payload["use_null_correction"] is True
    assert "Lange" in payload["method"]
    assert payload["n_null_subsamples"] == 2
    # scores table has the null-adjusted columns.
    scores_df = pd.DataFrame(payload["scores"])
    expected = {"resolution", "n_clusters", "stability_real",
                 "stability_null", "excess_stability", "std_real"}
    assert set(scores_df.columns) >= expected
    # Chosen resolution's labels written under key_added.
    assert "leiden_auto" in a.obs.columns


def test_use_null_correction_false_falls_back_to_plain_stability(
    adata_with_neighbors,
):
    """``use_null_correction=False`` reverts to plain bootstrap-ARI argmax."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    _, best, df = ov.single.auto_resolution(
        a, resolutions=[0.3, 0.6], n_subsamples=2,
        use_null_correction=False, random_state=0, verbose=False,
    )
    # null columns are still in the df but all zeros.
    assert (df["stability_null"] == 0.0).all()
    assert df["stability_real"].idxmax() == best
    payload = a.uns["autoResolution"]
    assert payload["use_null_correction"] is False
    assert payload["n_null_subsamples"] == 0


# ─────────────────────────── invariants ───────────────────────────────────────


def test_temp_obs_cols_are_cleaned(adata_with_neighbors):
    """The intermediate ``_autores_*`` obs columns must NOT leak."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    obs_cols_before = set(a.obs.columns)
    ov.single.auto_resolution(
        a, resolutions=[0.3, 0.5], n_subsamples=2, n_null_subsamples=2,
        random_state=0, verbose=False,
    )
    leaked = [c for c in a.obs.columns
               if c.startswith("_autores") and c not in obs_cols_before]
    assert leaked == []


def test_records_one_provenance_entry(adata_with_neighbors):
    """@tracked wires this into adata.uns['_ov_provenance']; nested
    leiden invocations are silenced by the depth guard."""
    import omicverse as ov
    from omicverse.report._provenance import (
        clear_provenance, get_provenance,
    )

    a = adata_with_neighbors.copy()
    clear_provenance(a)
    ov.single.auto_resolution(
        a, resolutions=[0.3, 0.6], n_subsamples=2, n_null_subsamples=2,
        random_state=0, verbose=False,
    )
    prov = get_provenance(a)
    names = [e["name"] for e in prov]
    assert names == ["auto_resolution"]
    e = prov[0]
    assert e["function"] == "ov.single.auto_resolution"
    assert "ARI" in e["backend"]
    viz_fns = [v["function"] for v in e["viz"]]
    assert "ov.pl.cluster_sizes_bar" in viz_fns
    assert "ov.pl.auto_resolution_curve" in viz_fns


# ─────────────────────────── error paths ──────────────────────────────────────


def test_min_clusters_guard_raises(adata_with_neighbors):
    """If every candidate produces fewer than min_clusters, raise."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    with pytest.raises(RuntimeError, match="No resolution"):
        ov.single.auto_resolution(
            a, resolutions=[0.1, 0.3], n_subsamples=2, n_null_subsamples=2,
            min_clusters=999, random_state=0, verbose=False,
        )


def test_requires_neighbor_graph():
    import omicverse as ov

    a = _three_blob_adata(n_per_blob=60, n_genes=20, seed=0)
    with pytest.raises(ValueError, match="connectivities"):
        ov.single.auto_resolution(a, verbose=False)


def test_rejects_tiny_adata():
    import omicverse as ov

    a = _three_blob_adata(n_per_blob=10, n_genes=20, seed=0)
    with pytest.raises(ValueError, match="at least 50 cells"):
        ov.single.auto_resolution(a, verbose=False)


# ─────────────────────── method='champ' backend route ─────────────────────────


def test_method_champ_routes_to_champ(adata_with_neighbors):
    """`method='champ'` delegates to ov.pp.champ and returns a scalar
    resolution + the CHAMP partitions DataFrame."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    _, best_r, df = ov.single.auto_resolution(
        a, method='champ',
        gamma_min=0.05, gamma_max=1.5, n_partitions=10,
        random_state=0, verbose=False,
    )
    assert isinstance(best_r, float)
    # CHAMP-shape DataFrame, not bootstrap-ARI-shape.
    assert {"a", "b", "n_clusters", "on_hull",
            "gamma_lo", "gamma_hi", "gamma_range"}.issubset(df.columns)
    # CHAMP writes its payload under key_added (default 'leiden') —
    # reachable via ov.pl.champ_landscape(adata).
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ax = ov.pl.champ_landscape(a)
    assert isinstance(ax, plt.Axes)
    plt.close("all")


def test_invalid_method_raises(adata_with_neighbors):
    import omicverse as ov

    a = adata_with_neighbors.copy()
    with pytest.raises(ValueError, match="method must be"):
        ov.single.auto_resolution(a, method='unknown-thing', verbose=False)


def test_method_champ_silences_nested_champ_provenance(adata_with_neighbors):
    """When called via auto_resolution(method='champ'), the nesting
    guard silences ov.pp.champ's own record_step — only one provenance
    entry (named 'auto_resolution') appears, and its backend reflects
    that CHAMP was used."""
    import omicverse as ov
    from omicverse.report._provenance import (
        clear_provenance, get_provenance,
    )

    a = adata_with_neighbors.copy()
    clear_provenance(a)
    ov.single.auto_resolution(
        a, method='champ',
        gamma_min=0.1, gamma_max=1.2, n_partitions=6,
        random_state=0, verbose=False,
    )
    prov = get_provenance(a)
    names = [e["name"] for e in prov]
    assert names == ["auto_resolution"]
    assert "CHAMP" in prov[0]["backend"]


# ─────────────────────── auto_resolution_curve plot ───────────────────────────


def test_auto_resolution_curve_renders_from_uns(adata_with_neighbors):
    """``ov.pl.auto_resolution_curve(adata)`` reads from
    ``adata.uns['autoResolution']`` and returns a matplotlib Axes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import omicverse as ov

    a = adata_with_neighbors.copy()
    ov.single.auto_resolution(
        a, resolutions=[0.3, 0.6, 1.0], n_subsamples=2, n_null_subsamples=2,
        random_state=0, verbose=False,
    )
    ax = ov.pl.auto_resolution_curve(a)
    assert isinstance(ax, plt.Axes)
    # The chosen-resolution annotation should be in the plot.
    texts = [t.get_text() for t in ax.texts]
    assert any("chosen r=" in t for t in texts)
    plt.close("all")


def test_auto_resolution_curve_explicit_scores():
    """The curve helper accepts an explicit scores DataFrame, no adata."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import omicverse as ov

    df = pd.DataFrame({
        "stability_real":   [0.6, 0.7, 0.8, 0.7],
        "stability_null":   [1.0, 0.05, 0.06, 0.05],
        "excess_stability": [-0.4, 0.65, 0.74, 0.65],
        "n_clusters":       [3, 5, 7, 9],
    }, index=[0.2, 0.4, 0.6, 0.8])
    df.index.name = "resolution"
    ax = ov.pl.auto_resolution_curve(scores=df)
    assert isinstance(ax, plt.Axes)
    plt.close("all")
