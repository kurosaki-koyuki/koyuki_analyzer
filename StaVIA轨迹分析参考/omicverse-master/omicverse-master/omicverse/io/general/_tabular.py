"""Tabular CSV/TSV readers with sample-axis safety checks.

The default `pandas.read_csv` silently auto-renames duplicate column
labels (``id154``, ``id154`` → ``id154`` + ``id154.1``), which masks
the single most common silent failure mode in joint-table analyses:
two columns of a counts CSV that hold the same biological sample's
data become two "unique" samples in downstream PCA / DEG / clustering.

`ov.io.read_csv` and `ov.io.read_table` wrap pandas's readers with a
mandatory raw-header check that emits a loud stdout warning (or
raises, configurable) when duplicate column labels are detected. The
warning points the caller at `ov.utils.preflight_alignment` for the
full diagnostic. All existing kwargs of `pandas.read_csv` continue to
work; the only addition is `on_duplicate=`.
"""

from __future__ import annotations

import collections
from pathlib import Path
from typing import IO, Any

import pandas as pd

from ..._registry import register_function


# Sentinel — `header_row="first-non-comment"` skips '#'-prefixed lines
# (featurecounts / STAR style) before reading the header. Avoids string-
# magic at the call site.


def _maybe_path(filepath_or_buffer) -> Path | None:
    """Return a Path when the input looks like an on-disk file path,
    else None (so we silently skip the duplicate scan for buffers /
    URLs / file-like objects we can't pre-peek)."""
    if isinstance(filepath_or_buffer, (str, Path)):
        p = Path(str(filepath_or_buffer))
        if p.exists() and p.is_file():
            return p
    return None


def _read_raw_header(path: Path, sep: str) -> list[str]:
    """Read the first non-comment line and split on `sep`. Preserves
    duplicate labels (pandas would auto-rename)."""
    with open(path) as f:
        for raw_line in f:
            if raw_line.lstrip().startswith("#"):
                continue
            return raw_line.rstrip("\r\n").split(sep)
    raise ValueError(f"empty file: {path}")


def _detect_duplicate_columns(path: Path, sep: str) -> tuple[int, list[str]]:
    """Return ``(n_duplicate_labels, list_of_duplicated_labels)`` from
    the raw header. ``n_duplicate_labels`` is the count of labels that
    appear ≥ 2 times (not the total extra occurrences)."""
    header = _read_raw_header(path, sep)
    counts = collections.Counter(header)
    dup_labels = sorted({label for label, c in counts.items() if c > 1})
    return len(dup_labels), dup_labels


def _emit_duplicate_warning(
    path: Path,
    dup_labels: list[str],
    on_duplicate: str,
    sep_name: str,
) -> None:
    """Default action when duplicates are detected. Goes to stdout (not
    Python's warnings module) so it lands in agent tool-result output."""
    msg = (
        f"\n⚠️  ov.io.read_csv: detected {len(dup_labels)} duplicate "
        f"column label(s) in {path.name} (separator={sep_name!r}). "
        f"pandas.read_csv silently renames duplicates to `name.1`, `name.2`, "
        f"... — any downstream `.duplicated()` check on the resulting "
        f"DataFrame will return 0 even though duplicates exist.\n"
        f"   Duplicated labels (first 5): {dup_labels[:5]}"
        f"{' …' if len(dup_labels) > 5 else ''}\n"
        f"   Recommended next step: run\n"
        f"     result = ov.utils.preflight_alignment(matrix_path, meta_path)\n"
        f"   to diagnose the full alignment (duplicates + missing-on-each-"
        f"side), then\n"
        f"     matrix, meta = ov.utils.align_to_common(matrix_path, meta_path, result)\n"
        f"   to drop duplicates and intersect to the common sample set.\n"
        f"   Pass on_duplicate='ignore' if you've audited the file and "
        f"deliberately want pandas's rename behavior.\n"
    )
    if on_duplicate == "raise":
        raise ValueError(msg.lstrip("\n"))
    # "warn" — print so the agent's tool result captures it.
    print(msg)


def _infer_text_sep(path: Path, sep: str | None) -> tuple[str, str]:
    """Resolve the delimiter to use, returning (sep_value, sep_name)."""
    if sep is not None:
        return sep, "tab" if sep == "\t" else (sep if len(sep) <= 2 else "custom")
    suffix = path.suffix.lower()
    if suffix in {".tsv", ".tab"}:
        return "\t", "tab"
    if suffix == ".txt":
        return "\t", "tab"
    return ",", "comma"


