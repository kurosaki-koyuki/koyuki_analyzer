r"""``ov.epi.tl`` — epigenomics analysis tools (wraps :mod:`epione.tl`).

Dimensionality reduction (iterative LSI), clustering, gene-activity
scores, peak-to-gene linkage, chromVAR motif deviations, footprinting and
cross-modality integration — all delegating to
`epione <https://github.com/aristoteleo/epione>`_. Each function imports
epione internally.

scATAC embedding → clustering → gene scores::

    ov.epi.tl.iterative_lsi(adata, n_components=30)
    ov.epi.pp.neighbors(adata, use_rep='X_iterative_lsi')
    ov.epi.tl.clusters(adata, method='leiden', use_rep='X_iterative_lsi')
    ov.epi.tl.umap(adata)
    ov.epi.tl.add_gene_score_matrix(adata, gene_anno)

chromVAR motif/TF activity::

    ov.epi.tl.build_motif_database(genome_fasta, out_dir)
    ov.epi.tl.add_motif_matrix(adata, motif_database=out_dir)
    ov.epi.tl.add_background_peaks(adata, genome_fasta=genome_fasta)
    ov.epi.tl.compute_deviations(adata)
"""

from __future__ import annotations

from typing import Any

from ._utils import epione_module, make_passthrough_getattr


# ---- dimensionality reduction / clustering ---------------------------------
def lsi(adata, *args, **kwargs):
    r"""Latent semantic indexing (single-pass). Wraps :func:`epione.tl.lsi`."""
    return epione_module("tl").lsi(adata, *args, **kwargs)


def iterative_lsi(adata, *, n_components: int = 30, iterations: int = 2,
                  var_features: int = 25000, **kwargs):
    r"""ArchR-style iterative LSI on a cell × tile/peak matrix.

    Wraps :func:`epione.tl.iterative_lsi`; stores the embedding in
    ``adata.obsm['X_iterative_lsi']`` by default.
    """
    return epione_module("tl").iterative_lsi(
        adata, n_components=n_components, iterations=iterations,
        var_features=var_features, **kwargs)


def clusters(adata, *args, **kwargs):
    r"""Leiden / Louvain / kmeans clustering on a representation. Wraps :func:`epione.tl.clusters`."""
    return epione_module("tl").clusters(adata, *args, **kwargs)


def umap(adata, *args, **kwargs):
    r"""UMAP embedding. Wraps :func:`epione.tl.umap`."""
    return epione_module("tl").umap(adata, *args, **kwargs)


def find_marker_features(adata, *args, **kwargs):
    r"""Rank marker peaks/features per group. Wraps :func:`epione.tl.find_marker_features`."""
    return epione_module("tl").find_marker_features(adata, *args, **kwargs)


def differential_peaks(*args, **kwargs):
    r"""Differential accessibility testing (pyDESeq2 backend). Wraps :func:`epione.tl.differential_peaks`."""
    return epione_module("tl").differential_peaks(*args, **kwargs)


# ---- gene activity / linkage -----------------------------------------------
def add_gene_score_matrix(adata, gene_anno, **kwargs):
    r"""ArchR-style gene-activity scores from tile accessibility.

    Wraps :func:`epione.tl.add_gene_score_matrix`.
    """
    return epione_module("tl").add_gene_score_matrix(adata, gene_anno, **kwargs)


def peak_to_gene(adata, *args, **kwargs):
    r"""Correlate peak accessibility with gene expression to link peaks→genes.

    Wraps :func:`epione.tl.peak_to_gene`. Visualise with
    :func:`ov.epi.pl.plot_peak2gene`.
    """
    return epione_module("tl").peak_to_gene(adata, *args, **kwargs)


def coaccessibility(adata, *args, **kwargs):
    r"""Peak co-accessibility (Cicero-style) links. Wraps :func:`epione.tl.coaccessibility`."""
    return epione_module("tl").coaccessibility(adata, *args, **kwargs)


# ---- motif / chromVAR ------------------------------------------------------
def build_motif_database(*args, **kwargs):
    r"""Scan a genome for motif hits, building a reusable motif database.

    Wraps :func:`epione.tl.build_motif_database`.
    """
    return epione_module("tl").build_motif_database(*args, **kwargs)


def query_motif_database(*args, **kwargs):
    r"""Query a prebuilt motif database for a set of peaks. Wraps :func:`epione.tl.query_motif_database`."""
    return epione_module("tl").query_motif_database(*args, **kwargs)


def add_motif_matrix(adata, *args, **kwargs):
    r"""Add a peak × motif membership matrix to ``adata``. Wraps :func:`epione.tl.add_motif_matrix`."""
    return epione_module("tl").add_motif_matrix(adata, *args, **kwargs)


def add_background_peaks(adata, *args, **kwargs):
    r"""Sample GC/accessibility-matched background peaks for chromVAR.

    Wraps :func:`epione.tl.add_background_peaks`.
    """
    return epione_module("tl").add_background_peaks(adata, *args, **kwargs)


def compute_deviations(adata, *args, **kwargs):
    r"""chromVAR motif/TF deviation z-scores per cell. Wraps :func:`epione.tl.compute_deviations`."""
    return epione_module("tl").compute_deviations(adata, *args, **kwargs)


# ---- footprinting ----------------------------------------------------------
def compute_tn5_bias_table(*args, **kwargs):
    r"""Estimate the Tn5 sequence-insertion bias table. Wraps :func:`epione.tl.compute_tn5_bias_table`."""
    return epione_module("tl").compute_tn5_bias_table(*args, **kwargs)


def get_footprints(adata, *args, **kwargs):
    r"""Aggregate TF footprints over motif sites. Wraps :func:`epione.tl.get_footprints`."""
    return epione_module("tl").get_footprints(adata, *args, **kwargs)


def multi_scale_footprint_region(adata, *args, **kwargs):
    r"""Multi-scale footprint profile over a region. Wraps :func:`epione.tl.multi_scale_footprint_region`."""
    return epione_module("tl").multi_scale_footprint_region(adata, *args, **kwargs)


# ---- cross-modality integration --------------------------------------------
def integrate(adata1, adata2, *args, **kwargs):
    r"""CCA-style integration of two modalities/datasets. Wraps :func:`epione.tl.integrate`."""
    return epione_module("tl").integrate(adata1, adata2, *args, **kwargs)


def transfer_labels(query, reference, *args, **kwargs):
    r"""Transfer reference labels onto a query via kNN in a shared space.

    Wraps :func:`epione.tl.transfer_labels`.
    """
    return epione_module("tl").transfer_labels(query, reference, *args, **kwargs)


def joint_embedding(adata1, adata2, *args, **kwargs):
    r"""Joint embedding of two integrated modalities. Wraps :func:`epione.tl.joint_embedding`."""
    return epione_module("tl").joint_embedding(adata1, adata2, *args, **kwargs)


__getattr__ = make_passthrough_getattr("tl")

__all__ = [
    "lsi", "iterative_lsi", "clusters", "umap", "find_marker_features",
    "differential_peaks", "add_gene_score_matrix", "peak_to_gene",
    "coaccessibility", "build_motif_database", "query_motif_database",
    "add_motif_matrix", "add_background_peaks", "compute_deviations",
    "compute_tn5_bias_table", "get_footprints", "multi_scale_footprint_region",
    "integrate", "transfer_labels", "joint_embedding",
]
