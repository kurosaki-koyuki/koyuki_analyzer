"""Lightweight GPU-tensor cache for the neighbors → umap → leiden chain.

In ``cpu-gpu-mixed`` mode the same fuzzy graph (and the same X) gets used
by several consecutive steps:

    ov.pp.neighbors(adata)   # builds GPU KNN + fuzzy graph, stores scipy CSR
    ov.pp.umap(adata)        # parametric UMAP rebuilds its own GPU graph
    ov.pp.leiden(adata)      # GPU Leiden re-uploads scipy CSR -> GPU COO

Each step does an independent CPU↔GPU round-trip plus, in pumap's case, a
full kNN re-computation. This module keeps the GPU representation alive
between calls so the downstream steps can short-circuit.

Design choices:
    * Cache is keyed by ``id(adata)`` plus a per-kind ``sentinel`` (currently
      the id, shape and nnz of the underlying scipy matrix). A mismatch
      means the user replaced the graph; we evict and treat as a miss.
    * Cache is a plain module-level dict — AnnData is unhashable so we
      can't use ``WeakKeyDictionary``. Stale entries (after the adata is
      gc'd) are negligible in size; an explicit ``clear()`` is exposed
      for paranoia.
    * Producer (neighbors) calls ``set``; consumers (umap/leiden) call
      ``get`` with the live source matrix and skip their own work if hit.
"""
from __future__ import annotations

import weakref
from typing import Any, Optional


_CACHE: dict[tuple, tuple] = {}  # (id(adata), kind) -> (sentinel, gpu_data)
_FINALIZERS: dict[int, weakref.finalize] = {}  # id(adata) -> finalizer


def _drop_all_for(adata_id: int) -> None:
    """Internal: drop every cache entry keyed by ``adata_id``."""
    for key in list(_CACHE):
        if key[0] == adata_id:
            _CACHE.pop(key, None)
    _FINALIZERS.pop(adata_id, None)


def _sentinel_for(source_obj) -> tuple:
    """Cheap identity tag for a scipy sparse matrix.

    Combining ``id`` with ``shape`` and ``nnz`` catches the common cases
    where the user replaced the matrix or ran a new neighbor computation.
    Doesn't catch arbitrary in-place data edits, but neither does scanpy.
    """
    if source_obj is None:
        return (None, None, None)
    nnz = getattr(source_obj, "nnz", None)
    if nnz is None:
        return (id(source_obj), getattr(source_obj, "shape", None), None)
    return (id(source_obj), source_obj.shape, int(nnz))


def cache_set(adata, kind: str, gpu_data: Any, source_obj=None) -> None:
    """Store ``gpu_data`` against ``(id(adata), kind)``.

    ``source_obj`` is the CPU-side artifact (typically a scipy CSR) the GPU
    data was derived from — its identity + shape + nnz become the eviction
    sentinel. A ``weakref.finalize`` on ``adata`` drops every cached entry
    (releasing the GPU tensors) when the AnnData is garbage-collected, so
    long-running notebook sessions don't accumulate stale VRAM.
    """
    adata_id = id(adata)
    key = (adata_id, kind)
    _CACHE[key] = (_sentinel_for(source_obj), gpu_data)
    if adata_id not in _FINALIZERS:
        try:
            _FINALIZERS[adata_id] = weakref.finalize(adata, _drop_all_for, adata_id)
        except TypeError:
            # Some AnnData subclasses may disable weak refs; best effort.
            pass


def cache_get(adata, kind: str, source_obj=None) -> Optional[Any]:
    """Return cached GPU tensors if the source still matches, else ``None``."""
    key = (id(adata), kind)
    entry = _CACHE.get(key)
    if entry is None:
        return None
    sentinel, gpu_data = entry
    if sentinel != _sentinel_for(source_obj):
        _CACHE.pop(key, None)
        return None
    return gpu_data


def cache_invalidate(adata, kind: Optional[str] = None) -> None:
    """Drop one or all cached entries for ``adata``."""
    if kind is None:
        for key in list(_CACHE):
            if key[0] == id(adata):
                _CACHE.pop(key, None)
    else:
        _CACHE.pop((id(adata), kind), None)


def clear() -> None:
    """Drop the entire cache (e.g. before switching ``settings.mode``)."""
    _CACHE.clear()