@register_function(
    aliases=[
        "读取CSV", "read_csv", "csv reader",
        "ov.io.read_csv", "io.read_csv",
        "tab separated read", "tsv read",
        "duplicate-safe csv reader", "sample-aware csv reader",
        "样本安全的csv读取", "重复检测csv读取",
    ],
    category="utils",
    description=(
        "Wrapper around pandas.read_csv that adds a mandatory raw-header "
        "duplicate-column scan and emits a loud stdout warning (or raises) "
        "when found. The warning points at `ov.utils.preflight_alignment` / "
        "`ov.utils.align_to_common`. Default kwargs match pandas exactly; "
        "the only addition is `on_duplicate=` (default 'warn'). Use this in "
        "place of pandas.read_csv whenever loading a sample × feature matrix "
        "or a sample-sheet table — it catches the silent auto-rename failure "
        "mode that breaks downstream PCA / DEG / clustering."
    ),
    examples=[
        "# Standard usage — same signature as pandas",
        "df = ov.io.read_csv('counts.csv', index_col=0)",
        "",
        "# When duplicates exist, stdout shows a warning + remediation hint",
        "df = ov.io.read_csv('counts.csv')   # → '⚠️ ... duplicate labels detected ...'",
        "",
        "# Strict mode — refuse to load when duplicates are present",
        "df = ov.io.read_csv('counts.csv', on_duplicate='raise')",
        "",
        "# Audited file with intentional duplicates — silence the check",
        "df = ov.io.read_csv('counts.csv', on_duplicate='ignore')",
    ],
    related=[
        "io.read_table",
        "utils.preflight_alignment",
        "utils.align_to_common",
        "utils.align_samples",
        "utils.save",
        "utils.load",
    ],
    auto_fix="escalate",
)
def read_csv(
    filepath_or_buffer=None,
    *,
    sep: str | None = None,
    on_duplicate: str = "warn",
    **kwargs,
) -> pd.DataFrame:
    """Read a CSV / TSV file via ``pandas.read_csv`` with a mandatory
    duplicate-column scan on the raw header.

    Parameters
    ----------
    filepath_or_buffer
        Same as ``pandas.read_csv``. Accepts a path-like, a URL, or a
        file-like object. The duplicate scan only runs when the input
        is a real on-disk file path.
    sep
        Delimiter. Inferred from extension when ``None``
        (``.csv`` → ``,``, ``.tsv``/``.txt``/``.tab`` → ``\\t``).
    on_duplicate
        Action when duplicate column labels are found in the raw
        header. One of:

        - ``"warn"`` *(default)* — print a remediation-pointing message
          to stdout and continue with pandas's auto-rename.
        - ``"raise"`` — raise ``ValueError`` with the same message.
        - ``"ignore"`` — silent passthrough; identical to
          ``pandas.read_csv``.

    **kwargs
        Any other keyword argument accepted by ``pandas.read_csv`` (for
        example ``index_col``, ``dtype``, ``usecols``, ``comment``).

    Returns
    -------
    pandas.DataFrame
    """
    if on_duplicate not in {"warn", "raise", "ignore"}:
        raise ValueError(
            f"on_duplicate must be 'warn' / 'raise' / 'ignore', got {on_duplicate!r}"
        )

    path = _maybe_path(filepath_or_buffer)
    sep_value = sep
    if path is not None and on_duplicate != "ignore":
        sep_value, sep_name = _infer_text_sep(path, sep)
        try:
            n_dup, dup_labels = _detect_duplicate_columns(path, sep_value)
        except Exception:
            n_dup, dup_labels = 0, []
        if n_dup:
            _emit_duplicate_warning(path, dup_labels, on_duplicate, sep_name)

    # Forward to pandas. If we inferred sep from extension, pass it.
    if sep_value is not None and "sep" not in kwargs:
        kwargs["sep"] = sep_value
    return pd.read_csv(filepath_or_buffer, **kwargs)


@register_function(
    aliases=[
        "read_table", "ov.io.read_table", "io.read_table",
        "tsv reader", "tab separated reader",
        "读取TSV", "读取tab表",
    ],
    category="utils",
    description=(
        "Tab-separated counterpart of `ov.io.read_csv`. Same duplicate-"
        "column safety scan; default separator is `\\t`. Use for "
        "featurecounts output, kallisto abundance tables, generic TSV "
        "sample sheets, and similar tab-delimited tabular data."
    ),
    examples=[
        "df = ov.io.read_table('featurecounts.txt', comment='#', index_col=0)",
        "df = ov.io.read_table('abundance.tsv', on_duplicate='raise')",
    ],
    related=[
        "io.read_csv",
        "utils.preflight_alignment",
    ],
    auto_fix="escalate",
)
def read_table(
    filepath_or_buffer=None,
    *,
    sep: str = "\t",
    on_duplicate: str = "warn",
    **kwargs,
) -> pd.DataFrame:
    """Read a TSV / generic tab-delimited file. See :func:`read_csv`
    for the full parameter list — `read_table` is `read_csv` with
    `sep="\\t"` as the default."""
    return read_csv(
        filepath_or_buffer,
        sep=sep,
        on_duplicate=on_duplicate,
        **kwargs,
    )


__all__ = ["read_csv", "read_table"]
