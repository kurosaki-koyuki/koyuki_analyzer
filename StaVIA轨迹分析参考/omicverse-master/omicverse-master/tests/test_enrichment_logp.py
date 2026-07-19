"""Regression test for issue #685.

`enrich_res['logp']` is rendered through a colour bar labelled
``$-Log_{10}(P_{adjusted})$``. Before the fix, the value was computed
with ``np.log`` (natural log) and silently disagreed with the label
by a factor of ``ln(10) ≈ 2.303``. These tests pin the base-10
convention so the regression cannot reappear.

The tests exercise the *post-processing math* directly — they do not
require a live ``gseapy.enrich`` / ``prerank`` call (which would need
network access for gene-set DBs). The math is what has to stay log10.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


_ENRICHMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "omicverse" / "bulk" / "_Enrichment.py"
)
_SCGSEA_PATH = (
    Path(__file__).resolve().parents[1]
    / "omicverse" / "single" / "_scgsea.py"
)


def _enrich_res_logp(padj: np.ndarray) -> pd.DataFrame:
    """Reproduce the post-fix `logp` math used by every enrichment site.

    Equivalent to:

        enrich_res['logp'] = -np.log10(enrich_res['<P column>'])

    on `_Enrichment.geneset_enrichment` (lines 94/97/100/103),
    `_Enrichment.pyGSEA.run` (line 553) and `_scgsea.pathway_enrichment`
    (lines 450/453).
    """
    df = pd.DataFrame({"P-value": padj})
    df["logp"] = -np.log10(df["P-value"])
    return df


def test_logp_equals_minus_log10_of_padj() -> None:
    padj = np.array([1e-2, 1e-5, 1e-8, 1e-12])
    out = _enrich_res_logp(padj)
    np.testing.assert_allclose(out["logp"].to_numpy(), -np.log10(padj))


def test_logp_is_NOT_natural_log() -> None:
    """Defensive against the original bug: -np.log(p) gives values that
    look plausible but are inflated by ln(10) ≈ 2.303 — exactly the bug
    that landed in production for a long time.
    """
    padj = np.array([1e-2, 1e-5, 1e-10])
    out = _enrich_res_logp(padj)
    natural = -np.log(padj)
    assert not np.allclose(out["logp"].to_numpy(), natural)
    # The bug-relative magnitude was inflated by ln(10).
    np.testing.assert_allclose(natural / out["logp"].to_numpy(),
                               np.full(padj.size, np.log(10)))


def test_logp_range_matches_label_for_typical_padj_span() -> None:
    """A Padj range of 1e-12 … 1e-2 (typical pathway enrichment) must
    map to a colour-bar range of 2 … 12 — what the label
    ``$-Log_{10}(P_{adjusted})$`` claims. Before the fix this same
    input mapped to roughly 4.6 … 27.6.
    """
    padj_span = np.geomspace(1e-12, 1e-2, 11)
    out = _enrich_res_logp(padj_span)
    assert out["logp"].min() == 2.0
    assert out["logp"].max() == 12.0


def _grep(path: Path, pattern: str) -> list[str]:
    return [line for line in path.read_text().splitlines() if re.search(pattern, line)]


def test_no_natural_log_logp_in_enrichment_source() -> None:
    """Pin the source itself: every `logp = -np.log(...)` site has been
    converted to `np.log10`. Catches a future regression introduced by
    a copy-paste from older code or external snippets.
    """
    for path in (_ENRICHMENT_PATH, _SCGSEA_PATH):
        # Lines that look like `logp = -np.log(<something>)` (NOT log10).
        offenders = _grep(path, r"logp\s*=\s*-\s*np\.log\b\(")
        assert not offenders, (
            f"{path.name} still computes logp with natural log:\n"
            + "\n".join(f"  {ln}" for ln in offenders)
        )


def test_geneset_enrichment_GSEA_returns_only_pre_res() -> None:
    """The function used to have unreachable post-`return pre_res` code
    that mirrored the post-processing in `pyGSEA.run`. The dead block
    (a) couldn't run because of the early return, and (b) was a
    misleading "fix this too" hot-spot during review of #685.
    Removing it during the same review keeps the source honest.
    """
    src = _ENRICHMENT_PATH.read_text()
    # Locate the function and confirm there is exactly one return.
    match = re.search(
        r"def geneset_enrichment_GSEA\(.*?\):\n(.*?)(?=\n@register_function|\nclass |\ndef )",
        src, re.DOTALL,
    )
    assert match, "geneset_enrichment_GSEA function not found"
    body = match.group(1)
    assert body.count("return ") == 1, (
        "geneset_enrichment_GSEA should have one explicit return statement; "
        "found:\n" + body
    )
