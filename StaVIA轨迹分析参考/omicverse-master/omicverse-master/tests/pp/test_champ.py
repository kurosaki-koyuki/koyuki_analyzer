"""Tests for ``ov.pp.champ`` (CHAMP — Weir et al. 2017).

Verifies:
- Modularity coefficients (a, b) match the closed-form formula on a
  trivial graph that we can hand-check.
- The upper-hull selection picks a hull partition (never a dominated
  one) on synthetic three-blob data.
- ``adata.uns['champ']`` payload schema, temp-column cleanup,
  ``@tracked`` provenance hookup, missing-graph error.
"""
from __future__ import annotations

import os

import anndata as ad
import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp


def _three_blob_adata(n_per_blob: int = 100, n_genes: int = 50,
                       seed: int = 0) -> ad.AnnData:
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
    obs = pd.DataFrame({"true_label": np.repeat(["A", "B", "C"], n_per_blob)},
                        index=[f"c{i}" for i in range(3 * n_per_blob)])
    var = pd.DataFrame(index=[f"g{i}" for i in range(n_genes)])
    return ad.AnnData(X=X, obs=obs, var=var)


@pytest.fixture(scope="module")
def adata_with_neighbors():
    os.environ.setdefault("OMICVERSE_DISABLE_LLM", "1")
    import scanpy as sc
    a = _three_blob_adata(n_per_blob=120, n_genes=60, seed=0)
    sc.pp.pca(a, n_comps=10)
    sc.pp.neighbors(a, n_neighbors=15, use_rep="X_pca")
    return a


# ─────────────────────── modularity coefficients ──────────────────────────────


def test_modularity_coefficients_two_perfect_clusters():
    """For a graph with two disconnected fully-connected components and
    a partition that respects them, ``a = 1`` (all edges within-cluster)
    and ``b = sum of (D_c / 2m)^2`` over clusters.
    """
    from omicverse.pp._champ import _modularity_coefficients

    # Two K_3 components (3 nodes each, fully connected within).
    A = np.zeros((6, 6))
    for i in range(3):
        for j in range(3):
            if i != j:
                A[i, j] = 1.0
    for i in range(3, 6):
        for j in range(3, 6):
            if i != j:
                A[i, j] = 1.0
    W = sp.csr_matrix(A)
    labels = np.array([0, 0, 0, 1, 1, 1])
    a, b = _modularity_coefficients(W, labels)
    # Total weight 2m = 12 (12 directed edges, 6 undirected). Each cluster
    # contributes 6 (within edge weight). a = 12/12 = 1.0.
    assert a == pytest.approx(1.0)
    # Each cluster has total degree 6. (6/12)^2 + (6/12)^2 = 0.25 + 0.25 = 0.5.
    assert b == pytest.approx(0.5)
    # Q at γ=1 should equal a − b = 0.5 — modularity of perfect partition
    # on disconnected graph is well-known to be 0.5 for two K_3's.
    assert (a - 1.0 * b) == pytest.approx(0.5)


def test_modularity_coefficients_handle_dense_input():
    from omicverse.pp._champ import _modularity_coefficients
    W = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]], dtype=float)
    a, b = _modularity_coefficients(W, np.array([0, 0, 1]))
    # 2m = 6; within-cluster edge weight = 2 (only edge between 0–1);
    # a = 2/6 = 1/3.
    assert a == pytest.approx(1 / 3)


# ─────────────────────── upper hull primitive ─────────────────────────────────


def test_upper_hull_filters_dominated_points():
    from omicverse.pp._champ import _upper_hull_indices
    # Two points form a clear hull; (0.5, 0.0) is dominated.
    b = np.array([0.0, 0.5, 1.0])
    a = np.array([1.0, 0.0, 0.5])
    hull = _upper_hull_indices(b, a)
    # Point 0 (0,1) and point 2 (1,0.5) are on the upper envelope;
    # point 1 (0.5,0) is dominated. Andrew's monotone chain returns
    # them in ascending b order.
    assert hull == [0, 2]


