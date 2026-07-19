r"""``ov.epi.data`` — prebuilt reference genomes.

Re-exports epione's :class:`~epione.core.genome.Genome` instances. Access
a genome to lazily download (and cache) its FASTA + Gencode annotation via
pooch on first use::

    g = ov.epi.data.hg38
    g.fasta()        # downloads GRCh38 FASTA on first call
    g.annotation     # Gencode GFF3

Available: ``hg38``/``GRCh38``, ``hg19``/``GRCh37``, ``mm39``/``GRCm39``,
``mm10``/``GRCm38``, plus the ``Genome`` class.
"""

from __future__ import annotations

from ._utils import epione_module, import_epione

_NAMES = ("GRCh37", "GRCh38", "GRCm38", "GRCm39", "hg19", "hg38", "mm10", "mm39")


def __getattr__(name):
    import_epione()
    if name == "Genome":
        return epione_module("core").Genome
    data = epione_module("data")
    try:
        return getattr(data, name)
    except AttributeError as exc:
        raise AttributeError(f"ov.epi.data has no genome '{name}'") from exc


def __dir__():
    return list(_NAMES) + ["Genome"]


__all__ = list(_NAMES) + ["Genome"]
