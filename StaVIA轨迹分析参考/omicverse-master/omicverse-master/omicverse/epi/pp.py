r"""``ov.epi.pp`` — epigenomics preprocessing (wraps :mod:`epione.pp`).

Quality control, fragment ingestion and feature-matrix construction for
single-cell ATAC-seq, delegating to `epione <https://github.com/aristoteleo/epione>`_.
Each function imports epione internally, so importing omicverse stays cheap.

Typical scATAC ingest → QC → feature-matrix flow::

    import omicverse as ov
    frag = ov.epi.datasets.atac_pbmc5k_fragments()
    adata = ov.epi.pp.import_fragments(frag, chrom_sizes=ov.epi.data.hg38)
    genes = ov.epi.io.get_gene_annotation(ov.epi.data.hg38)
    ov.epi.pp.tsse(adata, genes)
    ov.epi.pp.frag_size_distr(adata)
    ov.epi.pp.nucleosome_signal(adata)
    adata = ov.epi.pp.qc(adata)
    ov.epi.pp.add_tile_matrix(adata)
    ov.epi.pp.select_features(adata, n_features=250000)
"""

from __future__ import annotations

from typing import Any, Optional

from ._utils import epione_module, make_passthrough_getattr


def import_fragments(fragment_file, chrom_sizes, *, file: Optional[str] = None,
                     min_num_fragments: int = 200, n_jobs: int = 1, **kwargs):
    r"""Scan a bgzipped ``fragments.tsv.gz`` into a per-cell QC AnnData.

    Wraps :func:`epione.pp.import_fragments`.

    Parameters
    ----------
    fragment_file
        Path (or list of paths) to a tabix-indexed ``fragments.tsv.gz``.
    chrom_sizes
        An :class:`epione.core.genome.Genome` (e.g. ``ov.epi.data.hg38``)
        or a ``{chrom: length}`` dict.
    file
        Optional output ``.h5ad`` path; when given, ``X`` is stored
        out-of-memory via anndataoom.
    min_num_fragments
        Minimum unique fragments per cell to retain.
    """
    return epione_module("pp").import_fragments(
        fragment_file, chrom_sizes, file=file,
        min_num_fragments=min_num_fragments, n_jobs=n_jobs, **kwargs)


def concat_samples(*args, **kwargs):
    r"""Concatenate multiple per-sample ATAC AnnData objects. Wraps :func:`epione.pp.concat_samples`."""
    return epione_module("pp").concat_samples(*args, **kwargs)


def frag_size_distr(adata, **kwargs):
    r"""Compute the fragment-size distribution (nucleosome periodicity QC).

    Wraps :func:`epione.pp.frag_size_distr`. Plot it with
    :func:`ov.epi.pl.frag_size_distr`.
    """
    return epione_module("pp").frag_size_distr(adata, **kwargs)


def nucleosome_signal(adata, n: Optional[int] = None, **kwargs):
    r"""Per-cell mono/nucleosome-free fragment ratio. Wraps :func:`epione.pp.nucleosome_signal`."""
    if n is None:
        return epione_module("pp").nucleosome_signal(adata, **kwargs)
    return epione_module("pp").nucleosome_signal(adata, n=n, **kwargs)


def tsse(adata, gene_anno, **kwargs):
    r"""TSS-enrichment score per cell (ArchR-style).

    Wraps :func:`epione.pp.tsse`. ``gene_anno`` is the per-gene frame from
    :func:`ov.epi.io.get_gene_annotation`.
    """
    return epione_module("pp").tsse(adata, gene_anno, **kwargs)


def tss_enrichment(adata, *args, **kwargs):
    r"""Alias kept for parity with epione's ``tss_enrichment``. Wraps :func:`epione.pp.tss_enrichment`."""
    return epione_module("pp").tss_enrichment(adata, *args, **kwargs)


def qc(adata, tresh: Optional[dict] = None, **kwargs):
    r"""One-step QC filter on fragment count / TSSe / nucleosome signal.

    Wraps :func:`epione.pp.qc`. ``tresh`` keys: ``fragment_counts_min``,
    ``fragment_counts_max``, ``TSS_score_min``, ``TSS_score_max``,
    ``Nucleosome_singal_max``.
    """
    return epione_module("pp").qc(adata, tresh=tresh, **kwargs)


def add_tile_matrix(adata, *, bin_size: int = 500, **kwargs):
    r"""Bin the genome into ``bin_size`` windows and count per-cell insertions.

    Wraps :func:`epione.pp.add_tile_matrix`. The tile matrix lands in ``adata.X``.
    """
    return epione_module("pp").add_tile_matrix(adata, bin_size=bin_size, **kwargs)


def select_features(adata, n_features: int = 500_000, **kwargs):
    r"""Select the most-accessible features for dimensionality reduction.

    Wraps :func:`epione.pp.select_features` (writes ``adata.var['selected']``).
    """
    return epione_module("pp").select_features(adata, n_features=n_features, **kwargs)


def make_peak_matrix(adata, *args, **kwargs):
    r"""Build a cell × peak count matrix from a peak set. Wraps :func:`epione.pp.make_peak_matrix`."""
    return epione_module("pp").make_peak_matrix(adata, *args, **kwargs)


def make_gene_matrix(adata, gene_anno, **kwargs):
    r"""Build a cell × gene activity matrix. Wraps :func:`epione.pp.make_gene_matrix`."""
    return epione_module("pp").make_gene_matrix(adata, gene_anno, **kwargs)


def scrublet(adata, *args, **kwargs):
    r"""Doublet scoring for scATAC. Wraps :func:`epione.pp.scrublet`."""
    return epione_module("pp").scrublet(adata, *args, **kwargs)


def neighbors(adata, *args, **kwargs):
    r"""Build the kNN graph on a low-dimensional representation. Wraps :func:`epione.pp.neighbors`."""
    return epione_module("pp").neighbors(adata, *args, **kwargs)


# Anything not explicitly wrapped above is forwarded to ``epione.pp``.
__getattr__ = make_passthrough_getattr("pp")

__all__ = [
    "import_fragments", "concat_samples", "frag_size_distr", "nucleosome_signal",
    "tsse", "tss_enrichment", "qc", "add_tile_matrix", "select_features",
    "make_peak_matrix", "make_gene_matrix", "scrublet", "neighbors",
]
