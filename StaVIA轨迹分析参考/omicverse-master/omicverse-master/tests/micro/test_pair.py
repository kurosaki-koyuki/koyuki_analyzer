"""Unit tests for ov.micro._pair (paired microbe ↔ metabolite integration)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _has_franzosa_cache() -> bool:
    import os
    for n in ("genera.tsv", "mtb.tsv", "metadata.tsv"):
        if not os.path.exists(os.path.join(
            "/scratch/users/steorra/analysis/omicverse_dev/cache/franzosa_2019",
            n,
        )):
            return False
    return True


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


requires_torch = pytest.mark.skipif(
    not _torch_available(),
    reason="torch not installed (install the [tests] extra)",
)

# Network-fetching tests are opt-in: set OMICVERSE_NET_TESTS=1 to run, or
# drop the cached TSVs under the hard-coded scratch path used by the
# microbiome tutorial. CI / reviewers can skip.
import os as _os
requires_franzosa = pytest.mark.skipif(
    not (_os.environ.get("OMICVERSE_NET_TESTS") == "1" or _has_franzosa_cache()),
    reason="fetch_franzosa_ibd_2019 test needs either a cached copy or "
           "OMICVERSE_NET_TESTS=1 to actually download (~30 MB).",
)


# ---------------------------------------------------------------------------
# simulate_paired
# ---------------------------------------------------------------------------


def test_simulate_paired_shapes_and_alignment():
    from omicverse.micro import simulate_paired
    mb, mt, truth = simulate_paired(
        n_samples=20, n_microbes=30, n_metabolites=15, n_pairs=4, seed=1,
    )
    assert mb.shape == (20, 30)
    assert mt.shape == (20, 15)
    assert list(mb.obs_names) == list(mt.obs_names)
    assert truth.shape == (4, 3)
    assert set(truth.columns) == {"microbe", "metabolite", "effect"}
    assert (truth["effect"] > 0).all()


def test_simulate_paired_counts_are_integers():
    from omicverse.micro import simulate_paired
    mb, _, _ = simulate_paired(seed=42)
    X = mb.X.toarray() if hasattr(mb.X, "toarray") else np.asarray(mb.X)
    assert np.issubdtype(X.dtype, np.integer) or np.all(X == X.astype(int))


# ---------------------------------------------------------------------------
# paired_spearman
# ---------------------------------------------------------------------------


def test_paired_spearman_recovers_planted_pairs_in_top_rank():
    from omicverse.micro import simulate_paired, paired_spearman
    mb, mt, truth = simulate_paired(n_pairs=5, seed=0)
    res = paired_spearman(mb, mt)
    assert set(res.columns) == {
        "microbe", "metabolite", "rho", "p_value", "fdr_bh",
    }
    # Every planted pair should rank above most of the ~800 random pairs.
    pairs = list(zip(truth["microbe"], truth["metabolite"]))
    ranks = []
    for m, x in pairs:
        hit = res[(res["microbe"] == m) & (res["metabolite"] == x)]
        assert len(hit) == 1
        ranks.append(int(hit.index[0]) + 1)
    assert max(ranks) <= 10      # all planted pairs in top 10 / 800


def test_paired_spearman_rejects_mismatched_obs():
    from omicverse.micro import simulate_paired, paired_spearman
    mb, mt, _ = simulate_paired(seed=0)
    mt2 = mt.copy()
    mt2.obs_names = [f"X{i}" for i in range(mt2.shape[0])]
    with pytest.raises(ValueError, match="obs_names"):
        paired_spearman(mb, mt2)


# ---------------------------------------------------------------------------
# paired_cca
# ---------------------------------------------------------------------------


def test_paired_cca_returns_expected_keys():
    from omicverse.micro import simulate_paired, paired_cca
    mb, mt, _ = simulate_paired(seed=0)
    out = paired_cca(mb, mt, n_components=2)
    for key in ("cca", "x_scores", "y_scores",
                "microbe_loadings", "metabolite_loadings",
                "canonical_correlations"):
        assert key in out
    assert out["x_scores"].shape == (mb.shape[0], 2)
    assert out["y_scores"].shape == (mt.shape[0], 2)
    assert len(out["canonical_correlations"]) == 2
    # With a planted signal the first canonical correlation should be high.
    assert out["canonical_correlations"][0] > 0.5


# ---------------------------------------------------------------------------
# MMvec
# ---------------------------------------------------------------------------


@requires_torch
def test_mmvec_fit_and_accessors():
    from omicverse.micro import simulate_paired, MMvec
    mb, mt, _ = simulate_paired(n_samples=25, seed=7)
    model = MMvec(n_latent=2, epochs=100, val_frac=0.0, seed=0).fit(mb, mt)
    # shapes
    assert model.microbe_embeddings_.shape    == (mb.shape[1], 2)
    assert model.metabolite_embeddings_.shape == (mt.shape[1], 2)
    # loss history is non-empty and monotonically non-increasing on avg
    assert len(model.loss_history_) >= 50
    # training loss should have dropped by a non-trivial amount.
    first = np.mean(model.loss_history_[:10])
    last  = np.mean(model.loss_history_[-10:])
    assert last < first


@requires_torch
def test_mmvec_cooccurrence_and_conditional_probs():
    from omicverse.micro import simulate_paired, MMvec
    mb, mt, _ = simulate_paired(n_samples=20, seed=7)
    model = MMvec(n_latent=2, epochs=80, val_frac=0.0, seed=0).fit(mb, mt)
    co = model.cooccurrence()
    assert co.shape == (mb.shape[1], mt.shape[1])
    probs = model.conditional_probabilities()
    # Each row should be a valid probability distribution.
    row_sums = probs.sum(axis=1).values
    np.testing.assert_allclose(row_sums, np.ones_like(row_sums), atol=1e-5)


@requires_torch
def test_mmvec_top_pairs_includes_some_planted():
    """MMvec is trained on small synthetic data — recovery quality isn't
    guaranteed to beat Spearman, but at least one planted pair should be
    in the top-30 |log-odds| hits."""
    from omicverse.micro import simulate_paired, MMvec
    mb, mt, truth = simulate_paired(n_pairs=5, seed=0)
    model = MMvec(n_latent=3, epochs=400, val_frac=0.1,
                  patience=50, seed=0).fit(mb, mt)
    top = model.top_pairs(n=30)
    hits = top.merge(truth[["microbe", "metabolite"]],
                     on=["microbe", "metabolite"])
    assert len(hits) >= 1


def test_mmvec_unfitted_accessors_raise():
    from omicverse.micro import MMvec
    model = MMvec()
    with pytest.raises(RuntimeError, match="not fitted"):
        _ = model.microbe_embeddings_


# ---------------------------------------------------------------------------
# Plotting — just assert Axes are returned and nothing crashes.
# ---------------------------------------------------------------------------


@requires_torch
def test_plot_mmvec_training_returns_axes():
    import matplotlib
    matplotlib.use("Agg", force=True)
    from omicverse.micro import simulate_paired, MMvec, plot_mmvec_training

    mb, mt, _ = simulate_paired(n_samples=18, seed=3)
    model = MMvec(n_latent=2, epochs=40, val_frac=0.2,
                  patience=100, seed=0).fit(mb, mt)
    ax = plot_mmvec_training(model)
    assert ax is not None and hasattr(ax, "plot")


def test_plot_cooccurrence_returns_axes():
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt  # noqa: F401
    from omicverse.micro import plot_cooccurrence
    df = pd.DataFrame(
        np.random.default_rng(0).normal(size=(8, 6)),
        index=[f"m{i}" for i in range(8)],
        columns=[f"x{j}" for j in range(6)],
    )
    ax = plot_cooccurrence(df, top_n=None)
    assert ax is not None


# ---------------------------------------------------------------------------
# fetch_franzosa_ibd_2019 — opt-in; runs only against a cached copy or when
# the tester sets OMICVERSE_NET_TESTS=1.
# ---------------------------------------------------------------------------


@requires_franzosa
def test_fetch_franzosa_ibd_2019_shape_and_alignment(tmp_path):
    """Validate the curated Franzosa 2019 fetcher: shapes, aligned obs,
    parsed taxonomy/annotation columns, three-arm cohort split."""
    import os
    from omicverse.micro import fetch_franzosa_ibd_2019

    cache = "/scratch/users/steorra/analysis/omicverse_dev/cache/franzosa_2019"
    data_dir = cache if _has_franzosa_cache() else str(tmp_path)
    mb, mt = fetch_franzosa_ibd_2019(data_dir=data_dir)

    assert mb.shape == (220, 11720)
    assert mt.shape == (220, 8848)
    assert list(mb.obs_names) == list(mt.obs_names)

    # microbe var: parsed GTDB taxonomy + full-string fallback
    for col in ("domain", "phylum", "class", "order",
                "family", "genus", "species", "taxonomy"):
        assert col in mb.var.columns, col

    # metabolite var: cluster id + name
    assert "cluster" in mt.var.columns and "name" in mt.var.columns
    assert mt.var["name"].notna().sum() > 0

    # Three-arm cohort: CD / UC / Control
    assert set(mb.obs["Study.Group"].unique()) == {"CD", "UC", "Control"}

    # Default microbe_count_scale=1e6 → integer pseudo-counts summing near 1M
    sums = np.asarray(mb.X).sum(axis=1)
    assert np.issubdtype(mb.X.dtype, np.integer)
    assert 9e5 < float(sums.mean()) < 1.1e6


def test_plot_method_comparison_requires_at_least_one_method():
    from omicverse.micro import plot_paired_method_comparison
    truth = pd.DataFrame({
        "microbe":    ["ASV_0"],
        "metabolite": ["MET_0"],
        "effect":     [1.5],
    })
    with pytest.raises(ValueError, match="at least one"):
        plot_paired_method_comparison(truth)
