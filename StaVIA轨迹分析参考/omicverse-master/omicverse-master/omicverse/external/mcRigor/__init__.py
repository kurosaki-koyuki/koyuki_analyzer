"""Pure-Python port of mcRigor (Hou & Li, Nat Commun 2025).

Reference
---------
Hou X, Li JJ. *Rigorously detecting dubious metacells in single-cell genomics.*
Nature Communications 16, 5236 (2025).
https://doi.org/10.1038/s41467-025-63626-5

Original (R + Rcpp) implementation: https://github.com/JSB-UCLA/mcRigor

This port faithfully reimplements the double-permutation null test (the
``mc_indpd_stats_cpp`` Frobenius statistic of ``Σ̂ - I``) plus the
size-stratified threshold and the γ-tradeoff selector in pure numpy, so
omicverse users can call ``ov.single.MetaCell.check_rigor()`` on the
output of *any* partitioner without an R install.
"""

from .rigor import (
    RigorReport,
    mc_indpd_stats,
    rigor_detect,
    rigor_optimize,
)

__all__ = [
    "RigorReport",
    "mc_indpd_stats",
    "rigor_detect",
    "rigor_optimize",
]
