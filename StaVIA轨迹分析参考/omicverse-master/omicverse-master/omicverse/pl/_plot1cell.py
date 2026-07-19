"""Python port of plot1cell::plot_circlize (HaojiaWu/plot1cell).

The original R function arranges a UMAP/t-SNE inside a circular
"circlize" layout: the circumference is split into cluster sectors
(arc length ~ log10(n_cells)), and any number of concentric outer
rings show per-cell metadata grouped by cluster. The scatter itself
is drawn in Cartesian space inside the unit circle, so the UMAP
stays readable — only the *annotation* part becomes circular.

This port uses only matplotlib + scipy.stats.gaussian_kde; no R
dependency, no circlize.
"""
from __future__ import annotations

import warnings
from typing import Iterable, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import Wedge
from scipy.stats import gaussian_kde

from .._registry import register_function
from ._palette import sc_color, pastel_palette, vibrant_palette


# Distinct matplotlib colormaps cycled across tracks when no palette is
# given and no `adata.uns[f"{col}_colors"]` is stored. Picked so adjacent
# tracks don't collide visually.
_DEFAULT_TRACK_PALETTES = (
    "tab20b", "tab20c", "Set3", "Paired", "Set2", "Pastel1",
    "Dark2", "Accent", "Pastel2", "tab10",
)


# ------------------------------------------------------------------ #
# Small helpers that mirror the R names so the mapping stays obvious  #
# ------------------------------------------------------------------ #
def _transform_coordinates(v: np.ndarray, zoom: float) -> np.ndarray:
    """R: ``transform_coordinates``. Centre ``v`` at the midpoint of
    its extent and rescale so the absolute max equals ``zoom``. The
    two axes are transformed **independently** (same as the R code),
    which deliberately fills the circle instead of preserving the
    original UMAP aspect ratio."""
    lo, hi = float(np.min(v)), float(np.max(v))
    centred = v - 0.5 * (lo + hi)
    m = float(np.max(np.abs(centred))) or 1.0
    return centred * zoom / m


def _cluster_order(clusters: Sequence[str]) -> List[str]:
    """Preserve pandas-categorical order when given, else first-seen."""
    if isinstance(clusters, pd.Categorical):
        return list(clusters.categories)
    cats = pd.Series(list(clusters)).astype("category")
    return list(cats.cat.categories)


def _resolve_palette(n: int, palette) -> List[str]:
    if palette is None:
        if n <= len(sc_color):
            return list(sc_color[:n])
        cmap = plt.get_cmap("tab20", n)
        return [cmap(i) for i in range(n)]
    if isinstance(palette, str):
        cmap = plt.get_cmap(palette, n)
        return [cmap(i) for i in range(n)]
    palette = list(palette)
    if len(palette) < n:
        # Recycle
        palette = [palette[i % len(palette)] for i in range(n)]
    return palette[:n]


def _pick_palette(n, palette, adata, key, *, fallback_idx=0):
    """Palette precedence for a categorical column:
    1. explicit ``palette`` arg (if given)
    2. ``adata.uns[f"{key}_colors"]`` (if long enough)
    3. ``_DEFAULT_TRACK_PALETTES[fallback_idx]`` matplotlib cmap
    """
    if palette is not None:
        return _resolve_palette(n, palette)
    if adata is not None and key is not None and hasattr(adata, "uns"):
        uns_key = f"{key}_colors"
        if uns_key in adata.uns:
            stored = list(adata.uns[uns_key])
            if len(stored) >= n:
                return stored[:n]
    cmap_name = _DEFAULT_TRACK_PALETTES[
        fallback_idx % len(_DEFAULT_TRACK_PALETTES)
    ]
    cmap = plt.get_cmap(cmap_name, max(n, 1))
    return [cmap(i) for i in range(n)]


def _data_unit_per_pt(ax):
    """Number of data units per 1 typographic point on ``ax``. Used to
    translate fontsize (pt) into angular char widths when rendering
    curved text."""
    fig = ax.figure
    bbox = ax.get_window_extent()
    dx = ax.get_xlim()[1] - ax.get_xlim()[0]
    px_per_data = max(bbox.width, 1.0) / max(dx, 1e-9)
    pt_per_data = px_per_data * 72.0 / fig.dpi
    return 1.0 / max(pt_per_data, 1e-9)


