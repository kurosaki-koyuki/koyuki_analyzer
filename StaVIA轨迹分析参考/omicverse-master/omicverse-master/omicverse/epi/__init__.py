r"""``ov.epi`` — epigenomics analysis for omicverse.

A thin, omicverse-flavoured bridge over the `epione
<https://github.com/aristoteleo/epione>`_ package, giving single-cell and
bulk **epigenomics** (scATAC-seq, bulk ATAC/ChIP/CUT&RUN, footprinting,
chromVAR motif activity, peak-to-gene linkage, and Hi-C) a home next to
the rest of omicverse. Every wrapper imports epione internally and
delegates, so ``import omicverse`` stays light — epione's heavier
optional dependencies (snapatac2, anndataoom, cooler, MOODS, pysam) load
only when an ``ov.epi.*`` function is first called.

Submodules
----------
- :mod:`ov.epi.pp`        preprocessing — fragments, QC, tile/peak/gene matrices
- :mod:`ov.epi.tl`        tools — iterative LSI, clustering, gene scores, chromVAR, footprints, peak2gene, integration
- :mod:`ov.epi.pl`        plotting — QC, embeddings, differential, peak2gene, footprints, Hi-C
- :mod:`ov.epi.io`        readers — 10x ATAC, GTF/GFF, gene annotation, peak utilities
- :mod:`ov.epi.datasets`  fetch-on-demand example datasets (PBMC 5k/500 scATAC, PBMC 10k multiome)
- :mod:`ov.epi.data`      prebuilt reference genomes (hg38/hg19/mm39/mm10)
- :mod:`ov.epi.single`    single-cell ATAC/Hi-C specifics (macs3, pseudobulk, scHiCluster)
- :mod:`ov.epi.bulk`      bulk ATAC/ChIP/Hi-C specifics (bigwig engine, motif enrichment)
- :mod:`ov.epi.upstream`  FASTQ→BAM→bigwig/pairs→cool pipelines (CLI-driven)
- :mod:`ov.epi.utils`     genome accessors and region operations

Quick start (single-cell ATAC, fully reproducible on CPU)::

    import omicverse as ov

    frag  = ov.epi.datasets.atac_pbmc5k_fragments()
    adata = ov.epi.pp.import_fragments(frag, chrom_sizes=ov.epi.data.hg38)
    genes = ov.epi.io.get_gene_annotation(ov.epi.data.hg38)

    ov.epi.pp.tsse(adata, genes)
    ov.epi.pp.frag_size_distr(adata)
    ov.epi.pp.nucleosome_signal(adata)
    adata = ov.epi.pp.qc(adata)

    ov.epi.pp.add_tile_matrix(adata)
    ov.epi.pp.select_features(adata, n_features=250000)
    ov.epi.tl.iterative_lsi(adata, n_components=30)
    ov.epi.pp.neighbors(adata, use_rep='X_iterative_lsi')
    ov.epi.tl.clusters(adata, method='leiden', use_rep='X_iterative_lsi')
    ov.epi.tl.umap(adata)
    ov.epi.pl.umap(adata, color='leiden')
"""

from __future__ import annotations

from . import pp, tl, pl, io, datasets, data, single, bulk, upstream, utils
from ._utils import import_epione


def check_epione(verbose: bool = True):
    """Check that the backing ``epione`` package is importable.

    Returns the epione version string on success; raises an informative
    :class:`ImportError` (with an install hint) otherwise.
    """
    epi = import_epione()
    ver = getattr(epi, "__version__", None)
    if ver is None:
        try:
            from importlib.metadata import version as _v
            ver = _v("epione")
        except Exception:
            ver = "unknown"
    if verbose:
        print(f"epione is available (version {ver}); ov.epi is ready.")
    return ver


__all__ = [
    "pp", "tl", "pl", "io", "datasets", "data",
    "single", "bulk", "upstream", "utils", "check_epione",
]
