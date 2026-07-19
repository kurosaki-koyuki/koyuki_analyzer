r"""``ov.epi.bulk`` — bulk epigenomics tooling.

Passthrough to :mod:`epione.bulk` (``epione.bulk.atac`` /
``epione.bulk.hic``): the ``bigwig`` track/matrix engine, HOMER motif
enrichment (``find_motifs_genome`` / ``run_homer_motifs``), ArchR-style
footprinting (``footprint_archr``), and bulk Hi-C compartment/insulation/
loop analysis. Names resolve lazily from epione on first access.

>>> bw = ov.epi.bulk.bigwig()          # track viewer + matrix engine (a class)
>>> ov.epi.bulk.find_motifs_genome(...)
"""

from __future__ import annotations

from ._utils import make_passthrough_getattr

__getattr__ = make_passthrough_getattr("bulk")