def _current_font_family():
    """Resolve the currently active matplotlib font family to a concrete
    name. We pass this *explicitly* to every per-character ``ax.text``
    call below — without it, matplotlib's rotated-single-character path
    sometimes falls through to ``DejaVu Serif`` even when ``rcParams['font.family']``
    points at a registered sans-serif (e.g. Arial via ``ov.style()``).
    The visible symptom is the outer ring labels appearing in serifs
    while the inner UMAP labels stay sans-serif (issue: 'outer label
    font looks weird vs centre label')."""
    fam = plt.rcParams.get("font.family", ["sans-serif"])
    if isinstance(fam, str):
        fam = [fam]
    name = fam[0] if fam else "sans-serif"
    if name in ("sans-serif", "serif", "monospace", "cursive", "fantasy"):
        # Generic family — resolve to the first concrete entry.
        concrete = plt.rcParams.get(f"font.{name}", [])
        if concrete:
            return concrete[0]
    return name


def _bend_one_line(ax, line, a_center_deg, radius, fontsize, *,
                   color="black", zorder=5, char_width_ratio=0.55,
                   fontname=None):
    """Draw one line of text curved along the arc at ``radius``, centered
    on angle ``a_center_deg`` (degrees). Emulates circlize's
    ``facing='bending.inside'`` with ``niceFacing=TRUE``: the upper half
    (0° < mid < 180°) has letter tops pointing outward (reading upright
    from outside); the lower half is flipped so tops point inward, still
    reading upright. Letters progress so letter 0 sits on the viewer's
    LEFT (i.e., larger angle in the upper half, smaller angle in the
    lower half)."""
    if not line:
        return
    if fontname is None:
        fontname = _current_font_family()
    n = len(line)
    upt = _data_unit_per_pt(ax)
    char_w_data = fontsize * char_width_ratio * upt
    angle_per_char = np.rad2deg(char_w_data / max(radius, 1e-6))

    mid = a_center_deg % 360.0
    # niceFacing for bending.inside: in the lower half (180°–360°) tops
    # would otherwise point downward, so flip to tops-inward.
    flip = 180.0 < mid < 360.0

    for i, ch in enumerate(line):
        offset = (i - (n - 1) / 2.0) * angle_per_char
        if flip:
            ang = a_center_deg + offset
            rot = (ang + 90.0) % 360.0  # tops inward
        else:
            ang = a_center_deg - offset
            rot = (ang - 90.0) % 360.0  # tops outward
        rad = np.deg2rad(ang)
        ax.text(
            radius * np.cos(rad), radius * np.sin(rad), ch,
            ha="center", va="center",
            rotation=rot, rotation_mode="anchor",
            fontsize=fontsize, color=color, zorder=zorder,
            fontname=fontname,
        )


def _bending_label(ax, text, a0_deg, a1_deg, radius, fontsize, *,
                   color="black", zorder=5, char_width_ratio=0.55,
                   max_lines=3, fontname=None):
    """Place ``text`` centered in the sector ``[a0_deg, a1_deg]`` along
    the arc at ``radius``, wrapping to at most ``max_lines`` lines if the
    label is too long to fit at the sector's angular width. Extra lines
    stack radially outward so labels never intrude into tracks."""
    import textwrap
    text = str(text).strip()
    if not text:
        return
    if fontname is None:
        fontname = _current_font_family()
    mid = 0.5 * (a0_deg + a1_deg)
    sector_w = max(a1_deg - a0_deg, 1e-3)

    upt = _data_unit_per_pt(ax)
    char_w_data = fontsize * char_width_ratio * upt
    angle_per_char = np.rad2deg(char_w_data / max(radius, 1e-6))
    max_chars = max(3, int(0.95 * sector_w / max(angle_per_char, 1e-6)))

    if len(text) <= max_chars:
        lines = [text]
    else:
        lines = textwrap.wrap(
            text, width=max_chars, break_long_words=False,
            break_on_hyphens=False,
        ) or [text]
        if len(lines) > max_lines:
            # Merge tail lines so we respect the line cap
            lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1:])]

    line_h_data = fontsize * 1.25 * upt
    # Multi-line reading order depends on the viewer's visual up. In the
    # upper half the viewer is "above" the circle: first line sits at the
    # largest radius (furthest from centre). In the lower half the viewer
    # is "below", so first line sits at the smallest radius (closest to
    # the outer ring).
    flip = 180.0 < (mid % 360.0) < 360.0
    n_lines = len(lines)
    for li, line in enumerate(lines):
        offset = li if flip else (n_lines - 1 - li)
        r = radius + offset * line_h_data
        _bend_one_line(
            ax, line, mid, r, fontsize,
            color=color, zorder=zorder,
            char_width_ratio=char_width_ratio,
            fontname=fontname,
        )