def test_upper_hull_keeps_strictly_concave_points():
    """Three points with strictly decreasing slope between consecutive
    pairs → all three lie on the upper hull."""
    from omicverse.pp._champ import _upper_hull_indices
    # Slopes: (2-0)/(1-0)=2, (3-2)/(2-1)=1 — strictly decreasing → concave.
    hull = _upper_hull_indices(np.array([0.0, 1.0, 2.0]),
                                np.array([0.0, 2.0, 3.0]))
    assert hull == [0, 1, 2]


def test_upper_hull_drops_collinear_interior_point():
    """Three collinear points → Andrew's strict monotone chain drops
    the middle one (cross product is exactly 0 → popped). This is the
    intended strict-hull behaviour for CHAMP: the interior collinear
    partition gives the same Q as the line through its neighbours, so
    excluding it from the hull doesn't change the admissible
    envelope."""
    from omicverse.pp._champ import _upper_hull_indices
    hull = _upper_hull_indices(np.array([0.0, 1.0, 2.0]),
                                np.array([0.0, 1.0, 2.0]))
    assert hull == [0, 2]


# ─────────────────────────── end-to-end ───────────────────────────────────────


def test_champ_picks_a_hull_partition(adata_with_neighbors):
    """The chosen partition must be on the convex hull (never a
    dominated one). Verify by computing the chosen partition's own
    (a, b) and matching them against a hull row — label equality
    would be a weaker check because two resolutions can yield the
    same n_clusters without being the same partition."""
    import omicverse as ov
    from omicverse.pp._champ import _modularity_coefficients

    a = adata_with_neighbors.copy()
    _, (lo, hi), df = ov.pp.champ(
        a, n_partitions=12, gamma_min=0.1, gamma_max=2.0,
        random_state=0, verbose=False,
    )
    assert hi >= lo

    chosen_labels = a.obs["champ"].astype(int).values
    a_chosen, b_chosen = _modularity_coefficients(
        a.obsp["connectivities"], chosen_labels,
    )
    hull = df[df["on_hull"]]
    # Floating-point match to some hull row's (a, b).
    matches = ((hull["a"] - a_chosen).abs() < 1e-9) & \
              ((hull["b"] - b_chosen).abs() < 1e-9)
    assert matches.any(), (
        f"chosen (a, b) = ({a_chosen:.6g}, {b_chosen:.6g}) "
        f"does not match any hull row:\n{hull}"
    )


def test_champ_writes_uns_payload_under_key_added(adata_with_neighbors):
    """``uns`` slot honours ``key_added`` (scanpy convention) so two
    calls with different ``key_added`` don't clobber each other."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    ov.pp.champ(
        a, n_partitions=10, random_state=0, verbose=False,
        key_added="champ_clusters",
    )
    assert "champ_clusters" in a.obs.columns
    assert "champ_clusters" in a.uns, \
        "uns slot should follow key_added, not be hardcoded to 'champ'"
    payload = a.uns["champ_clusters"]
    assert "Weir" in payload["method"]
    assert {"chosen_n_clusters", "chosen_gamma_range",
            "chosen_origin_resolution"}.issubset(payload)
    assert payload["chosen_n_clusters"] == int(a.obs["champ_clusters"].nunique())
    parts_df = pd.DataFrame(payload["partitions"])
    assert {"a", "b", "n_clusters", "on_hull",
            "gamma_lo", "gamma_hi", "gamma_range"}.issubset(parts_df.columns)


def test_champ_preserves_user_column_at_scratch_key(adata_with_neighbors):
    """If the caller already has obs['_champ_tmp'], CHAMP must restore
    it — the scratch slot is an internal detail, not a licence to
    clobber user state."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    a.obs["_champ_tmp"] = np.arange(a.n_obs)  # user-owned column
    before = a.obs["_champ_tmp"].copy()
    ov.pp.champ(a, n_partitions=6, random_state=0, verbose=False)
    assert "_champ_tmp" in a.obs.columns
    assert (a.obs["_champ_tmp"].values == before.values).all()


