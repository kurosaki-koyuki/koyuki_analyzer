r"""``ov.epi.utils`` — epigenomics utilities & region operations.

Passthrough to :mod:`epione.utils`: genome accessors
(``utils.genome.hg38`` / ``hg19`` / ...), peak-set operations
(``merge_peaks``, ``annotate_peaks``, ``classify_peaks_by_overlap``),
gene-annotation parsing and AnnData on-disk helpers (``obs_to_pandas``).
Names resolve lazily from epione on first access.

>>> genes = ov.epi.utils.get_gene_annotation(ov.epi.data.hg38)
>>> obs = ov.epi.utils.obs_to_pandas(adata)   # pull a backed obs into memory
"""

from __future__ import annotations

from ._utils import make_passthrough_getattr

__getattr__ = make_passthrough_getattr("utils")
