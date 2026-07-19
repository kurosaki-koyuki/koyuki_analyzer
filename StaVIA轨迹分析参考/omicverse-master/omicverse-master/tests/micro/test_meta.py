"""Unit tests for ov.micro.combine_studies + meta_da."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _skbio_available() -> bool:
    try:
        import skbio  # noqa: F401
    except ImportError:
        return False
    return True


def _pydeseq2_available() -> bool:
    try:
        import pydeseq2  # noqa: F401
    except ImportError:
        return False
    return True


requires_skbio = pytest.mark.skipif(
    not _skbio_available(),
    reason="scikit-bio not installed (install the [tests] extra)",
)
requires_pydeseq2 = pytest.mark.skipif(
    not _pydeseq2_available(),
    reason="pydeseq2 not installed (install the [tests] extra)",
)


def _make_study(n_per_group=4, n_features=8, seed=0,
                feature_prefix="A", group_label=("CTRL", "CASE"),
                effect=None):
    """Build a (samples × features) AnnData with group metadata.

    ``effect`` optionally: dict {feature_idx: multiplier} applied to the
    CASE group to plant a ground-truth DA signal.
    """
    import anndata as ad
    from scipy import sparse
    rng = np.random.default_rng(seed)
    n = 2 * n_per_group
    X = rng.integers(50, 500, size=(n, n_features)).astype(np.int32)
    if effect:
        for feat_idx, mult in effect.items():
            X[n_per_group:, feat_idx] = (
                X[n_per_group:, feat_idx] * mult
            ).astype(np.int32)
    obs = pd.DataFrame({
        "group": [group_label[0]] * n_per_group + [group_label[1]] * n_per_group,
    }, index=[f"{feature_prefix}_S{i}" for i in range(n)])
    var = pd.DataFrame({
        "genus":   [f"{feature_prefix}g{i}" if i < 3 else f"sharedg{i}" for i in range(n_features)],
        "domain":  ["Bacteria"] * n_features,
        "phylum":  [""] * n_features,
        "class":   [""] * n_features,
        "order":   [""] * n_features,
        "family":  [""] * n_features,
        "species": [""] * n_features,
    }, index=[f"{feature_prefix}_ASV{i}" for i in range(n_features)])
    return ad.AnnData(X=sparse.csr_matrix(X), obs=obs, var=var)


# ---------------------------------------------------------------------------
# combine_studies
# ---------------------------------------------------------------------------


def test_combine_studies_union_and_study_label():
    from omicverse.micro import combine_studies
    a = _make_study(feature_prefix="A", seed=1)
    b = _make_study(feature_prefix="B", seed=2)
    merged = combine_studies([a, b], study_names=["A", "B"], rank="genus")
    # Each study contributes 3 unique + 5 shared genera → 11 features total.
    assert merged.shape[0] == a.shape[0] + b.shape[0]
    assert "study" in merged.obs.columns
    assert set(merged.obs["study"]) == {"A", "B"}
    # Union of genera: Ag0, Ag1, Ag2, Bg0, Bg1, Bg2, sharedg{3..7}
    names = set(merged.var_names)
    assert "Ag0" in names and "Bg0" in names
    assert "sharedg3" in names


def test_combine_studies_zero_fill_for_absent_features():
    from omicverse.micro import combine_studies
    a = _make_study(feature_prefix="A", seed=11)
    b = _make_study(feature_prefix="B", seed=22)
    merged = combine_studies([a, b], study_names=["A", "B"], rank="genus")
    # In merged, a column that originates only from study A must be
    # all-zero for study-B rows (and vice versa).
    X = merged.X.toarray()
    b_mask = merged.obs["study"].values == "B"
    ag0 = merged.var_names.get_loc("Ag0")
    assert X[b_mask, ag0].sum() == 0
    a_mask = merged.obs["study"].values == "A"
    bg0 = merged.var_names.get_loc("Bg0")
    assert X[a_mask, bg0].sum() == 0


def test_combine_studies_default_study_names():
    from omicverse.micro import combine_studies
    a = _make_study(feature_prefix="A", seed=3)
    b = _make_study(feature_prefix="B", seed=4)
    merged = combine_studies([a, b], rank="genus")
    assert set(merged.obs["study"]) == {"study_0", "study_1"}


def test_combine_studies_rejects_empty_list():
    from omicverse.micro import combine_studies
    with pytest.raises(ValueError, match="empty"):
        combine_studies([])


def test_combine_studies_rejects_mismatched_names():
    from omicverse.micro import combine_studies
    a = _make_study()
    with pytest.raises(ValueError, match="length"):
        combine_studies([a, a], study_names=["only-one"], rank="genus")


# ---------------------------------------------------------------------------
# meta_da
# ---------------------------------------------------------------------------


def test_meta_da_rejects_unknown_method():
    from omicverse.micro import meta_da
    a = _make_study()
    with pytest.raises(ValueError, match="method="):
        meta_da([a], group_key="group", method="bogus")


def test_meta_da_rejects_unknown_combine():
    from omicverse.micro import meta_da
    a = _make_study()
    with pytest.raises(ValueError, match="combine="):
        meta_da([a], group_key="group", method="wilcoxon",
                combine="max-likelihood-or-whatever")


def test_meta_da_wilcoxon_returns_expected_columns():
    """Wilcoxon has no real SE, but meta_da should still produce the schema."""
    from omicverse.micro import meta_da
    studies = [
        _make_study(feature_prefix="A", seed=1,
                    effect={0: 3.0, 1: 2.5}),
        _make_study(feature_prefix="A", seed=2,
                    effect={0: 3.2, 1: 2.6}),
        _make_study(feature_prefix="A", seed=3,
                    effect={0: 2.9, 1: 2.7}),
    ]
    out = meta_da(studies, group_key="group",
                  group_a="CTRL", group_b="CASE",
                  method="wilcoxon", rank="genus",
                  min_prevalence=0.1)
    for col in ("feature", "combined_lfc", "combined_se", "z",
                "p_value", "fdr_bh", "n_studies", "Q", "I2", "tau2"):
        assert col in out.columns, col
    # Per-study traceability columns
    assert "lfc_study_0" in out.columns and "se_study_2" in out.columns
    # All three cohorts planted the same signal on features 0 and 1 → they
    # should be ranked high (low fdr_bh). Feature labels after genus
    # collapse are "Ag0", "Ag1".
    top2 = set(out.head(4)["feature"])
    assert {"Ag0", "Ag1"} & top2


@requires_pydeseq2
def test_meta_da_deseq2_recovers_planted_signal():
    """DESeq2 meta-DA should rank the two planted features first."""
    from omicverse.micro import meta_da
    studies = [
        _make_study(feature_prefix="A", seed=10,
                    effect={0: 5.0, 1: 4.0}),
        _make_study(feature_prefix="A", seed=20,
                    effect={0: 4.5, 1: 4.5}),
        _make_study(feature_prefix="A", seed=30,
                    effect={0: 5.5, 1: 3.5}),
    ]
    out = meta_da(studies, group_key="group",
                  group_a="CTRL", group_b="CASE",
                  method="deseq2", rank="genus",
                  min_prevalence=0.1)
    # n_studies must be 3 for the planted features (each appears in all).
    top = out[out["feature"].isin(["Ag0", "Ag1"])]
    assert (top["n_studies"] == 3).all()
    # Direction: CASE > CTRL → combined_lfc positive.
    assert (top["combined_lfc"] > 0).all()


def test_meta_da_single_study_feature_has_nan_heterogeneity():
    """A taxon seen in only one study should produce NaN Q / I² / tau²."""
    from omicverse.micro import meta_da
    # Study A has feature Ag0 and Ag1 only; Study B has completely disjoint
    # genera (Bg0/Bg1) post-collapse.
    sa = _make_study(feature_prefix="A", seed=7)
    sb = _make_study(feature_prefix="B", seed=8)
    out = meta_da([sa, sb], group_key="group",
                  group_a="CTRL", group_b="CASE",
                  method="wilcoxon", rank="genus",
                  min_prevalence=0.1)
    # An A-only feature: Ag0. Only study A carries it.
    ag0 = out[out["feature"] == "Ag0"]
    assert not ag0.empty
    row = ag0.iloc[0]
    assert row["n_studies"] == 1
    assert np.isnan(row["Q"])
    assert np.isnan(row["I2"])
    assert np.isnan(row["tau2"])


@requires_pydeseq2
def test_meta_da_random_vs_fixed_effects():
    """Random-effects combine should widen SE (vs fixed) when studies disagree."""
    from omicverse.micro import meta_da
    # Plant a heterogeneous effect: study 2 has the opposite sign.
    studies = [
        _make_study(feature_prefix="A", seed=100, effect={0: 6.0}),
        _make_study(feature_prefix="A", seed=200, effect={0: 6.0}),
        # Inverse effect: make CASE lower than CTRL on feature 0.
        _make_study(feature_prefix="A", seed=300, effect={0: 0.2}),
    ]
    fe = meta_da(studies, group_key="group",
                 group_a="CTRL", group_b="CASE",
                 method="deseq2", rank="genus",
                 combine="fixed_effects", min_prevalence=0.1)
    re_ = meta_da(studies, group_key="group",
                  group_a="CTRL", group_b="CASE",
                  method="deseq2", rank="genus",
                  combine="random_effects", min_prevalence=0.1)
    # For the conflicted feature, random-effects SE must be >= fixed-effects SE.
    fe_row = fe[fe["feature"] == "Ag0"].iloc[0]
    re_row = re_[re_["feature"] == "Ag0"].iloc[0]
    assert re_row["combined_se"] >= fe_row["combined_se"] - 1e-9
    # I² should be high (>>50%) because studies disagree.
    assert re_row["I2"] > 0.5
