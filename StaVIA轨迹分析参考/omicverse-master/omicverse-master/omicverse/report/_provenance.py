"""Lightweight per-step provenance recorded into ``adata.uns``.

The pipeline-report system is structured as a small, explicit contract
between the dispatcher and the report:

    @tracked('umap', 'ov.pp.umap')
    def umap(adata, **kwargs):
        if settings.mode == 'cpu':
            ...
            note(backend='omicverse(cpu) · scanpy')
        ...
        note(viz=[{'function': 'ov.pl.embedding',
                    'kwargs': {'basis': 'X_umap',
                               'color': pick_color_key(adata)}}])

* ``@tracked`` owns the infrastructure: timing, kwargs capture, the
  thread-local nesting guard (so a ``tracked`` sub-call inside another
  ``tracked`` body is silenced — the user-visible outer call owns the
  record), and the call to :func:`record_step` at the end. Exceptions
  are re-raised without recording.
* :func:`note` lets the body annotate the currently-running tracked
  call with branch-determined fields — typically ``backend`` and
  ``viz``. It's a no-op outside a tracked body.
* :func:`record_step` is still exposed as a low-level primitive for
  callers who want to bypass the decorator.

The recorded entry lives at ``adata.uns['_ov_provenance']`` as a
dict-of-dicts keyed ``"000_qc"``, ``"001_umap"``, …; the ``viz``
list-of-dicts is JSON-encoded on write so the whole log round-trips
through h5ad cleanly.
"""
from __future__ import annotations

import datetime
import functools
import inspect
import json
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterable, Optional

PROVENANCE_KEY = "_ov_provenance"

_PRIMITIVE = (str, int, float, bool, type(None))

# Thread-local stack of currently-running tracked entries. The outermost
# entry corresponds to the user's direct call; anything below is a
# library-internal sub-call that must not emit its own record.
_state = threading.local()


def _stack() -> list:
    stack = getattr(_state, "stack", None)
    if stack is None:
        _state.stack = []
        stack = _state.stack
    return stack


# ─────────────────────────── serialisation helpers ────────────────────────────


