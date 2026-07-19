"""Turn ``adata.uns['_ov_provenance']`` into the list of ``Step`` objects
the HTML renderer expects.

There are no heuristics here — no ``if "X_umap" in obsm``, no sniffing
of ``var.highly_variable``. A step appears in the report **if and only
if** some ``ov.*`` dispatcher logged it via ``record_step``. Anything
else on the AnnData was not produced by omicverse as far as we can
tell, and the report refuses to pretend otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ._provenance import get_provenance


@dataclass
class Step:
    name: str                              # canonical key, e.g. "umap"
    title: str                             # human-readable title
    backend: str = ""                      # backend label, e.g. "omicverse(cpu)"
    summary: str = ""                      # one-line description
    params: dict = field(default_factory=dict)   # kwargs the user passed
    code: str = ""                         # reconstructed public call
    viz: list[dict] = field(default_factory=list)  # list of {function, kwargs}
    provenance: dict = field(default_factory=dict)  # raw provenance entry


def _humanize(name: str) -> str:
    override = {
        "qc":                "Quality Control",
        "scrublet":          "Doublet detection",
        "scdblfinder":       "Doublet detection",
        "preprocess":        "Preprocess (normalize + HVG)",
        "normalize_total":   "Normalization",
        "log1p":             "Log transform",
        "hvg":               "Highly variable genes",
        "highly_variable_genes": "Highly variable genes",
        "scale":             "Scaling",
        "pca":               "Principal component analysis",
        "neighbors":         "Nearest-neighbor graph",
        "umap":              "UMAP embedding",
        "tsne":              "t-SNE embedding",
        "mde":               "MDE embedding",
        "leiden":            "Leiden clustering",
        "louvain":           "Louvain clustering",
        "score_genes_cell_cycle": "Cell cycle scoring",
        "find_markers":      "Marker gene ranking",
    }
    return override.get(name, name.replace("_", " ").capitalize())


def _format_repr(v: Any) -> str:
    if isinstance(v, (list, tuple)) and len(v) > 6:
        head = ", ".join(repr(x) for x in list(v)[:3])
        tail = ", ".join(repr(x) for x in list(v)[-2:])
        return f"[{head}, ..., {tail}]  # len={len(v)}"
    return repr(v)


def _format_call(function: str, params: dict) -> str:
    """Render the literal call the user made — only the kwargs they
    actually passed, never any filled-in defaults."""
    if not params:
        return f"{function}(adata)"
    lines = [f"{function}("]
    lines.append("    adata,")
    for k, v in params.items():
        lines.append(f"    {k}={_format_repr(v)},")
    lines.append(")")
    return "\n".join(lines)


def _summary(entry: dict) -> str:
    parts = []
    nb = entry.get("n_obs_before")
    na = entry.get("n_obs_after")
    if nb is not None and na is not None and nb != na:
        parts.append(f"cells {nb:,} → {na:,}")
    if entry.get("version"):
        parts.append(f"v{entry['version']}")
    return "  ·  ".join(parts) if parts else ""


def _step_from_entry(entry: dict) -> Step:
    name = entry.get("name", "step")
    function = entry.get("function", "")
    params = dict(entry.get("params", {}) or {})
    viz = list(entry.get("viz", []) or [])
    return Step(
        name=name,
        title=_humanize(name),
        backend=entry.get("backend", ""),
        summary=_summary(entry),
        params=params,
        code=_format_call(function, params) if function else "",
        viz=viz,
        provenance=entry,
    )


def scan(adata) -> list[Step]:
    """Return an ordered list of steps, one per provenance entry."""
    return [_step_from_entry(e) for e in get_provenance(adata)]