def _radial_outer_labels(ax, items, label_r, fontsize, *,
                         color="black", zorder=5, fontname=None,
                         repel=True, leader_color="#888",
                         leader_lw=0.4, wrap_width=12):
    """Draw cluster names *horizontally* just outside the ring.

    Each label is a SINGLE ``ax.text`` placed at the sector midpoint;
    long names wrap to multiple lines (``textwrap``) so they don't
    crowd neighbours. The anchor is chosen per quadrant so labels
    radiate outward visually without ever rotating: the left half uses
    ``ha='right'``, the right half ``ha='left'``; top/bottom regions
    centre horizontally and stack the wrapped lines above/below the
    midpoint. If ``adjustText`` is available, overlaps are repelled
    and a thin leader line is drawn back to the sector midpoint.

    ``items`` is an iterable of ``(name, mid_angle_deg)`` pairs."""
    import re
    import textwrap

    def _wrap(name: str, width: int) -> str:
        """Wrap on whitespace, '_' or '-' (which are common separators
        in cluster names), keeping the separators."""
        if len(name) <= width:
            return name
        # Split keeping the separator on the preceding token so the
        # rendered line shows e.g. "Memory_" / "B_Cell".
        toks, buf = [], ""
        for piece in re.split(r"([ _\-])", name):
            buf += piece
            if piece in (" ", "_", "-"):
                toks.append(buf)
                buf = ""
        if buf:
            toks.append(buf)
        if not toks:
            return name
        lines, cur = [], ""
        for t in toks:
            if cur and len(cur) + len(t) > width:
                lines.append(cur)
                cur = t
            else:
                cur += t
        if cur:
            lines.append(cur)
        # Fallback: any single token still longer than width gets a
        # hard textwrap so very long monolithic names don't blow out.
        out = []
        for ln in lines:
            if len(ln) > width:
                out.extend(textwrap.wrap(ln, width=width) or [ln])
            else:
                out.append(ln)
        return "\n".join(out)

    if fontname is None:
        fontname = _current_font_family()
    texts = []
    for name, mid in items:
        m = mid % 360.0
        rad = np.deg2rad(m)
        cx, cy = np.cos(rad), np.sin(rad)
        x = label_r * cx
        y = label_r * cy
        # Quadrant-aware alignment so the text edge nearest the ring
        # is the anchor point — keeps the label visually radiating
        # outward without rotation.
        if cx > 0.30:
            ha = "left"
        elif cx < -0.30:
            ha = "right"
        else:
            ha = "center"
        if cy > 0.30:
            va = "bottom"
        elif cy < -0.30:
            va = "top"
        else:
            va = "center"
        wrapped = _wrap(str(name), wrap_width)
        t = ax.text(
            x, y, wrapped,
            ha=ha, va=va,
            rotation=0,
            fontsize=fontsize, color=color, zorder=zorder,
            fontname=fontname,
            linespacing=0.95,
        )
        texts.append(t)
    if not repel or not texts:
        return
    try:
        from adjustText import adjust_text
    except ImportError:
        return
    adjust_text(
        texts, ax=ax,
        only_move={"text": "xy", "static": "xy"},
        expand=(1.05, 1.15),
        arrowprops=dict(arrowstyle="-", color=leader_color, lw=leader_lw),
    )


