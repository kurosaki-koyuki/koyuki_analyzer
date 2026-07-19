r"""Internal helpers shared by the ``ov.epi`` wrappers.

``ov.epi`` is a thin bridge over the `epione
<https://github.com/aristoteleo/epione>`_ epigenomics package: every
public function imports :mod:`epione` *inside* the call and delegates to
the matching ``epione`` symbol. Keeping the import inside the function
(rather than at module top level) means ``import omicverse`` never pulls
in epione's heavy optional dependencies (snapatac2, anndataoom, cooler,
MOODS, pysam, ...) unless an ``ov.epi.*`` function is actually called.
"""

from __future__ import annotations

import functools
import importlib
from types import ModuleType
from typing import Any, Callable

_INSTALL_HINT = (
    "ov.epi requires the 'epione' package, which is not installed.\n"
    "Install it with:\n"
    "    pip install epione            # core\n"
    "    pip install 'epione[full]'    # + motif / footprint extras\n"
    "or from source: pip install git+https://github.com/aristoteleo/epione"
)


def import_epione() -> ModuleType:
    """Import and return the top-level :mod:`epione` module.

    Raises a friendly :class:`ImportError` (with an install hint) when
    epione is missing, instead of a bare ``ModuleNotFoundError`` from
    deep inside a wrapper.
    """
    try:
        return importlib.import_module("epione")
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(_INSTALL_HINT) from exc


def epione_module(name: str) -> ModuleType:
    """Return an epione submodule by dotted suffix, e.g. ``"pp"`` or ``"bulk.atac"``."""
    import_epione()  # ensure top-level import + friendly error first
    return importlib.import_module(f"epione.{name}")


def delegate(submodule: str, attr: str) -> Callable[..., Any]:
    """Build a wrapper that forwards ``*args, **kwargs`` to ``epione.<submodule>.<attr>``.

    The returned function imports epione lazily on first call and copies
    the target's ``__doc__`` / ``__name__`` so ``help()`` and Sphinx see
    the real epione documentation.
    """

    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        mod = epione_module(submodule)
        target = getattr(mod, attr)
        return target(*args, **kwargs)

    _wrapper.__name__ = attr
    _wrapper.__qualname__ = attr
    _wrapper.__doc__ = (
        f"omicverse wrapper around :func:`epione.{submodule}.{attr}`.\n\n"
        f"This calls ``epione.{submodule}.{attr}(*args, **kwargs)`` directly; "
        f"see the epione documentation for the full signature."
    )
    _wrapper.__wrapped_target__ = f"epione.{submodule}.{attr}"  # type: ignore[attr-defined]
    return _wrapper


def make_passthrough_getattr(submodule: str) -> Callable[[str], Any]:
    """Build a module-level ``__getattr__`` that forwards any unknown name to an epione submodule.

    Curated wrappers defined explicitly in the ov.epi submodule take
    precedence (normal attribute lookup happens first); anything not
    explicitly wrapped is resolved lazily from ``epione.<submodule>`` so
    the full epione surface remains reachable through ``ov.epi``.
    """

    @functools.lru_cache(maxsize=None)
    def _getattr(name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        mod = epione_module(submodule)
        try:
            return getattr(mod, name)
        except AttributeError as exc:
            raise AttributeError(
                f"'epione.{submodule}' has no attribute '{name}'"
            ) from exc

    return _getattr
