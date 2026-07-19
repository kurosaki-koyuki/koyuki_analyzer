"""Integration tests for the ``ov.protein`` module.

Covers:
- Lazy import + module surface (read_*, qc_filter, normalize, impute, de, enrich, volcano)
- Synthetic MaxQuant-like AnnData → full pipeline (qc → normalize → impute → de)
- Each ``de(method=...)`` branch runs (deqms / limma / wilcoxon / welch_t)
- Each ``impute(method=...)`` branch runs (mindet / minprob / qrilc / half_min / zero)
- @register_function metadata visible in ov.find_function / list_functions

These are smoke tests that don't require R — algorithmic correctness is
covered by the standalone py-imputeLCMD / py-DEqMS test suites.
"""
from __future__ import annotations

import importlib.util
import warnings

import numpy as np
import pandas as pd
import pytest

# Quiet expected DeqMS / scipy warnings during synthetic test runs.
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ov.protein dispatches to standalone backend packages (pyimputelcmd,
# pydeqms, pyproda, pymsstats). They are the ``omicverse[protein]`` /
# ``omicverse[tests]`` optional dependencies — skip this whole file
# gracefully if they are not installed rather than erroring.
_BACKENDS = ["pyimputelcmd", "pydeqms", "pyproda", "pymsstats"]
_MISSING_BACKENDS = [m for m in _BACKENDS
                     if importlib.util.find_spec(m) is None]
pytestmark = pytest.mark.skipif(
    bool(_MISSING_BACKENDS),
    reason=f"ov.protein backend packages not installed: {_MISSING_BACKENDS}",
)


def _make_anndata(seed: int = 0, n_proteins: int = 200, n_per_group: int = 6):
    """Synthetic 12-sample LFQ-style AnnData with NaN dropouts and DE."""
    from anndata import AnnData

    rng = np.random.default_rng(seed)
    n_samples = 2 * n_per_group
    base = rng.normal(20.0, 1.5, n_proteins)
    count = rng.integers(1, 20, n_proteins).astype(float)
    sigma = 0.5 + 0.5 / np.sqrt(count)
    is_de = rng.uniform(size=n_proteins) < 0.15
    delta = np.where(is_de, rng.choice([-1, 1], n_proteins) * 1.0, 0.0)

    X = np.zeros((n_samples, n_proteins))  # samples × proteins
    for g in [0, 1]:
        mu = base + (delta if g else 0)
        X[g * n_per_group:(g + 1) * n_per_group, :] = (
            rng.normal(mu[None, :], sigma[None, :], (n_per_group, n_proteins))
        )
    X = 2.0 ** X  # raw intensities
    # Inject ~10% MNAR missingness at low intensities.
    threshold = np.quantile(X, 0.10)
    p_miss = np.exp(-(X / threshold) ** 2)
    X[rng.uniform(size=X.shape) < p_miss * 0.5] = np.nan
    X[X < threshold * 0.5] = np.nan

    obs = pd.DataFrame({
        "group": ["control"] * n_per_group + ["treated"] * n_per_group,
    }, index=[f"S{i:02d}" for i in range(n_samples)])
    var = pd.DataFrame({
        "peptides":   count,
        "Gene_names": [f"gene_{i:04d}" for i in range(n_proteins)],
        "is_de_true": is_de,
    }, index=[f"prot_{i:04d}" for i in range(n_proteins)])
    return AnnData(X=X, obs=obs, var=var)


# --------------------------------------------------------------------------- #
# Module surface                                                              #
# --------------------------------------------------------------------------- #

def test_module_loads_and_exposes_public_api():
    import omicverse as ov
    p = ov.protein
    for sym in (
        "read_maxquant", "read_diann", "read_fragpipe", "read_olink_npx",
        "read_wide", "qc_filter", "normalize", "impute", "de", "enrich",
        "volcano", "missing_pattern_plot", "abundance_rank_plot",
    ):
        assert hasattr(p, sym), f"ov.protein.{sym} missing"


def test_registry_sees_protein_module():
    from omicverse._registry import get_registry
    import omicverse.protein as _p
    _p._hydrate_registry()
    reg = get_registry()
    keys = [e for e in reg._registry.values()
            if "omicverse.protein" in str(e.get("module", ""))]
    assert len(keys) > 0, "no ov.protein functions registered"


# --------------------------------------------------------------------------- #
# Pipeline                                                                    #
# --------------------------------------------------------------------------- #

def test_full_pipeline_qc_normalize_impute_de_deqms():
    import omicverse as ov
    adata = _make_anndata(seed=0)
    # qc_filter (drops low-peptide proteins).
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    assert adata.n_vars > 0
    assert "n_valid_proteins" in adata.obs.columns
    # normalize (log2 + median centering).
    ov.protein.normalize(adata, method="median", log2=True)
    assert "raw" in adata.layers
    assert "log2" in adata.layers
    # impute (QRILC).
    ov.protein.impute(adata, method="qrilc", seed=0)
    assert not np.isnan(adata.X).any()
    # DE via DEqMS.
    res = ov.protein.de(adata, group="group", method="deqms",
                        count_var="peptides")
    assert {"gene", "logFC", "P.Value", "adj.P.Val"}.issubset(res.columns)
    assert res["P.Value"].notna().sum() > 0


@pytest.mark.parametrize("imp_method", ["mindet", "minprob", "qrilc",
                                          "half_min", "min", "zero",
                                          "knn", "mle", "svd",
                                          "mar", "mar_mnar", "auto"])
def test_impute_dispatch_each_method(imp_method):
    import omicverse as ov
    adata = _make_anndata(seed=1)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    ov.protein.normalize(adata, method="median", log2=True)
    ov.protein.impute(adata, method=imp_method, seed=0)
    assert not np.isnan(adata.X).any()


def test_model_selector_classifies_proteins():
    import omicverse as ov
    adata = _make_anndata(seed=11)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    ov.protein.normalize(adata, method="median", log2=True)
    mask, thr = ov.protein.model_selector(adata)
    assert mask.shape == (adata.n_vars,)
    assert mask.dtype == bool
    assert "is_mcar" in adata.var.columns
    assert np.isfinite(thr)


def test_normalize_equalize_medians():
    import omicverse as ov
    adata = _make_anndata(seed=12)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    ov.protein.normalize(adata, method="equalize_medians", log2=True)
    # After column-median equalisation, per-sample medians ~equal.
    medians = np.nanmedian(adata.X, axis=1)
    assert np.std(medians) < 0.1


def test_summarize_peptide_to_protein():
    """Peptide-level AnnData → protein-level AnnData via each method."""
    import omicverse as ov
    from anndata import AnnData
    rng = np.random.default_rng(20)
    n_proteins, n_pep_each, n_samples = 40, 3, 8
    n_peptides = n_proteins * n_pep_each
    # Build peptide-level matrix.
    base = rng.normal(20.0, 1.0, n_proteins)
    X = np.zeros((n_samples, n_peptides))
    protein_of = []
    for p in range(n_proteins):
        for k in range(n_pep_each):
            col = p * n_pep_each + k
            X[:, col] = 2.0 ** rng.normal(base[p] + rng.normal(0, 0.3), 0.3, n_samples)
            protein_of.append(f"prot_{p:03d}")
    obs = pd.DataFrame({"group": ["A"] * 4 + ["B"] * 4},
                       index=[f"S{i}" for i in range(n_samples)])
    var = pd.DataFrame({"Protein": protein_of},
                       index=[f"pep_{i:04d}" for i in range(n_peptides)])
    pep_adata = AnnData(X=X, obs=obs, var=var)
    for method in ["median", "median_sweeping", "medpolish", "tmp", "linear"]:
        prot = ov.protein.summarize(pep_adata, protein_col="Protein",
                                    method=method)
        assert prot.n_vars == n_proteins, f"{method}: wrong protein count"
        assert prot.n_obs == n_samples
        assert list(prot.obs["group"]) == list(pep_adata.obs["group"])


def test_contrast_matrix():
    import omicverse as ov
    C = ov.protein.contrast_matrix("treated-control", ["control", "treated"])
    # treated - control → [-1, +1] on [control, treated].
    arr = C.to_numpy() if hasattr(C, "to_numpy") else np.asarray(C)
    assert arr.shape[1] == 2
    row = arr[0]
    assert row[0] == -1 and row[1] == 1


def test_sample_size_runs():
    import omicverse as ov
    adata = _make_anndata(seed=21, n_proteins=120, n_per_group=6)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.4)
    ov.protein.normalize(adata, method="median", log2=True)
    ov.protein.impute(adata, method="qrilc", seed=0)
    tbl = ov.protein.sample_size(adata, group="group",
                                 desired_fc=(1.5, 2.0))
    assert len(tbl) >= 1


