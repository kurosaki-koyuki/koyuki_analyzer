r"""``ov.epi.pl`` — epigenomics plotting (wraps :mod:`epione.pl`).

QC diagnostics, embeddings, differential-accessibility and peak-to-gene
plots, footprints and Hi-C contact visualisations, delegating to
`epione <https://github.com/aristoteleo/epione>`_. Each function imports
epione internally and returns the matplotlib figure/axes that epione
produces.
"""

from __future__ import annotations

from ._utils import epione_module, make_passthrough_getattr


def plot_set(*args, **kwargs):
    r"""Apply omicverse/epione publication plotting defaults. Wraps :func:`epione.pl.plot_set`."""
    return epione_module("pl").plot_set(*args, **kwargs)


def frag_size_distr(adata, **kwargs):
    r"""Plot the fragment-size distribution (nucleosome periodicity). Wraps :func:`epione.pl.frag_size_distr`."""
    return epione_module("pl").frag_size_distr(adata, **kwargs)


def tss_enrichment(adata, **kwargs):
    r"""Plot the TSS-enrichment profile. Wraps :func:`epione.pl.tss_enrichment`."""
    return epione_module("pl").tss_enrichment(adata, **kwargs)


def plot_joint(adata, **kwargs):
    r"""KDE-overlaid joint QC scatter (e.g. log-fragments vs TSSe). Wraps :func:`epione.pl.plot_joint`."""
    return epione_module("pl").plot_joint(adata, **kwargs)


def fragment_histogram(adata, **kwargs):
    r"""Histogram of fragment sizes. Wraps :func:`epione.pl.fragment_histogram`."""
    return epione_module("pl").fragment_histogram(adata, **kwargs)


def umap(adata, **kwargs):
    r"""UMAP scatter colored by an obs/var key. Wraps :func:`epione.pl.umap`."""
    return epione_module("pl").umap(adata, **kwargs)


def embedding(adata, *args, **kwargs):
    r"""Generic embedding scatter. Wraps :func:`epione.pl.embedding`."""
    return epione_module("pl").embedding(adata, *args, **kwargs)


def pca(adata, **kwargs):
    r"""PCA scatter. Wraps :func:`epione.pl.pca`."""
    return epione_module("pl").pca(adata, **kwargs)


def tsne(adata, **kwargs):
    r"""t-SNE scatter. Wraps :func:`epione.pl.tsne`."""
    return epione_module("pl").tsne(adata, **kwargs)


def volcano(*args, **kwargs):
    r"""Volcano plot for differential accessibility. Wraps :func:`epione.pl.volcano`."""
    return epione_module("pl").volcano(*args, **kwargs)


def ma_plot(*args, **kwargs):
    r"""MA plot for differential accessibility. Wraps :func:`epione.pl.ma_plot`."""
    return epione_module("pl").ma_plot(*args, **kwargs)


def plot_peak2gene(*args, **kwargs):
    r"""Arc/track plot of peak→gene links. Wraps :func:`epione.pl.plot_peak2gene`."""
    return epione_module("pl").plot_peak2gene(*args, **kwargs)


def plot_footprints(*args, **kwargs):
    r"""TF footprint profile plot. Wraps :func:`epione.pl.plot_footprints`."""
    return epione_module("pl").plot_footprints(*args, **kwargs)


def homer_motif_table(*args, **kwargs):
    r"""Render a HOMER motif-enrichment table. Wraps :func:`epione.pl.homer_motif_table`."""
    return epione_module("pl").homer_motif_table(*args, **kwargs)


# Hi-C contact-map family + anything else forwarded to epione.pl.
__getattr__ = make_passthrough_getattr("pl")

__all__ = [
    "plot_set", "frag_size_distr", "tss_enrichment", "plot_joint",
    "fragment_histogram", "umap", "embedding", "pca", "tsne", "volcano",
    "ma_plot", "plot_peak2gene", "plot_footprints", "homer_motif_table",
]
