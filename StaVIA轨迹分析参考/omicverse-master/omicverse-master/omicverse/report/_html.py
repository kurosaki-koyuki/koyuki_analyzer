"""HTML rendering for the AnnData report.

Single-file output: all plots are inlined as base64 PNGs and the CSS is
inlined too, so the report can be emailed or hosted from any static
file server with no asset directory.

Style: warm cream background, dark warm-grey text, single accent in
muted terracotta — keeps the report easy on the eyes for long
methods-section reads.
"""
from __future__ import annotations

import datetime
import html
from typing import Iterable, Optional

from ._scanner import Step


_CSS = """
:root {
  --bg:        #FAF8F2;
  --surface:   #F4F1E8;
  --text:      #2E2B27;
  --text-soft: #6E6862;
  --rule:      #E2DCD0;
  --accent:    #C9744D;
  --code-bg:   #ECE7DA;
  --code-text: #3E3A35;
  --max-width: 1240px;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
               "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  font-size: 15.5px; line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.wrap {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 56px 32px 96px 32px;
}
header.hero {
  border-bottom: 1px solid var(--rule);
  padding-bottom: 28px;
  margin-bottom: 44px;
}
header.hero .eyebrow {
  font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent); font-weight: 600;
  margin: 0 0 10px 0;
}
header.hero h1 {
  font-size: 34px; line-height: 1.2; margin: 0 0 14px 0;
  font-weight: 600; letter-spacing: -0.01em;
}
header.hero .meta {
  color: var(--text-soft); font-size: 14px;
}
header.hero .meta span + span::before {
  content: " · "; color: var(--rule);
}
section.step {
  margin: 56px 0 0 0;
  padding-top: 28px;
  border-top: 1px solid var(--rule);
}
section.step:first-of-type { border-top: none; padding-top: 0; }
section.step h2 {
  margin: 0 0 4px 0;
  font-size: 22px; font-weight: 600; letter-spacing: -0.005em;
}
section.step .step-meta {
  color: var(--text-soft);
  font-size: 13px;
  margin: 0 0 22px 0;
}
section.step .step-meta .pill {
  display: inline-block;
  padding: 1px 8px;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: var(--surface);
  font-size: 11px;
  color: var(--text-soft);
  margin-right: 6px;
}
section.step .summary {
  font-size: 15.5px;
  margin: 0 0 18px 0;
}
section.step .grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}
section.step .col { min-width: 0; }
@media (max-width: 900px) {
  section.step .grid { grid-template-columns: 1fr; }
}
section.step.no-figure .grid { grid-template-columns: 1fr; }
.code {
  background: var(--code-bg);
  color: var(--code-text);
  font-family: "SF Mono", "JetBrains Mono", "Menlo", "Consolas", ui-monospace,
                monospace;
  font-size: 13px; line-height: 1.55;
  padding: 14px 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0 0 22px 0;
}
.params {
  margin: 0 0 22px 0;
  border: 1px solid var(--rule);
  border-radius: 6px;
  overflow: hidden;
  font-size: 13.5px;
}
.params table {
  width: 100%; border-collapse: collapse;
}
.params th, .params td {
  text-align: left;
  padding: 8px 14px;
  border-bottom: 1px solid var(--rule);
  vertical-align: top;
}
.params th {
  background: var(--surface);
  color: var(--text-soft);
  font-weight: 500; font-size: 12px;
  letter-spacing: 0.04em; text-transform: uppercase;
}
.params tr:last-child td { border-bottom: none; }
.params td.k {
  font-family: "SF Mono", "Menlo", monospace;
  color: var(--accent);
  width: 38%;
}
.params td.v {
  font-family: "SF Mono", "Menlo", monospace;
  color: var(--code-text);
}
.figure {
  margin: 0;
  text-align: center;
}
.figure img {
  max-width: 100%; height: auto;
  border-radius: 4px;
  border: 1px solid var(--rule);
  background: var(--bg);
}
.figure.placeholder {
  display: flex; align-items: center; justify-content: center;
  min-height: 220px;
  border: 1px dashed var(--rule); border-radius: 4px;
  color: var(--text-soft); font-size: 13px; font-style: italic;
  background: var(--surface);
}
.empty {
  color: var(--text-soft);
  font-style: italic;
  font-size: 14px;
}
footer.foot {
  margin-top: 80px;
  padding-top: 24px;
  border-top: 1px solid var(--rule);
  font-size: 12.5px;
  color: var(--text-soft);
  text-align: center;
}
footer.foot a { color: var(--accent); text-decoration: none; }
"""


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _params_table(params: dict) -> str:
    if not params:
        return ""
    rows = []
    for k, v in params.items():
        rows.append(
            f"<tr><td class='k'>{_esc(k)}</td>"
            f"<td class='v'>{_esc(v)}</td></tr>"
        )
    return (
        "<div class='params'><table>"
        "<thead><tr><th>parameter</th><th>value</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _code_block(code: str) -> str:
    if not code:
        return ""
    return f"<pre class='code'>{_esc(code)}</pre>"


def _figure(b64: Optional[str], alt: str) -> str:
    if not b64:
        return ""
    return (
        f"<div class='figure'>"
        f"<img alt='{_esc(alt)}' src='data:image/png;base64,{b64}' />"
        f"</div>"
    )


def _figures(images: list[str], alt: str) -> str:
    if not images:
        return ""
    return "".join(_figure(b, f"{alt} ({i+1})") for i, b in enumerate(images))


def _step_section(step: Step, images: list[str]) -> str:
    rec = step.provenance or {}
    pills = []
    if step.backend:
        pills.append(f"<span class='pill'>{_esc(step.backend)}</span>")
    if rec.get("duration_s") is not None:
        pills.append(f"<span class='pill'>⏱ {rec['duration_s']:.2f}s</span>")
    if rec.get("timestamp"):
        pills.append(f"<span class='pill'>🕒 {_esc(rec['timestamp'])}</span>")

    fig_html = (_figures(images, step.title) if images
                else "<div class='figure placeholder'>no diagnostic plot</div>")
    left = f"<div class='col col-figure'>{fig_html}</div>"
    right = (
        "<div class='col col-text'>"
        f"{_params_table(step.params or {})}"
        f"{_code_block(step.code)}"
        "</div>"
    )
    return (
        f"<section class='step'>"
        f"<h2>{_esc(step.title)}</h2>"
        f"<div class='step-meta'>{''.join(pills)}</div>"
        f"<p class='summary'>{_esc(step.summary or '—')}</p>"
        f"<div class='grid'>{left}{right}</div>"
        f"</section>"
    )


def render(
    adata,
    steps: Iterable[Step],
    plots_b64: dict[int, list[str]],
    title: Optional[str] = None,
) -> str:
    """Return a complete standalone HTML document."""
    steps = list(steps)
    title = title or "AnnData report"
    n_obs, n_vars = adata.shape
    layers = list(adata.layers.keys()) if hasattr(adata, "layers") else []
    obsm = list(adata.obsm.keys())
    obsp = list(adata.obsp.keys())
    obs_n = len(adata.obs.columns)
    var_n = len(adata.var.columns)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        from omicverse import __version__ as ovv
    except Exception:  # noqa: BLE001
        ovv = "unknown"

    body_parts = [
        f"<header class='hero'>"
        f"<p class='eyebrow'>omicverse · adata report</p>"
        f"<h1>{_esc(title)}</h1>"
        f"<p class='meta'>"
        f"<span>{n_obs:,} cells</span>"
        f"<span>{n_vars:,} genes</span>"
        f"<span>{obs_n} obs cols · {var_n} var cols</span>"
        f"<span>{len(obsm)} obsm · {len(obsp)} obsp · {len(layers)} layers</span>"
        f"<span>{len(steps)} pipeline steps detected</span>"
        f"</p>"
        f"</header>"
    ]
    if not steps:
        body_parts.append(
            "<p class='empty'>No omicverse pipeline steps detected on this AnnData.</p>"
        )
    for i, s in enumerate(steps):
        body_parts.append(_step_section(s, plots_b64.get(i) or []))

    body_parts.append(
        f"<footer class='foot'>"
        f"Generated {_esc(now)} · "
        f"omicverse v{_esc(ovv)} · "
        f"<a href='https://github.com/omicverse/omicverse'>omicverse on GitHub</a>"
        f"</footer>"
    )

    body = "\n".join(body_parts)
    return (
        "<!DOCTYPE html>\n"
        f"<html lang='en'><head>"
        f"<meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_esc(title)}</title>"
        f"<style>{_CSS}</style>"
        f"</head><body><div class='wrap'>{body}</div></body></html>"
    )