def test_impute_invalid_method_raises():
    import omicverse as ov
    adata = _make_anndata(seed=2)
    with pytest.raises(ValueError, match="method must be one of"):
        ov.protein.impute(adata, method="nope")


@pytest.mark.parametrize("de_method", ["deqms", "limma", "wilcoxon", "welch_t"])
def test_de_dispatch_each_method(de_method):
    import omicverse as ov
    adata = _make_anndata(seed=3)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    ov.protein.normalize(adata, method="median", log2=True)
    ov.protein.impute(adata, method="qrilc", seed=0)
    res = ov.protein.de(adata, group="group", method=de_method,
                        count_var="peptides")
    assert {"gene", "logFC", "P.Value", "adj.P.Val"}.issubset(res.columns)
    assert len(res) > 0


@pytest.mark.parametrize("mg_method", ["anova", "kruskal"])
def test_de_multigroup(mg_method):
    """Three-group omnibus tests run and return a sorted table."""
    import omicverse as ov
    from anndata import AnnData
    rng = np.random.default_rng(30)
    n_proteins, n_per = 100, 5
    n_samples = n_per * 3
    X = np.zeros((n_samples, n_proteins))
    base = rng.normal(20.0, 1.0, n_proteins)
    for g in range(3):
        X[g * n_per:(g + 1) * n_per] = rng.normal(
            base[None, :] + (g * 0.5), 0.4, (n_per, n_proteins),
        )
    obs = pd.DataFrame({"group": (["G0"] * n_per + ["G1"] * n_per
                                  + ["G2"] * n_per)},
                       index=[f"S{i}" for i in range(n_samples)])
    adata = AnnData(X=X, obs=obs,
                    var=pd.DataFrame(index=[f"p{i}" for i in range(n_proteins)]))
    res = ov.protein.de(adata, group="group", method=mg_method)
    assert {"gene", "P.Value", "adj.P.Val"}.issubset(res.columns)
    assert len(res) == n_proteins
    pv = res["P.Value"].dropna().to_numpy()
    assert (np.diff(pv) >= -1e-9).all()