def _draw_sector_ticks(ax, a0_deg, a1_deg, r_base, n_cells, *,
                       tick_len=0.012, tick_color="black", tick_lw=0.5,
                       fontsize=4.5, text_color="black", zorder=4.6,
                       fontname=None):
    """Draw ``circos.axis``-style tick marks on the outer edge of a
    sector at radius ``r_base``, pointing radially outward. Ticks sit at
    integer values of the log10 cell rank (R: ``x_polar2``), matching
    plot_circlize's default axis. Numeric labels (small) sit just
    beyond each tick."""
    if fontname is None:
        fontname = _current_font_family()
    log_max = float(np.log10(max(n_cells, 1)))
    if log_max <= 0:
        tick_vals = [0]
    else:
        tick_vals = list(range(0, int(np.floor(log_max)) + 1))
    # Baseline arc: short line along the outer edge of the ring
    n_arc = 30
    arc_rad = np.deg2rad(np.linspace(a0_deg, a1_deg, n_arc))
    ax.plot(
        r_base * np.cos(arc_rad), r_base * np.sin(arc_rad),
        color=tick_color, lw=tick_lw, zorder=zorder,
    )
    for tv in tick_vals:
        if log_max <= 0:
            frac = 0.0
        else:
            frac = tv / log_max if log_max > 0 else 0.0
        ang = a0_deg + frac * (a1_deg - a0_deg)
        rad = np.deg2rad(ang)
        x0 = r_base * np.cos(rad)
        y0 = r_base * np.sin(rad)
        x1 = (r_base + tick_len) * np.cos(rad)
        y1 = (r_base + tick_len) * np.sin(rad)
        ax.plot([x0, x1], [y0, y1],
                color=tick_color, lw=tick_lw, zorder=zorder)
        # Small numeric label just beyond tick; rotated along tangent so
        # it sits flat on the circle (matches circos.axis default).
        lx = (r_base + tick_len * 1.6) * np.cos(rad)
        ly = (r_base + tick_len * 1.6) * np.sin(rad)
        mid = ang % 360.0
        flip = 90.0 < mid < 270.0
        rot = (mid + 180.0) % 360.0 if flip else mid
        ax.text(
            lx, ly, str(tv), ha="center", va="center",
            rotation=rot, rotation_mode="anchor",
            fontsize=fontsize, color=text_color, zorder=zorder,
            fontname=fontname,
        )


def _run_length(vals: np.ndarray):
    """Return ``(starts, lengths, values)`` of consecutive runs."""
    if len(vals) == 0:
        return np.array([]), np.array([]), np.array([])
    change = np.concatenate([[True], vals[1:] != vals[:-1]])
    starts = np.flatnonzero(change)
    lengths = np.diff(np.concatenate([starts, [len(vals)]]))
    values = vals[starts]
    return starts, lengths, values


