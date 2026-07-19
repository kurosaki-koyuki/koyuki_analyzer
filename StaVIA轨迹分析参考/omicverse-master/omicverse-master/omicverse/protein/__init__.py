"""
Proteomics analysis for omicverse — AnnData-native bulk LC-MS/MS &
Olink workflows.

``ov.protein`` is the analogue of ``ov.metabol`` for protein-level
quantitative proteomics: it consumes search-engine output
(MaxQuant ``proteinGroups.txt``, DIA-NN ``report.pg_matrix.tsv``,
FragPipe ``combined_protein.tsv``, Olink long NPX) and produces an
``AnnData`` with ``obs = samples``, ``var = proteins`` — the standard
omicverse convention. Downstream operations (impute, normalize,
differential expression, enrichment) are all dispatcher functions
that take ``method=`` as the algorithm selector.

The actual statistical machinery lives in the **standalone packages**
that omicverse ships as separate releases:

* :mod:`pyimputelcmd` — MinDet / MinProb / QRILC imputation (Lazar 2016)
* :mod:`pydeqms`       — peptide-count-aware moderated t (Zhu 2020)
* :mod:`pyproda`       — MNAR probabilistic DE (Ahlmann-Eltze 2020)
* :mod:`pyolinkanalyze`— Olink NPX QC + LMM
* :mod:`pymsstats`     — MaxQuant / DIA-NN DDA / DIA pipeline (Choi 2014)

Each is a thin sidecar package; ``ov.protein`` wraps them behind a
unified ``method=`` argument so users don't have to learn five
different APIs.

Quick-start
-----------
>>> import omicverse as ov
>>> adata = ov.protein.read_maxquant("proteinGroups.txt", sample_pattern=r"LFQ\\.intensity\\.(.+)")
>>> adata.obs["group"] = ["control"] * 6 + ["treated"] * 6
>>> ov.protein.qc_filter(adata, min_peptides=2)
>>> ov.protein.normalize(adata, method="median", log2=True)
>>> ov.protein.impute(adata, method="qrilc", seed=0)
>>> res = ov.protein.de(adata, group="group",
...                     method="deqms",
...                     count_var="peptides")
>>> ov.protein.volcano(res)

Pipeline stages
---------------
I/O                       ``read_maxquant``, ``read_diann``,
                          ``read_fragpipe``, ``read_olink_npx``
QC                        ``qc_filter`` (min peptides / valid values)
Imputation                ``impute`` (mindet / minprob / qrilc /
                          half_min / knn / zero)
Normalization             ``normalize`` (median / quantile / log2-only)
Differential expression   ``de`` (deqms / limma / proda / wilcoxon /
                          welch_t / olink_lmer / msstats)
Enrichment                ``enrich`` (forwards to ``ov.es``: ulm /
                          mlm / aucell / ora / gsea / …)
Plotting                  ``volcano``, ``missing_pattern_plot``,
                          ``abundance_rank_plot``

All algorithm-specific imports (``pyimputelcmd``, ``pydeqms`` …) are
deferred to call-time — ``import omicverse.protein`` does no heavy
work.
"""
from __future__ import annotations

import importlib as _importlib


# Lazy public surface — single source of truth for what's exposed.
_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    # I/O
    "read_maxquant":          (".io", "read_maxquant"),
    "read_diann":             (".io", "read_diann"),
    "read_fragpipe":          (".io", "read_fragpipe"),
    "read_olink_npx":         (".io", "read_olink_npx"),
    "read_wide":              (".io", "read_wide"),
    # Synthetic data (tutorials / tests)
    "simulate_lfq":           ("._simulate", "simulate_lfq"),
    # QC
    "qc_filter":              ("._qc", "qc_filter"),
    "missing_pattern":        ("._qc", "missing_pattern"),
    "model_selector":         ("._qc", "model_selector"),
    # Normalize
    "normalize":              ("._norm", "normalize"),
    # Peptide → protein summarization
    "summarize":              ("._summarize", "summarize"),
    # Imputation
    "impute":                 ("._impute", "impute"),
    # Study design / power
    "sample_size":            ("._design", "sample_size"),
    "contrast_matrix":        ("._design", "contrast_matrix"),
    # Differential expression
    "de":                     ("._de", "de"),
    # Enrichment (thin forwarder to ov.es)
    "enrich":                 ("._enrich", "enrich"),
    # Plotting
    "volcano":                (".plotting", "volcano"),
    "missing_pattern_plot":   (".plotting", "missing_pattern_plot"),
    "abundance_rank_plot":    (".plotting", "abundance_rank_plot"),
    "pca_plot":               (".plotting", "pca_plot"),
    "heatmap":                (".plotting", "heatmap"),
    "boxplot":                (".plotting", "boxplot"),
}

_LAZY_SUBMODULES = {"plotting"}

_REGISTRY_SUBMODULES = (
    ".io",
    "._simulate",
    "._qc",
    "._norm",
    "._summarize",
    "._impute",
    "._design",
    "._de",
    "._enrich",
    ".plotting",
)


def _hydrate_registry() -> None:
    """Force-import every @register_function-bearing submodule so the global
    registry sees ov.protein at export time. Called from
    :mod:`omicverse._registry._hydrate_registry_for_export`."""
    for mod in _REGISTRY_SUBMODULES:
        try:
            _importlib.import_module(mod, __name__)
        except Exception:
            # Optional backends (pydeqms, pyproda, statsmodels) may be missing —
            # register whatever loads cleanly.
            continue


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_path, attr_name = _LAZY_ATTRS[name]
        module = _importlib.import_module(module_path, __name__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    if name in _LAZY_SUBMODULES:
        module = _importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(list(globals().keys())
                      + list(_LAZY_ATTRS.keys())
                      + list(_LAZY_SUBMODULES)))


__version__ = "0.1.0"

__all__ = list(_LAZY_ATTRS.keys()) + list(_LAZY_SUBMODULES)