def _coerce(v: Any) -> Any:
    """Best-effort conversion to something h5ad/JSON can serialise."""
    if isinstance(v, _PRIMITIVE):
        return v
    if isinstance(v, (list, tuple)):
        return [_coerce(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _coerce(val) for k, val in v.items()}
    try:
        import numpy as np

        if isinstance(v, np.generic):
            return v.item()
    except ImportError:
        pass
    return repr(v)[:200]


def _omicverse_version() -> str:
    try:
        from omicverse import __version__ as v
        return str(v)
    except Exception:  # noqa: BLE001
        return ""


def _settings_mode() -> str:
    try:
        from omicverse._settings import settings
        return str(settings.mode)
    except Exception:  # noqa: BLE001
        return ""


# ────────────────────────── low-level primitive ───────────────────────────────


def record_step(
    adata,
    name: str,
    *,
    function: str,
    params: Optional[dict] = None,
    backend: str = "",
    duration_s: Optional[float] = None,
    n_obs_before: Optional[int] = None,
    n_obs_after: Optional[int] = None,
    viz: Optional[list[dict]] = None,
) -> None:
    """Append a provenance entry to ``adata.uns['_ov_provenance']``.

    Best-effort: failures here never crash the user's pipeline. Most
    callers should use :func:`tracked` + :func:`note` instead.
    """
    try:
        if adata is None or not hasattr(adata, "uns"):
            return
        entry = {
            "name": str(name),
            "function": str(function),
            "params": _coerce(params or {}),
            "backend": str(backend or ""),
            "mode": _settings_mode(),
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "duration_s": float(duration_s) if duration_s is not None else None,
            "version": _omicverse_version(),
            "n_obs_before": int(n_obs_before) if n_obs_before is not None else None,
            "n_obs_after": int(n_obs_after) if n_obs_after is not None
                            else int(adata.n_obs),
            # viz is a list-of-dicts; h5ad can't persist that natively, so
            # JSON-encode. get_provenance() decodes back.
            "viz": json.dumps(_coerce(viz or []), default=str),
        }
        log = dict(adata.uns.get(PROVENANCE_KEY, {}) or {})
        if isinstance(log, list):  # migrate legacy list-of-dicts
            log = {f"{i:03d}_{e.get('name', 'step')}": e for i, e in enumerate(log)}
        idx = f"{len(log):03d}_{name}"
        log[idx] = entry
        adata.uns[PROVENANCE_KEY] = log
    except Exception:  # noqa: BLE001
        pass


# ──────────────────────── high-level decorator + note ─────────────────────────


def note(**fields) -> None:
    """Annotate the currently-running ``@tracked`` call with extra fields.

    Typical uses inside a dispatcher body::

        note(backend='omicverse(cpu) · scanpy')
        note(viz=[{'function': 'ov.pl.embedding', 'kwargs': {...}}])
        note(params={**kwargs, 'forwarded': True})   # override defaults

    ``viz`` is **additive**: multiple ``note(viz=[...])`` calls in the
    same body append to the step's viz list rather than overwriting.
    All other fields follow standard dict-update semantics (later wins).

    No-op when called outside any ``@tracked`` body — safe to sprinkle in
    helpers that are sometimes called directly.
    """
    stack = getattr(_state, "stack", None)
    if not stack:
        return
    entry = stack[-1]
    viz = fields.pop("viz", None)
    if viz is not None:
        entry.setdefault("viz", []).extend(viz)
    entry.update(fields)


def tracked(name: str, function: str, *, adata_attr: Optional[str] = None):
    """Decorator for dispatchers that should appear in the pipeline report.

    Responsibilities covered here so the body doesn't have to:

    - Wall-clock timing (``duration_s``).
    - kwargs capture into ``params`` (positional args beyond ``adata`` /
      ``self`` are bound via :func:`inspect.signature` so they show up
      by name).
    - A thread-local stack that makes nested ``@tracked`` calls silent —
      only the outermost invocation writes a provenance entry. This is
      how e.g. ``ov.pp.qc`` internally invoking ``ov.pp.scrublet`` still
      yields a single ``qc`` entry.
    - Success-only recording: if the wrapped function raises, the
      staging entry is discarded.

    The body uses :func:`note` to populate ``backend`` / ``viz`` (and
    anything else branch-dependent).

    Free functions::

        @tracked('scale', 'ov.pp.scale')
        def scale(adata, ...): ...

    Class methods — pull adata from ``self.<adata_attr>``::

        @tracked('Annotation.annotate', 'ov.single.Annotation.annotate',
                 adata_attr='adata')
        def annotate(self, method='celltypist', ...): ...
    """

    def decorator(fn):
        sig = inspect.signature(fn)
        param_names = [
            n for n, p in sig.parameters.items()
            if n not in ("adata", "self", "data")
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        ]

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Capture kwargs the user actually passed (no defaults filled
            # in), plus any positional extras matched by parameter name.
            positional = {
                n: v for n, v in zip(param_names, args[1:])
            }
            captured = {**positional, **kwargs}
            # Resolve the AnnData to attach the entry to:
            # - free function: args[0] (or `adata=` kwarg)
            # - class method: getattr(self, adata_attr)
            if adata_attr is None:
                adata_in = args[0] if args else kwargs.get("adata")
            else:
                self_obj = args[0] if args else None
                adata_in = getattr(self_obj, adata_attr, None)
            n_obs_before = getattr(adata_in, "n_obs", None)
            stack = _stack()
            stack.append({
                "name": name,
                "function": function,
                "params": captured,
                "backend": "",
                "viz": [],
            })
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                stack.pop()
                raise
            entry = stack.pop()
            if stack:
                # Nested call — the outermost @tracked owns the record.
                return result
            # For free functions with copy-semantics, prefer the returned
            # AnnData. For methods, the target is always the bound adata
            # (returns are typically the model object, not the adata).
            if adata_attr is None and result is not None and hasattr(result, "uns"):
                target = result
            else:
                target = adata_in
            record_step(
                target, entry["name"],
                function=entry["function"],
                params=entry["params"],
                backend=entry["backend"],
                duration_s=time.time() - t0,
                n_obs_before=n_obs_before,
                n_obs_after=getattr(target, "n_obs", None),
                viz=entry["viz"],
            )
            return result

        return wrapper

    return decorator


# ────────────────────────── read-side helpers ─────────────────────────────────


def _decode_entry(entry: dict) -> dict:
    if not isinstance(entry, dict):
        return entry
    out = dict(entry)
    viz = out.get("viz")
    if isinstance(viz, str):
        try:
            out["viz"] = json.loads(viz) if viz else []
        except Exception:  # noqa: BLE001
            out["viz"] = []
    return out


def get_provenance(adata) -> list[dict]:
    """Return the list of recorded steps (oldest first); empty if none."""
    if adata is None or not hasattr(adata, "uns"):
        return []
    raw = adata.uns.get(PROVENANCE_KEY, None)
    if not raw:
        return []
    if isinstance(raw, list):
        return [_decode_entry(e) for e in raw]
    if isinstance(raw, dict):
        return [_decode_entry(raw[k]) for k in sorted(raw.keys())]
    return []


def clear_provenance(adata) -> None:
    """Drop all provenance entries."""
    if adata is not None and hasattr(adata, "uns") and PROVENANCE_KEY in adata.uns:
        del adata.uns[PROVENANCE_KEY]


def pick_color_key(adata, preference: Optional[Iterable[str]] = None) -> Optional[str]:
    """First present obs column among the preference list.

    Helper for building ``ov.pl.embedding`` viz specs that default to
    the most informative labeling on the AnnData.
    """
    candidates = list(preference or ("cell_type", "leiden", "louvain",
                                      "cluster", "phase"))
    for k in candidates:
        if k in adata.obs.columns:
            return k
    return None


# ──────────────── legacy / deprecated (kept for external callers) ─────────────


@contextmanager
def track(adata, name: str, *, function: str,
          params: Optional[dict] = None, backend: str = "",
          viz: Optional[list[dict]] = None):
    """Context-manager form — prefer :func:`tracked` + :func:`note` instead.

    Like :func:`tracked`, only records on successful completion: if the
    wrapped block raises, no entry is emitted. This keeps the report
    from showing ghost entries for failed steps.
    """
    n_before = getattr(adata, "n_obs", None)
    t0 = time.time()
    success = False
    try:
        yield
        success = True
    finally:
        if success:
            record_step(
                adata, name, function=function, params=params, backend=backend,
                duration_s=time.time() - t0,
                n_obs_before=n_before,
                n_obs_after=getattr(adata, "n_obs", None),
                viz=viz,
            )
