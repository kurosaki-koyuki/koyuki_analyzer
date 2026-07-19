"""Backend implementations for ``ov.single.MetaCell``.

Each backend wraps one upstream metacell algorithm (or a baseline) behind
the :class:`~omicverse.single._metacell_backends.base.MetaCellBackend`
Protocol so that :class:`ov.single.MetaCell` can dispatch on
``method=...`` without leaking backend-specific kwargs into the unified
class.

Add a new backend in three steps:

1.  Vendor / wrap its core in ``omicverse/external/<name>/``.
2.  Add a subclass of :class:`MetaCellBackend` here.
3.  Register it in :data:`BACKEND_REGISTRY` below.
"""

from .base import MetaCellBackend, FitResult, UnsupportedCapability
from .seacells_backend import SEACellsBackend
from .metaq_backend import MetaQBackend
from .mc2_backend import MC2Backend
from .supercell_backend import SuperCellBackend
from .kmeans_backend import KMeansBackend
from .random_backend import RandomBackend
from .geosketch_backend import GeoSketchBackend

BACKEND_REGISTRY = {
    "seacells": SEACellsBackend,
    "metaq": MetaQBackend,
    "mc2": MC2Backend,
    "supercell": SuperCellBackend,
    "kmeans": KMeansBackend,
    "random": RandomBackend,
    "geosketch": GeoSketchBackend,
}

__all__ = [
    "MetaCellBackend",
    "FitResult",
    "UnsupportedCapability",
    "BACKEND_REGISTRY",
    "SEACellsBackend",
    "MetaQBackend",
    "MC2Backend",
    "SuperCellBackend",
    "KMeansBackend",
    "RandomBackend",
    "GeoSketchBackend",
]
