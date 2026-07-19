r"""``ov.epi.upstream`` — FASTQ → BAM → bigwig / pairs → cool pipelines.

Passthrough to :mod:`epione.upstream`: aligner wrappers (bowtie2,
bwa-mem2), samtools/BAM utilities, MACS2 peak calling, Tn5 shifting,
reference preparation, and the Hi-C ``pairs``/``cool`` chain. These call
external command-line tools, so they are not exercised by the shipped
tutorials. Names resolve lazily from epione on first access.
"""

from __future__ import annotations

from ._utils import make_passthrough_getattr

__getattr__ = make_passthrough_getattr("upstream")
