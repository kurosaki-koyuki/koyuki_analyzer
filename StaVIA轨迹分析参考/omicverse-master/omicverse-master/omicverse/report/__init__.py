"""omicverse.report — one-call HTML pipeline report for an AnnData.

Usage::

    import omicverse as ov
    ov.report.from_anndata(adata, output="report.html",
                            title="PBMC 3k pipeline")

The report inspects ``adata`` for evidence of standard scRNA pipeline
steps (QC, HVG, PCA, neighbors, UMAP, t-SNE, Leiden, Louvain …) and
emits a single self-contained HTML file with one section per step
including parameters, the omicverse call to reproduce it, and a metric
plot generated on the fly from ``.obsm`` / ``.obs`` / ``.var``.

If the AnnData was processed through omicverse's tracked dispatchers
(``ov.pp.umap``, …) an authoritative provenance log is kept in
``adata.uns['_ov_provenance']`` and used in preference to heuristic
detection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from . import _html, _plots, _scanner
from ._provenance import (
    PROVENANCE_KEY,
    clear_provenance,
    get_provenance,
    record_step,
    track,
)


def from_anndata(
    adata,
    output: Union[str, Path] = "anndata_report.html",
    *,
    title: Optional[str] = None,
) -> Path:
    """Render an HTML pipeline report for ``adata``.

    Parameters
    ----------
    adata
        The AnnData to inspect.
    output
        Path to write the HTML to. Parent directories are created.
    title
        Optional title for the report header. Defaults to the file stem.

    Returns
    -------
    pathlib.Path
        Absolute path of the written HTML file.
    """
    out = Path(output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if title is None:
        title = out.stem.replace("_", " ").title()

    steps = _scanner.scan(adata)
    # Key plots by the step's position in the ordered list so duplicate
    # step names (e.g. two umap runs) don't collide.
    plots: dict[int, list[str]] = {}
    for i, s in enumerate(steps):
        images = _plots.render(s, adata)
        if images:
            plots[i] = images

    html = _html.render(adata, steps, plots, title=title)
    out.write_text(html, encoding="utf-8")
    return out


__all__ = [
    "from_anndata",
    "get_provenance",
    "clear_provenance",
    "record_step",
    "track",
    "PROVENANCE_KEY",
]