def test_de_two_group_method_rejects_three_groups():
    import omicverse as ov
    from anndata import AnnData
    rng = np.random.default_rng(31)
    X = rng.normal(20, 1, (15, 50))
    obs = pd.DataFrame({"group": ["A"] * 5 + ["B"] * 5 + ["C"] * 5},
                       index=[f"S{i}" for i in range(15)])
    adata = AnnData(X=X, obs=obs,
                    var=pd.DataFrame(index=[f"p{i}" for i in range(50)]))
    with pytest.raises(ValueError, match="two-group test"):
        ov.protein.de(adata, group="group", method="welch_t")


def test_de_recovers_planted_de_proteins():
    """Top-N DE genes should overlap with the planted-true set."""
    import omicverse as ov
    adata = _make_anndata(seed=4, n_proteins=300, n_per_group=8)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.4)
    ov.protein.normalize(adata, method="median", log2=True)
    ov.protein.impute(adata, method="qrilc", seed=0)
    res = ov.protein.de(adata, group="group", method="deqms",
                        count_var="peptides")
    n_true = int(adata.var["is_de_true"].sum())
    if n_true == 0:
        pytest.skip("no DE proteins planted")
    top = set(res["gene"].head(n_true).astype(str))
    true_de_genes = set(adata.var.index[adata.var["is_de_true"]].astype(str))
    overlap = len(top & true_de_genes) / max(n_true, 1)
    assert overlap > 0.4, f"only {overlap:.1%} of top-{n_true} are true DE"


def test_volcano_returns_axes_and_does_not_crash():
    import matplotlib
    matplotlib.use("Agg")
    import omicverse as ov
    adata = _make_anndata(seed=5)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    ov.protein.normalize(adata, method="median", log2=True)
    ov.protein.impute(adata, method="qrilc", seed=0)
    res = ov.protein.de(adata, group="group", method="limma")
    ax = ov.protein.volcano(res, label_top=5)
    assert ax is not None


def test_missing_pattern_returns_stats():
    import omicverse as ov
    adata = _make_anndata(seed=6)
    stats = ov.protein.missing_pattern(adata)
    assert "protein_missing_frac" in stats
    assert "sample_missing_frac" in stats
    assert 0.0 <= stats["overall"] <= 1.0


def test_normalize_quantile_method():
    import omicverse as ov
    adata = _make_anndata(seed=7)
    ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.3)
    ov.protein.normalize(adata, method="quantile", log2=True)
    # After quantile norm, per-sample row medians should be approximately equal.
    medians = np.nanmedian(adata.X, axis=1)
    assert np.std(medians) < 0.05


def test_olink_npx_pipeline():
    """Synthetic Olink NPX data goes through the no-log2 path."""
    import omicverse as ov
    from anndata import AnnData
    rng = np.random.default_rng(8)
    n_proteins = 50
    n_samples = 16
    base = rng.normal(0.0, 2.0, n_proteins)
    delta = rng.choice([-1, 0, 1], n_proteins, p=[0.1, 0.8, 0.1]) * 1.0
    X = np.zeros((n_samples, n_proteins))
    for s in range(n_samples):
        g = 0 if s < 8 else 1
        X[s] = rng.normal(base + (delta if g else 0), 0.4)
    obs = pd.DataFrame({"group": ["G0"] * 8 + ["G1"] * 8},
                       index=[f"S{i:02d}" for i in range(n_samples)])
    var = pd.DataFrame(index=[f"prot_{i:04d}" for i in range(n_proteins)])
    adata = AnnData(X=X, obs=obs, var=var)
    # Olink NPX is already log2 — skip log2 step.
    ov.protein.normalize(adata, method="median", log2=False)
    # Olink data doesn't need imputation (no NPX dropouts typically).
    res = ov.protein.de(adata, group="group", method="welch_t")
    assert len(res) == n_proteins
