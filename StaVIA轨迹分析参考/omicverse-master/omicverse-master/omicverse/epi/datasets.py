r"""``ov.epi.datasets`` — fetch-on-demand example epigenomics datasets.

Convenience wrappers over epione's pooch registry
(:func:`epione.utils.register_datasets`). Each fetcher downloads (once,
then caches under epione's pooch cache) a small public dataset suitable
for running an ``ov.epi`` tutorial end-to-end, mirroring the
``scanpy.datasets`` style.

>>> import omicverse as ov
>>> frag = ov.epi.datasets.atac_pbmc5k_fragments()   # 10x PBMC 5k fragments
>>> adata = ov.epi.datasets.atac_pbmc5k()            # prebuilt tile-matrix h5ad
"""

from __future__ import annotations

from ._utils import epione_module, import_epione


def register_datasets():
    r"""Return epione's :class:`pooch.Pooch` example-data registry.

    Use ``.fetch(key)`` to download any registered file; see
    :data:`available_keys` for the catalogue. Wraps
    :func:`epione.utils.register_datasets`.
    """
    return epione_module("utils").register_datasets()


def available_keys():
    """List the keys available in epione's example-data registry."""
    return list(register_datasets().registry.keys())


def _fetch(key: str) -> str:
    return register_datasets().fetch(key)


def _read_h5ad(path: str):
    import anndata as ad
    return ad.read_h5ad(path)


# ---- 10x PBMC 5k scATAC ----------------------------------------------------
def atac_pbmc5k_fragments() -> str:
    """Path to the 10x PBMC-5k scATAC ``fragments.tsv.gz`` (GRCh38).

    Feed straight into :func:`ov.epi.pp.import_fragments`.
    """
    return _fetch("atac_pbmc_5k.tsv.gz")


def atac_pbmc5k(annotated: bool = False):
    """Prebuilt 10x PBMC-5k scATAC tile-matrix AnnData (GRCh38).

    Parameters
    ----------
    annotated
        If True, return the version carrying published cell-type labels
        (``atac_pbmc_5k_annotated.h5ad``); otherwise the unlabeled
        tile-matrix (``atac_pbmc_5k.h5ad``).
    """
    key = "atac_pbmc_5k_annotated.h5ad" if annotated else "atac_pbmc_5k.h5ad"
    return _read_h5ad(_fetch(key))


# ---- 10x PBMC 500 scATAC (smallest) ---------------------------------------
def atac_pbmc500_fragments(downsample: bool = False) -> str:
    """Path to the 10x PBMC-500 scATAC ``fragments.tsv.gz`` (GRCh38).

    The smallest fragments file in the registry — handy for fast,
    low-memory demos. Set ``downsample=True`` for the even smaller
    downsampled variant.
    """
    return _fetch("atac_pbmc_500_downsample.tsv.gz" if downsample else "atac_pbmc_500.tsv.gz")


# ---- 10x PBMC 10k multiome -------------------------------------------------
def pbmc10k_multiome():
    """The paired 10x PBMC-10k multiome ATAC + RNA AnnData pair (GRCh38).

    Returns
    -------
    (atac, rna)
        Two :class:`~anndata.AnnData` objects sharing cell barcodes —
        the input for :func:`ov.epi.tl.peak_to_gene`.
    """
    atac = _read_h5ad(_fetch("10x-Multiome-Pbmc10k-ATAC.h5ad"))
    rna = _read_h5ad(_fetch("10x-Multiome-Pbmc10k-RNA.h5ad"))
    return atac, rna


def pbmc10k_atac_fragments() -> str:
    """Path to the 10x PBMC-10k multiome ATAC ``fragments.tsv.gz`` (GRCh38)."""
    return _fetch("pbmc_10k_atac.tsv.gz")


def __getattr__(name):  # forward e.g. raw registry helpers
    import_epione()
    return getattr(epione_module("datasets"), name)


__all__ = [
    "register_datasets", "available_keys", "atac_pbmc5k_fragments",
    "atac_pbmc5k", "atac_pbmc500_fragments", "pbmc10k_multiome",
    "pbmc10k_atac_fragments",
]