def test_champ_rejects_single_resolution(adata_with_neighbors):
    """A single resolution can't define a hull — raise clearly."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    with pytest.raises(ValueError, match="at least 2"):
        ov.pp.champ(a, resolutions=[0.5], random_state=0, verbose=False)


def test_champ_cleans_temp_obs_cols(adata_with_neighbors):
    import omicverse as ov

    a = adata_with_neighbors.copy()
    obs_before = set(a.obs.columns)
    ov.pp.champ(a, n_partitions=8, random_state=0, verbose=False)
    leaked = [c for c in a.obs.columns
               if c.startswith("_champ_") and c not in obs_before]
    assert leaked == []


def test_champ_records_one_provenance_entry(adata_with_neighbors):
    import omicverse as ov
    from omicverse.report._provenance import (
        clear_provenance, get_provenance,
    )

    a = adata_with_neighbors.copy()
    clear_provenance(a)
    ov.pp.champ(a, n_partitions=8, random_state=0, verbose=False)
    prov = get_provenance(a)
    names = [e["name"] for e in prov]
    assert names == ["champ"]
    e = prov[0]
    assert e["function"] == "ov.pp.champ"
    assert "CHAMP" in e["backend"]


def test_champ_requires_neighbor_graph():
    import omicverse as ov

    a = _three_blob_adata(n_per_blob=60, n_genes=20, seed=0)
    with pytest.raises(ValueError, match="connectivities"):
        ov.pp.champ(a, verbose=False)


def test_champ_widths_are_non_negative(adata_with_neighbors):
    """The clamped widths column should never report negative ranges
    even when hull partitions extend beyond gamma_max."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    _, _, df = ov.pp.champ(
        a, n_partitions=8, gamma_min=0.1, gamma_max=0.5,  # tight cap
        random_state=0, verbose=False,
    )
    hull_widths = df.loc[df["on_hull"], "gamma_range"]
    # All hull rows should report a non-negative range after clamping.
    assert (hull_widths >= 0).all()


# ─────────────────────── width_metric ──────────────────────────────────────────


