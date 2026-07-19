r"""``pyMetabo`` — AnnData-native lifecycle class for metabolomics QC/stats.

Same lifecycle as ``omicverse.pp._scdblfinder.ScDblFinder`` and
``omicverse.single.Milo`` — a class that holds the AnnData, exposes
chainable methods for each pipeline stage, and stashes intermediate
artifacts on ``self`` for later inspection/plotting.

Usage
-----
>>> from omicverse.metabol import pyMetabo, read_metaboanalyst
>>> # group_col is required — pass the factor column name from your CSV
>>> adata = read_metaboanalyst("human_cachexia.csv", group_col="Muscle loss")
>>> m = pyMetabo(adata)
>>> (m.impute(method="qrilc", seed=0)
...    .normalize(method="pqn")
...    .transform(method="log")
...    .differential(method="welch_t", log_transformed=True)
...    .transform(method="pareto", stash_raw=False)
...    .plsda(n_components=2))
>>> m.deg_table.head()
>>> m.plsda_result.to_vip_table(m.adata.var_names).head()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from anndata import AnnData

from . import _impute as _imp
from . import _norm as _norm
from . import _plsda as _pls
from . import _qc as _qc_mod
from . import _stats as _stats_mod
from . import _transform as _tf

from .._registry import register_function


@register_function(
    aliases=['pyMetabo', 'metabolomics_pipeline', '代谢组学流水线'],
    category='metabolomics',
    description='AnnData-native lifecycle class for metabolomics QC + stats; '
                'chainable impute / normalize / transform / differential / '
                'plsda / opls_da on a single seeded pipeline.',
    examples=[
        "m = ov.metabol.pyMetabo(adata)"
        ".impute(method='qrilc').normalize(method='pqn')"
        ".transform(method='log').differential(group_col='group',"
        " group_a='case', group_b='ctrl', log_transformed=True)",
    ],
    related=[
        'metabol.read_metaboanalyst', 'metabol.impute', 'metabol.normalize',
        'metabol.transform', 'metabol.differential', 'metabol.plsda',
        'metabol.opls_da',
    ],
)
@dataclass
class pyMetabo:
    """Lifecycle class for a metabolomics analysis.

    Attributes populated as the pipeline runs
    ------------------------------------------
    adata : the current state of the AnnData (updated in place on each call)
    raw   : the original AnnData handed in at construction (never mutated)
    deg_table : DataFrame returned by ``differential()``
    plsda_result : PLSDAResult from ``plsda()`` / ``opls_da()``
    """

    adata: AnnData
    random_state: int = 0
    raw: AnnData = field(init=False)
    deg_table: Optional[pd.DataFrame] = field(default=None, init=False)
    plsda_result: Optional[_pls.PLSDAResult] = field(default=None, init=False)

    def __post_init__(self):
        # Freeze the input for provenance; we always operate on self.adata
        self.raw = self.adata.copy()

    # ------------------------------------------------------------------
    # preprocessing stages
    # ------------------------------------------------------------------
    @register_function(
        aliases=['pyMetabo.cv_filter', 'pymetabo_cv_filter'],
        category='metabolomics',
        description='pyMetabo chainable: drop features with QC coefficient-of-variation above cv_threshold.',
        examples=["m.cv_filter(qc_mask=qc_bool, cv_threshold=0.30)"],
        related=['metabol.cv_filter', 'metabol.pyMetabo'],
    )
    def cv_filter(self, *, qc_mask, cv_threshold: float = 0.30) -> "pyMetabo":
        """Drop features with QC coefficient-of-variation above ``cv_threshold``.

        Thin wrapper around :func:`omicverse.metabol.cv_filter` that keeps the
        chainable lifecycle. Operates on ``self.adata`` in place and returns
        ``self`` so calls can be composed (``m.cv_filter(...).normalize(...)``).
        See the underlying function for the QC-mask conventions and the
        across='qc'|'all' default.
        """
        self.adata = _qc_mod.cv_filter(self.adata, qc_mask=qc_mask,
                                       cv_threshold=cv_threshold)
        return self

    @register_function(
        aliases=['pyMetabo.drift_correct', 'pymetabo_drift_correct'],
        category='metabolomics',
        description='pyMetabo chainable: correct injection-order drift via LOESS on QC samples.',
        examples=["m.drift_correct(injection_order='order', qc_mask=qc_bool, frac=0.5)"],
        related=['metabol.drift_correct', 'metabol.pyMetabo'],
    )
    def drift_correct(self, *, injection_order, qc_mask, frac: float = 0.5) -> "pyMetabo":
        """Correct injection-order drift via LOESS regression on QC samples.

        Thin wrapper around :func:`omicverse.metabol.drift_correct`. Pass the
        injection-order column name (or array) and a boolean QC mask;
        ``frac`` is the LOESS smoothing window. Returns ``self``.
        """
        self.adata = _qc_mod.drift_correct(
            self.adata, injection_order=injection_order,
            qc_mask=qc_mask, frac=frac,
        )
        return self

    @register_function(
        aliases=['pyMetabo.blank_filter', 'pymetabo_blank_filter'],
        category='metabolomics',
        description='pyMetabo chainable: drop features whose mean signal is not ratio× the blank mean (LC-MS contaminant pruning).',
        examples=["m.blank_filter(blank_mask=blank_bool, ratio=3.0)"],
        related=['metabol.blank_filter', 'metabol.pyMetabo'],
    )
    def blank_filter(self, *, blank_mask, ratio: float = 3.0) -> "pyMetabo":
        """Drop features whose mean signal isn't ``ratio``× the blank mean.

        Thin wrapper around :func:`omicverse.metabol.blank_filter`. Used to
        purge LC-MS contaminants — features that are on in process blanks
        at comparable intensity get filtered. Returns ``self``.
        """
        self.adata = _qc_mod.blank_filter(self.adata, blank_mask=blank_mask, ratio=ratio)
        return self

    @register_function(
        aliases=['pyMetabo.impute', 'pymetabo_impute'],
        category='metabolomics',
        description='pyMetabo chainable: impute missing values; method qrilc (MNAR) / knn (MAR) / half_min / zero.',
        examples=["m.impute(method='qrilc', seed=0)"],
        related=['metabol.impute', 'metabol.pyMetabo'],
    )
    def impute(self, *, method: str = "qrilc", seed: Optional[int] = None,
               **kwargs) -> "pyMetabo":
        """Impute missing values in ``adata.X`` and return ``self``.

        Thin wrapper around :func:`omicverse.metabol.impute`. Choose
        ``method`` based on the missingness mechanism — ``'knn'`` for
        missing-at-random, ``'qrilc'`` for missing-not-at-random
        (left-censored below detection limit), ``'half_min'`` /
        ``'zero'`` for fast baselines. Reproducibility is preserved by
        falling back to ``self.random_state`` when ``seed`` is ``None``.
        Extra kwargs (``missing_threshold``, ``n_neighbors``, ``q``) are
        forwarded.
        """
        # Default to the class's own random_state so the chainable pipeline
        # is reproducible under a single seed.
        if seed is None:
            seed = self.random_state
        self.adata = _imp.impute(self.adata, method=method, seed=seed, **kwargs)
        return self

    @register_function(
        aliases=['pyMetabo.normalize', 'pymetabo_normalize'],
        category='metabolomics',
        description='pyMetabo chainable: per-sample normalization (PQN/TIC/median/MSTUS) — run after imputation, before transform.',
        examples=["m.normalize(method='pqn')"],
        related=['metabol.normalize', 'metabol.pyMetabo'],
    )
    def normalize(self, *, method: str = "pqn", **kwargs) -> "pyMetabo":
        """Normalize each sample row to correct dilution and return ``self``.

        Thin wrapper around :func:`omicverse.metabol.normalize`. Default
        ``'pqn'`` (Probabilistic Quotient Normalization) is the canonical
        choice for NMR/LC-MS metabolomics; ``'tic'`` / ``'median'`` /
        ``'mstus'`` are alternatives. Run **after** imputation, **before**
        feature-level transformation.
        """
        self.adata = _norm.normalize(self.adata, method=method, **kwargs)
        return self

    @register_function(
        aliases=['pyMetabo.transform', 'pymetabo_transform'],
        category='metabolomics',
        description='pyMetabo chainable: feature-level transformation (log / glog / autoscale / pareto). Run log → pareto for univariate-then-multivariate flow.',
        examples=[
            "m.transform(method='log')",
            "m.transform(method='pareto', stash_raw=False)",
        ],
        related=['metabol.transform', 'metabol.pyMetabo'],
    )
    def transform(self, *, method: str = "log", **kwargs) -> "pyMetabo":
        """Apply a feature-level transformation and return ``self``.

        Thin wrapper around :func:`omicverse.metabol.transform`. Typical
        chain is ``log`` (variance stabilisation) for univariate stats,
        followed later by ``pareto`` (centring + sqrt(SD) scaling) for
        multivariate (PLS-DA / OPLS-DA) input. ``stash_raw=True`` keeps
        the previous matrix in ``adata.layers`` so the chain is reversible.
        """
        self.adata = _tf.transform(self.adata, method=method, **kwargs)
        return self

    # ------------------------------------------------------------------
    # analysis stages
    # ------------------------------------------------------------------
    @register_function(
        aliases=['pyMetabo.differential', 'pymetabo_differential'],
        category='metabolomics',
        description='pyMetabo chainable: two-group univariate test (welch_t / mannwhitney / paired_t); stores result on self.deg_table.',
        examples=[
            "m.differential(group_col='group', group_a='case', group_b='ctrl', method='welch_t', log_transformed=True)",
        ],
        related=['metabol.differential', 'metabol.pyMetabo'],
    )
    def differential(
        self, *,
        group_col: str = "group", group_a: Optional[str] = None,
        group_b: Optional[str] = None, method: str = "welch_t",
        log_transformed: bool = True,
    ) -> "pyMetabo":
        """Two-group univariate test across all metabolites; stores ``self.deg_table``.

        Thin wrapper around :func:`omicverse.metabol.differential`. Set
        ``log_transformed=True`` if ``transform(method='log')`` was already
        called — fold-changes are then computed in linear space from the
        un-logged means. Result is a DataFrame keyed by metabolite with
        ``log2fc`` / ``pvalue`` / ``padj`` (BH-FDR) / ``mean_a``,
        ``mean_b``, accessible via ``self.deg_table``.
        """
        self.deg_table = _stats_mod.differential(
            self.adata, group_col=group_col, group_a=group_a, group_b=group_b,
            method=method, log_transformed=log_transformed,
        )
        return self

    @register_function(
        aliases=['pyMetabo.plsda', 'pymetabo_plsda'],
        category='metabolomics',
        description='pyMetabo chainable: fit PLS-DA on Pareto-scaled data; stores result on self.plsda_result.',
        examples=["m.plsda(n_components=2, group_col='group')"],
        related=['metabol.plsda', 'metabol.pyMetabo'],
    )
    def plsda(self, *, n_components: int = 2, group_col: str = "group",
              group_a: Optional[str] = None, group_b: Optional[str] = None,
              scale: bool = False) -> "pyMetabo":
        """Fit PLS-DA and stash the result on ``self.plsda_result``.

        Thin wrapper around :func:`omicverse.metabol.plsda`. Best run after
        ``transform(method='pareto')`` so the multivariate model sees
        Pareto-scaled features. ``scale=False`` because Pareto already
        handled it. Returns ``self``; downstream call ``.vip_table()`` for
        VIP-ranked features.
        """
        self.plsda_result = _pls.plsda(
            self.adata, group_col=group_col, group_a=group_a, group_b=group_b,
            n_components=n_components, scale=scale,
        )
        return self

    @register_function(
        aliases=['pyMetabo.opls_da', 'pymetabo_opls_da'],
        category='metabolomics',
        description='pyMetabo chainable: fit OPLS-DA (one predictive + n_ortho orthogonal components); stores result on self.plsda_result.',
        examples=["m.opls_da(n_ortho=1, group_col='group')"],
        related=['metabol.opls_da', 'metabol.pyMetabo'],
    )
    def opls_da(self, *, n_ortho: int = 1, group_col: str = "group",
                group_a: Optional[str] = None, group_b: Optional[str] = None,
                scale: bool = False) -> "pyMetabo":
        """Fit OPLS-DA (one predictive + ``n_ortho`` orthogonal components).

        Thin wrapper around :func:`omicverse.metabol.opls_da`. Separates
        class-discriminating signal (predictive component) from
        within-class variation (orthogonal components), giving cleaner
        S-plots and VIP scores than vanilla PLS-DA on heterogenous
        cohorts. Result lands on ``self.plsda_result``.
        """
        self.plsda_result = _pls.opls_da(
            self.adata, group_col=group_col, group_a=group_a, group_b=group_b,
            n_ortho=n_ortho, scale=scale,
        )
        return self

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------
    @register_function(
        aliases=['pyMetabo.vip_table', 'pymetabo_vip'],
        category='metabolomics',
        description='pyMetabo accessor: VIP-sorted DataFrame after a PLS-DA / OPLS-DA fit; raises if neither has been called.',
        examples=["m.vip_table().head(15)"],
        related=['metabol.pyMetabo', 'metabol.vip_bar'],
    )
    def vip_table(self) -> pd.DataFrame:
        """Return VIP scores per metabolite — requires a prior PLS-DA / OPLS-DA fit.

        VIP > 1 is the canonical importance threshold; metabolites are
        sorted descending. Raises ``RuntimeError`` if ``plsda()`` or
        ``opls_da()`` hasn't been called yet.
        """
        if self.plsda_result is None:
            raise RuntimeError("call .plsda() or .opls_da() first")
        return self.plsda_result.to_vip_table(self.adata.var_names)

    @register_function(
        aliases=['pyMetabo.significant_metabolites', 'pymetabo_sig_metabolites'],
        category='metabolomics',
        description='pyMetabo accessor: subset of self.deg_table at padj < padj_thresh and |log2fc| >= log2fc_thresh.',
        examples=["m.significant_metabolites(padj_thresh=0.10, log2fc_thresh=0.3)"],
        related=['metabol.pyMetabo', 'metabol.differential', 'metabol.volcano'],
    )
    def significant_metabolites(
        self, *, padj_thresh: float = 0.05, log2fc_thresh: float = 1.0
    ) -> pd.DataFrame:
        """Filter ``self.deg_table`` to padj < ``padj_thresh`` and |log2fc| ≥ ``log2fc_thresh``.

        Convenience selector — equivalent to the standard volcano-plot
        cutoffs. Raises ``RuntimeError`` if ``differential()`` hasn't run.
        For small-cohort metabolomics studies, consider relaxing
        ``padj_thresh`` (e.g. 0.10–0.20) since BH-FDR is conservative.
        """
        if self.deg_table is None:
            raise RuntimeError("call .differential() first")
        d = self.deg_table
        return d[(d["padj"] < padj_thresh) & (d["log2fc"].abs() >= log2fc_thresh)]
