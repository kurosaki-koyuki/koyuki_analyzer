r"""``ov.epi.single`` — single-cell-specific epigenomics tooling.

Passthrough to :mod:`epione.single` (``epione.single.atac`` /
``epione.single.hic``): scATAC peak calling (``macs3``), pseudobulk
generation, and single-cell Hi-C imputation/embedding. Names resolve
lazily from epione on first access.

>>> ov.epi.single.macs3(adata, groupby='leiden', ...)
>>> ov.epi.single.pseudobulk(adata, groupby='cell_type')
"""

from __future__ import annotations

from ._utils import make_passthrough_getattr

__getattr__ = make_passthrough_getattr("single")