# ------------------------------------------------------------------ #
# Public API                                                          #
# ------------------------------------------------------------------ #
@register_function(
    aliases=[
        "plot1cell",
        "circlize_umap",
        "circular_umap",
        "环形UMAP",
        "圆形UMAP",
    ],
    category="pl",
    description=(
        "Circular UMAP/t-SNE with concentric per-cell metadata tracks "
        "(Python port of R plot1cell::plot_circlize)."
    ),
    examples=[
        "# basic: clusters only",
        "ov.pl.plot1cell(adata, clusters='leiden', basis='X_umap')",
        "# with extra metadata tracks",
        "ov.pl.plot1cell(adata, clusters='cell_type',",
        "                tracks=['sample', 'phase'])",
    ],
    related=["pl.embedding", "pl.umap", "pl.embedding_atlas"],
)
def plot1cell(
    adata,
    clusters: str,
    basis: str = "X_umap",
    tracks: Optional[Sequence[str]] = None,
    *,
    coord_scale: float = 0.8,
    point_size: float = 3.0,
    point_alpha: float = 0.3,
    contour_levels: Optional[Sequence[float]] = (0.2, 0.3),
    contour_color: str = "#ae9c76",
    kde_n: int = 200,
    do_label: bool = True,
    label_fontsize: float = 9.0,
    label_orient: str = "radial",
    cluster_palette=None,
    track_palette=None,
    track_palettes: Optional[Sequence] = None,
    bg_color: Optional[str] = None,
    gap_between_deg: float = 2.0,
    gap_start_deg: float = 12.0,
    cluster_track_width: float = 0.035,
    track_width: float = 0.025,
    track_gap: float = 0.004,
    cluster_label_pad: float = 0.03,
    show_ticks: bool = True,
    tick_fontsize: float = 4.5,
    tick_length: float = 0.012,
    figsize=(7, 7),
    ax: Optional[Axes] = None,
    show: bool = True,
    return_data: bool = False,
):
    """Circular UMAP with metadata tracks.

    Mirrors plot1cell::plot_circlize (Wu 2021). Clusters are laid out
    as arc sectors on the circumference, sector length proportional
    to ``log10(n_cells)``. The scatter is drawn in Cartesian
    coordinates **inside** the unit circle, with a Gaussian-KDE
    contour overlay. Each entry in ``tracks`` becomes one extra
    concentric ring coloured by the run-length segments of that
    metadata column **within each cluster sector**.

    Parameters
    ----------
    adata : AnnData
    clusters : str
        Key in ``adata.obs`` giving the cluster label per cell.
    basis : str
        Key in ``adata.obsm``; first two columns are used.
    tracks : list[str] | None
        Additional ``adata.obs`` columns to show as outer rings.
    coord_scale : float
        ``zoom`` parameter from the R version; the scatter fills
        ``[-coord_scale, coord_scale]`` on each axis.
    contour_levels : tuple[float, ...] | None
        Level set(s) of the 2-D KDE to overlay. ``None`` disables
        contours.
    gap_between_deg, gap_start_deg : float
        Angular gaps (degrees) between adjacent cluster sectors and
        at the circle's starting point.
    cluster_track_width, track_width : float
        Radial thickness of the cluster ring and each metadata ring,
        expressed as a fraction of the unit radius.
    ax : matplotlib Axes | None
        If given, draw into it (must be ``aspect='equal'``). A new
        figure is created otherwise.
    return_data : bool
        If True, also return the per-cell dataframe used for
        plotting (useful for reproducing or extending the figure).

    Returns
    -------
    ax : matplotlib.axes.Axes
    (ax, df) if ``return_data=True``.
    """
    # --- 1. Fetch + validate inputs -------------------------------
    if basis not in adata.obsm:
        raise KeyError(f"basis {basis!r} not in adata.obsm")
    if clusters not in adata.obs:
        raise KeyError(f"clusters column {clusters!r} not in adata.obs")
    tracks = list(tracks) if tracks else []
    for t in tracks:
        if t not in adata.obs:
            raise KeyError(f"track column {t!r} not in adata.obs")

    xy = np.asarray(adata.obsm[basis])[:, :2]
    cl_vals = adata.obs[clusters].astype(str).to_numpy()
    cl_order = _cluster_order(adata.obs[clusters])

    # Transform to the plotting square
    x = _transform_coordinates(xy[:, 0], coord_scale)
    y = _transform_coordinates(xy[:, 1], coord_scale)

    df = pd.DataFrame({
        "cell": np.asarray(adata.obs_names),
        "cluster": cl_vals,
        "x": x,
        "y": y,
    })
    for t in tracks:
        df[t] = adata.obs[t].astype(str).to_numpy()

    # Within each cluster, rank 1..N. x_polar2 = log10(rank) is the
    # *width* assigned to each cell along its sector (same as R).
    df["x_polar"] = df.groupby("cluster").cumcount() + 1

    # --- 2. Sector geometry ---------------------------------------
    # angle span of each cluster is proportional to log10(n_cluster),
    # matching circlize's x-axis = x_polar2.
    counts = df["cluster"].value_counts().reindex(cl_order).fillna(0).astype(int)
    log_counts = np.log10(counts.clip(lower=1).to_numpy())
    n_clusters = len(cl_order)
    total_gap = (n_clusters - 1) * gap_between_deg + gap_start_deg
    usable = 360.0 - total_gap
    if usable <= 0:
        raise ValueError(
            f"gaps ({total_gap}°) exceed 360°; reduce gap_between_deg / "
            f"gap_start_deg or collapse clusters."
        )
    cluster_deg = usable * log_counts / log_counts.sum()

    # Start just past 3-o'clock going counter-clockwise: matches the
    # circlize default where the start-gap sits at angle 0 (east).
    sector_bounds: dict[str, tuple[float, float]] = {}
    theta = 0.5 * gap_start_deg
    for cl, deg in zip(cl_order, cluster_deg):
        a0 = theta
        a1 = theta + deg
        sector_bounds[cl] = (a0, a1)
        theta = a1 + gap_between_deg

    # --- 3. Figure setup ------------------------------------------
    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
        created_fig = True
    else:
        fig = ax.figure
    ax.set_aspect("equal")
    # Outer edge of the cluster ring; tracks stack from here outward.
    r_cluster_out = 1.0 + cluster_track_width
    tracks_total = len(tracks) * (track_width + track_gap)
    # Outer edge of the last ring drawn (cluster ring if no tracks).
    r_outer_ring = r_cluster_out + tracks_total
    tick_margin = (tick_length * 2.2 if show_ticks else 0.0)
    # Reserve room for up-to-3-line bending labels plus a safety margin.
    # Long cluster names (e.g. "kidney loop of Henle thick ascending limb
    # epithelial cell") stack radially outward at ~1.25 * fontsize per
    # line; keep the plot extent generous so none get clipped.
    label_margin = max(0.55, label_fontsize * 0.06)
    outer = r_outer_ring + tick_margin + cluster_label_pad + label_margin
    ax.set_xlim(-outer, outer)
    ax.set_ylim(-outer, outer)
    if bg_color is not None:
        ax.set_facecolor(bg_color)
        if created_fig:
            fig.patch.set_facecolor(bg_color)
    ax.set_axis_off()

    # --- 4. Scatter + KDE -----------------------------------------
    # Cluster palette: explicit > adata.uns[{clusters}_colors] > sc_color
    # (or tab20 fallback for > len(sc_color)).
    if cluster_palette is None and hasattr(adata, "uns") \
            and f"{clusters}_colors" in adata.uns \
            and len(list(adata.uns[f"{clusters}_colors"])) >= n_clusters:
        cluster_colors = list(adata.uns[f"{clusters}_colors"])[:n_clusters]
    else:
        cluster_colors = _resolve_palette(n_clusters, cluster_palette)
    cl_to_color = dict(zip(cl_order, cluster_colors))
    pt_colors = [cl_to_color[c] for c in df["cluster"]]
    ax.scatter(
        df["x"].to_numpy(), df["y"].to_numpy(),
        s=point_size, c=pt_colors, alpha=point_alpha,
        linewidths=0, zorder=2,
    )

    if contour_levels is not None and len(df) >= 10:
        try:
            kde = gaussian_kde(np.vstack([df["x"].to_numpy(), df["y"].to_numpy()]))
            lim = coord_scale * 1.05
            gx, gy = np.mgrid[-lim:lim:complex(kde_n), -lim:lim:complex(kde_n)]
            zz = kde(np.vstack([gx.ravel(), gy.ravel()])).reshape(gx.shape)
            # Normalise to match the R ``levels`` interpretation (values
            # are roughly the density relative to its max over the grid).
            zz = zz / (zz.max() + 1e-12)
            ax.contour(gx, gy, zz, levels=sorted(contour_levels),
                       colors=contour_color, linewidths=0.8, zorder=3)
        except Exception as exc:  # pragma: no cover — KDE can fail on tiny data
            warnings.warn(f"KDE contour skipped: {exc}")

    # --- 5. Cluster ring ------------------------------------------
    r_in = 1.0
    r_out = r_cluster_out
    for cl, (a0, a1) in sector_bounds.items():
        w = Wedge(
            center=(0, 0), r=r_out, theta1=a0, theta2=a1,
            width=r_out - r_in, facecolor=cl_to_color[cl],
            edgecolor="none", linewidth=0, zorder=4,
        )
        ax.add_patch(w)

    # --- 6. In-UMAP cluster labels --------------------------------
    if do_label:
        import matplotlib.patheffects as pe
        texts = []
        for cl in cl_order:
            sub = df[df["cluster"] == cl]
            texts.append(ax.text(
                sub["x"].median(), sub["y"].median(), str(cl),
                ha="center", va="center", fontsize=label_fontsize,
                zorder=6,
                path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            ))
        try:
            from adjustText import adjust_text
            adjust_text(
                texts, ax=ax,
                expand=(1.1, 1.2),
                arrowprops=dict(arrowstyle="-", color="#666", lw=0.5),
                only_move={"text": "xy"},
            )
        except ImportError:
            # adjustText is optional — silently skip repel if unavailable.
            pass

    # --- 7. Metadata tracks ---------------------------------------
    # Remember per-track colors so the legend stays consistent with the
    # rendered rings (each track gets its own palette by default).
    track_colors_map: dict[str, dict[str, object]] = {}
    track_level_order: dict[str, list] = {}

    def _levels_for(col):
        try:
            return list(adata.obs[col].astype("category").cat.categories)
        except Exception:
            return sorted(df[col].unique().tolist())

    for t_idx, t in enumerate(tracks):
        r0 = r_out + track_gap + t_idx * (track_width + track_gap)
        r1 = r0 + track_width
        levels = _levels_for(t)
        # Per-track palette precedence: `track_palettes[t_idx]` > `track_palette`
        # > `adata.uns[f"{t}_colors"]` > distinct default per track index.
        per_track_override = (
            track_palettes[t_idx]
            if track_palettes is not None and t_idx < len(track_palettes)
            else None
        )
        if per_track_override is not None:
            colors = _resolve_palette(len(levels), per_track_override)
        elif track_palette is not None:
            colors = _resolve_palette(len(levels), track_palette)
        else:
            colors = _pick_palette(
                len(levels), None, adata, t, fallback_idx=t_idx + 1,
            )
        lvl_to_color = dict(zip(levels, colors))
        track_colors_map[t] = lvl_to_color
        track_level_order[t] = levels

        for cl in cl_order:
            a0, a1 = sector_bounds[cl]
            sub = df[df["cluster"] == cl].sort_values(t)
            vals = sub[t].to_numpy()
            _, lengths, rleg_vals = _run_length(vals)
            total = len(sub)
            if total == 0:
                continue
            cum = 0
            for length, val in zip(lengths, rleg_vals):
                ang0 = a0 + (cum / total) * (a1 - a0)
                ang1 = a0 + ((cum + length) / total) * (a1 - a0)
                ax.add_patch(Wedge(
                    center=(0, 0), r=r1, theta1=ang0, theta2=ang1,
                    width=r1 - r0, facecolor=lvl_to_color[val],
                    edgecolor="none", linewidth=0, zorder=4,
                ))
                cum += length

        # Track label inside the start-gap, stacked radially so
        # multiple tracks don't collide. (The start gap is centred on
        # angle 0 — the right side of the circle.)
        gap_mid_rad = np.deg2rad(0.0)
        mid_r = 0.5 * (r0 + r1)
        ax.text(
            np.cos(gap_mid_rad) * (mid_r + 0.005),
            np.sin(gap_mid_rad) * (mid_r + 0.005),
            t, ha="center", va="center",
            fontsize=label_fontsize * 0.75,
            rotation=-90, rotation_mode="anchor",
            zorder=5,
            fontname=_current_font_family(),
        )

    # --- 7b. Outer-ring ticks (circos.axis) + bending cluster labels ---
    if show_ticks:
        for cl, (a0, a1) in sector_bounds.items():
            _draw_sector_ticks(
                ax, a0, a1, r_outer_ring,
                int(counts[cl]),
                tick_len=tick_length,
                fontsize=tick_fontsize,
            )

    if do_label:
        label_r = (
            r_outer_ring
            + (tick_length * 2.2 if show_ticks else 0.0)
            + cluster_label_pad
        )
        if label_orient == "bending":
            for cl, (a0, a1) in sector_bounds.items():
                _bending_label(
                    ax, str(cl), a0, a1, label_r,
                    label_fontsize, zorder=5,
                )
        else:  # "radial" — single ax.text per label, native kerning
            items = [
                (cl, 0.5 * (a0 + a1))
                for cl, (a0, a1) in sector_bounds.items()
            ]
            _radial_outer_labels(
                ax, items, label_r, label_fontsize, zorder=5,
            )

    # --- 8. Track legends -----------------------------------------
    if tracks:
        legend_handles = []
        for t in tracks:
            lvl_to_color = track_colors_map[t]
            for lvl in track_level_order[t]:
                col = lvl_to_color[lvl]
                legend_handles.append(
                    plt.Line2D([], [], marker="s", linestyle="",
                               markerfacecolor=col, markeredgecolor=col,
                               markersize=8, label=f"{t}={lvl}")
                )
        ax.legend(
            handles=legend_handles, loc="center left",
            bbox_to_anchor=(1.02, 0.5), frameon=False,
            fontsize=label_fontsize * 0.8,
        )

    if show and created_fig:
        plt.show()

    if return_data:
        return ax, df
    return ax