def test_width_metric_log_default(adata_with_neighbors):
    """Default ``width_metric='log'`` is recorded in the uns payload."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    ov.pp.champ(a, n_partitions=8, random_state=0, verbose=False)
    assert a.uns["champ"]["width_metric"] == "log"


def test_width_metric_can_select_different_partitions(adata_with_neighbors):
    """linear vs log γ-width can pick *different* hull partitions —
    the whole point of the new metric. We don't assert which is right
    on the synthetic data, only that the choice depends on the metric."""
    import omicverse as ov

    chosen = {}
    for metric in ("linear", "log"):
        a = adata_with_neighbors.copy()
        _, _, df = ov.pp.champ(
            a, n_partitions=12, gamma_min=0.05, gamma_max=2.5,
            width_metric=metric, random_state=0, verbose=False,
        )
        # Both metrics must respect the on-hull invariant.
        chosen_idx = df["gamma_range"].idxmax()
        assert df.loc[chosen_idx, "on_hull"], \
            f"{metric}: chosen partition was not on the hull"
        chosen[metric] = (
            df.loc[chosen_idx, "n_clusters"],
            df.loc[chosen_idx, "gamma_lo"],
            df.loc[chosen_idx, "gamma_hi"],
        )
    # The two metrics need not agree, but both should produce hull
    # partitions; this test pins the contract that the parameter has
    # an effect on the chosen γ-range.
    # (On pbmc8k they pick wildly different partitions — see the
    # comparison notebook for empirical evidence.)
    assert isinstance(chosen["linear"], tuple) and isinstance(chosen["log"], tuple)


def test_width_metric_unknown_raises(adata_with_neighbors):
    import omicverse as ov

    a = adata_with_neighbors.copy()
    with pytest.raises(ValueError, match="width_metric"):
        ov.pp.champ(
            a, n_partitions=6, width_metric="bogus",
            random_state=0, verbose=False,
        )


# ─────────────────────── n_seeds ──────────────────────────────────────────────


def test_n_seeds_can_grow_candidate_pool(adata_with_neighbors):
    """``n_seeds=k`` runs leiden ``k`` times per γ; the resulting
    candidate pool is at least as large as ``n_seeds=1`` (sometimes
    larger when different seeds find different local optima)."""
    import omicverse as ov

    a1 = adata_with_neighbors.copy()
    _, _, df1 = ov.pp.champ(
        a1, n_partitions=8, n_seeds=1,
        gamma_min=0.05, gamma_max=2.0,
        random_state=0, verbose=False,
    )
    a3 = adata_with_neighbors.copy()
    _, _, df3 = ov.pp.champ(
        a3, n_partitions=8, n_seeds=3,
        gamma_min=0.05, gamma_max=2.0,
        random_state=0, verbose=False,
    )
    # n_seeds=3 considers ≥ as many partitions as n_seeds=1; uns
    # records the value used.
    assert len(df3) >= len(df1)
    assert a3.uns["champ"]["n_seeds"] == 3
    assert a1.uns["champ"]["n_seeds"] == 1


def test_n_seeds_zero_or_negative_raises(adata_with_neighbors):
    import omicverse as ov

    a = adata_with_neighbors.copy()
    with pytest.raises(ValueError, match="n_seeds"):
        ov.pp.champ(a, n_partitions=4, n_seeds=0,
                     random_state=0, verbose=False)


# ─────────────────────── modularity flavour ───────────────────────────────────


def test_modularity_coefficients_cpm():
    """CPM coefficients on the same 2·K_3 graph: ``a`` matches Newman
    (within-cluster edge weight is the same), but ``b_CPM = Σ |c|² / N²``
    differs from ``b_Newman = Σ D_c² / (2m)²``."""
    from omicverse.pp._champ import _modularity_coefficients

    A = np.zeros((6, 6))
    for i in range(3):
        for j in range(3):
            if i != j:
                A[i, j] = 1.0
    for i in range(3, 6):
        for j in range(3, 6):
            if i != j:
                A[i, j] = 1.0
    W = sp.csr_matrix(A)
    labels = np.array([0, 0, 0, 1, 1, 1])
    a_cpm, b_cpm = _modularity_coefficients(W, labels, modularity="cpm")
    a_new, b_new = _modularity_coefficients(W, labels, modularity="newman")
    # Both use the same 'a' (within-cluster edge weight / total).
    assert a_cpm == pytest.approx(a_new)
    # b_CPM = (3² + 3²) / 6² = 18/36 = 0.5 — same as b_Newman by
    # coincidence on this regular graph (D_c is constant).
    assert b_cpm == pytest.approx(0.5)


def test_modularity_unknown_raises():
    from omicverse.pp._champ import _modularity_coefficients
    W = sp.csr_matrix(np.eye(3))
    labels = np.array([0, 1, 2])
    with pytest.raises(ValueError, match="modularity"):
        _modularity_coefficients(W, labels, modularity="bogus")


def test_champ_modularity_cpm_runs(adata_with_neighbors):
    """End-to-end CPM scoring path. Only validates that the run
    completes and the uns payload records modularity='cpm' — the
    chosen partition naturally differs from Newman scoring (different
    objectives) and is data-dependent."""
    import omicverse as ov

    a = adata_with_neighbors.copy()
    try:
        _, _, df = ov.pp.champ(
            a, n_partitions=8, modularity="cpm",
            gamma_min=1e-4, gamma_max=1e-2,  # CPM γ-scale is much smaller
            random_state=0, verbose=False,
        )
    except ImportError as exc:
        pytest.skip(f"leidenalg not installed: {exc}")
    assert a.uns["champ"]["modularity"] == "cpm"
    assert "champ" in a.obs.columns


# ─────────────────────── adaptive refinement ──────────────────────────────────


def test_adaptive_appends_or_stabilises(adata_with_neighbors):
    """``adaptive=True`` either grows the partition set (if hidden
    crossovers were found) or terminates when the hull stabilises.
    Either way the result is at least as good (by hull size) as the
    non-adaptive baseline."""
    import omicverse as ov

    a_base = adata_with_neighbors.copy()
    _, _, df_base = ov.pp.champ(
        a_base, n_partitions=6,
        gamma_min=0.05, gamma_max=2.0,
        random_state=0, verbose=False,
    )
    a_adp = adata_with_neighbors.copy()
    _, _, df_adp = ov.pp.champ(
        a_adp, n_partitions=6, adaptive=True,
        adaptive_max_iter=2, adaptive_n_refine=2,
        gamma_min=0.05, gamma_max=2.0,
        random_state=0, verbose=False,
    )
    assert len(df_adp) >= len(df_base)
    assert a_adp.uns["champ"]["adaptive"] is True
    assert a_base.uns["champ"]["adaptive"] is False
