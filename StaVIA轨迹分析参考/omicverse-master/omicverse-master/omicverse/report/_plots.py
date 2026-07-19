"""Render the ``viz`` specs that each provenance entry declares.

The report system is a dumb executor: it takes ``{"function":
"ov.pl.<fn>", "kwargs": {...}}`` specs stored by the dispatcher, resolves
them against the installed ``omicverse.pl``, runs the call, and
base64-encodes the resulting figure. There is no hardcoded step-to-plot
mapping here — if a dispatcher didn't declare a viz, the report has
nothing to draw.

``omicverse.style()`` is applied once per process before the first draw.
"""
from __future__ import annotations

import base64
import inspect
import io
from typing import Optional

# Do NOT call matplotlib.use() at import time — it would clobber the
# user's current backend for the rest of the Python session (a real
# problem in Jupyter). fig.savefig(buf, format='png') works regardless
# of which interactive backend is selected; no backend switch needed.
import matplotlib.pyplot as plt


_STYLE_APPLIED = False


def _apply_style_once() -> None:
    global _STYLE_APPLIED
    if _STYLE_APPLIED:
        return
    try:
        import omicverse as ov
        ov.style()
    except Exception:  # noqa: BLE001
        pass
    _STYLE_APPLIED = True


def _resolve(path: str):
    """Resolve ``"ov.pl.embedding"`` → the callable.

    Accepts any dotted path rooted at ``omicverse`` (``ov`` → ``omicverse``).
    """
    if not path:
        return None
    parts = path.split(".")
    if not parts:
        return None
    head = parts[0]
    if head in ("ov", "omicverse"):
        import omicverse as ov
        obj: object = ov
    else:
        return None
    for p in parts[1:]:
        obj = getattr(obj, p, None)
        if obj is None:
            return None
    return obj if callable(obj) else None


def _encode(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight",
                dpi=150, pad_inches=0.25)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _fig_from(result) -> Optional[plt.Figure]:
    """``ov.pl.*`` helpers variously return Axes, Figure, dicts, or None.

    Fall back to the most recently opened pyplot figure only when the
    callee almost certainly drew *something* via the pyplot API (i.e.
    ``plt.get_fignums()`` is non-empty); otherwise return ``None`` so
    the caller can record a missing figure rather than snapshot a stale
    one from a previous render.
    """
    if isinstance(result, plt.Figure):
        return result
    if isinstance(result, plt.Axes):
        return result.figure
    if isinstance(result, dict):
        first = next(iter(result.values()), None)
        if isinstance(first, plt.Axes):
            return first.figure
        if isinstance(first, plt.Figure):
            return first
    fignums = plt.get_fignums()
    if fignums:
        return plt.figure(fignums[-1])
    return None


def _accepts(fn, name: str) -> bool:
    """Does ``fn`` accept a keyword called ``name``?"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return True  # built-ins / C-extensions: assume yes, let it raise
    params = sig.parameters
    if name in params:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


def _render_one(viz_entry: dict, adata) -> Optional[str]:
    fn = _resolve(viz_entry.get("function", ""))
    if fn is None:
        return None
    kwargs = dict(viz_entry.get("kwargs", {}) or {})
    # Only pass ``show=False`` to helpers that actually declare it —
    # avoids retry-on-TypeError swallowing unrelated type errors.
    if _accepts(fn, "show"):
        kwargs.setdefault("show", False)
    result = fn(adata, **kwargs)
    fig = _fig_from(result)
    if fig is None:
        return None
    return _encode(fig)


def render(step, adata) -> list[str]:
    """Return a list of base64-encoded PNGs, one per declared viz.

    Any individual viz that blows up is swallowed — we would rather
    render a report with a missing figure than have one buggy viz spec
    kill the whole thing.
    """
    _apply_style_once()
    out: list[str] = []
    for v in getattr(step, "viz", None) or []:
        try:
            b64 = _render_one(v, adata)
        except Exception:  # noqa: BLE001
            b64 = None
        if b64:
            out.append(b64)
    return out
