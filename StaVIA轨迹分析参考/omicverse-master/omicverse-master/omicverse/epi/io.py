r"""``ov.epi.io`` — epigenomics readers & region utilities.

Pure-format readers (10x ATAC matrices, GTF/GFF) plus coordinate ↔ gene
annotation and peak-set helpers, delegating to :mod:`epione.io` and
:mod:`epione.utils`. Each function imports epione internally.
"""

from __future__ import annotations

from ._utils import epione_module, make_passthrough_getattr


def read_ATAC_10x(*args, **kwargs):
    r"""Read a CellRanger / 10x scATAC matrix into AnnData. Wraps :func:`epione.io.read_ATAC_10x`."""
    return epione_module("io").read_ATAC_10x(*args, **kwargs)


def read_gtf(*args, **kwargs):
    r"""Read a GTF/GFF3 into a DataFrame. Wraps :func:`epione.io.read_gtf`."""
    return epione_module("io").read_gtf(*args, **kwargs)


def read_features(*args, **kwargs):
    r"""Read a feature/peak file. Wraps :func:`epione.io.read_features`."""
    return epione_module("io").read_features(*args, **kwargs)


def convert_gff_to_gtf(*args, **kwargs):
    r"""Convert GFF3 → GTF. Wraps :func:`epione.io.convert_gff_to_gtf`."""
    return epione_module("io").convert_gff_to_gtf(*args, **kwargs)


def get_gene_annotation(genome, **kwargs):
    r"""Parse a :class:`~epione.core.genome.Genome` into a per-gene TSS DataFrame.

    Wraps :func:`epione.io.get_gene_annotation`. The returned frame
    (chrom/start/end/strand, one row per gene) is the input expected by
    :func:`ov.epi.pp.tsse` and :func:`ov.epi.tl.add_gene_score_matrix`.
    """
    return epione_module("io").get_gene_annotation(genome, **kwargs)


def merge_peaks(*args, **kwargs):
    r"""Merge per-group peak calls into a unified non-overlapping set.

    Wraps :func:`epione.utils.merge_peaks`.
    """
    return epione_module("utils").merge_peaks(*args, **kwargs)


def save(*args, **kwargs):
    r"""Pickle/h5ad cache helper. Wraps :func:`epione.io.save`."""
    return epione_module("io").save(*args, **kwargs)


def load(*args, **kwargs):
    r"""Pickle/h5ad cache loader. Wraps :func:`epione.io.load`."""
    return epione_module("io").load(*args, **kwargs)


# Forward any other reader to epione.io (e.g. ``cached``).
__getattr__ = make_passthrough_getattr("io")

__all__ = [
    "read_ATAC_10x", "read_gtf", "read_features", "convert_gff_to_gtf",
    "get_gene_annotation", "merge_peaks", "save", "load",
]
