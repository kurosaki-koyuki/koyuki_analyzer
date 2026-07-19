"""Pure-Python subset of Bioconductor limma.

The public names intentionally mirror the R package where possible.
Current coverage focuses on the core linear-model workflow used by
DEqMS and many expression analyses: ``voom -> lmFit -> contrasts.fit
-> eBayes -> topTable``.
"""

from .fit import (
    DuplicateCorrelation,
    EList,
    MArrayLM,
    TestResults,
    choose_lowess_span,
    contrasts_fit,
    decide_tests,
    duplicate_correlation,
    ebayes,
    lm_fit,
    remove_batch_effect,
    treat,
    top_table,
    voom,
)

lmFit = lm_fit
eBayes = ebayes
contrasts_fit = contrasts_fit
topTable = top_table
duplicateCorrelation = duplicate_correlation
removeBatchEffect = remove_batch_effect
treat = treat
decideTests = decide_tests

__all__ = [
    "MArrayLM",
    "EList",
    "DuplicateCorrelation",
    "TestResults",
    "lm_fit",
    "lmFit",
    "remove_batch_effect",
    "removeBatchEffect",
    "voom",
    "choose_lowess_span",
    "duplicate_correlation",
    "duplicateCorrelation",
    "decide_tests",
    "decideTests",
    "contrasts_fit",
    "eBayes",
    "ebayes",
    "treat",
    "top_table",
    "topTable",
]
