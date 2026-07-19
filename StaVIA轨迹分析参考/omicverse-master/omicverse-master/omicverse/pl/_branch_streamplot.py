"""Branch-aware pseudotime ribbon plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from numpy.linalg import LinAlgError
from pandas.api.types import CategoricalDtype
from scipy.stats import gaussian_kde

from .._registry import register_function
from ._palette import palette_28, palette_56, palette_112


def sigmoid_curve(x: np.ndarray, center: float, steepness: float) -> np.ndarray:
    r"""Smooth logistic gate commonly used for branch splits and tapers."""
    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-(x - center) * steepness))


def tapered_kde(
    values: np.ndarray,
    x: np.ndarray,
    *,
    bw: float = 0.15,
    pad: float = 0.035,
) -> np.ndarray:
    r"""Estimate a tapered 1D density profile on pseudotime."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    x = np.asarray(x, dtype=float)

    if values.size < 3:
        return np.zeros_like(x)

    # Degenerate groups with tied pseudotime values produce a singular
    # covariance matrix inside gaussian_kde.
    if np.unique(values).size < 2:
        return np.zeros_like(x)

    try:
        density = gaussian_kde(values, bw_method=bw)(x)
    except LinAlgError:
        return np.zeros_like(x)

    q05, q95 = np.quantile(values, [0.05, 0.95])
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    start = max(x_min, float(q05) - pad)
    end = min(x_max, float(q95) + pad)
    gate = sigmoid_curve(x, start, 40.0) * (1.0 - sigmoid_curve(x, end, 40.0))
    return density * gate


def _ordered_groups(obs: pd.DataFrame, key: str) -> list[str]:
    series = obs[key]
    if isinstance(series.dtype, CategoricalDtype):
        return [str(cat) for cat in series.cat.categories]
    return list(dict.fromkeys(series.astype(str).tolist()))


def compute_group_kde_profiles(
    obs: pd.DataFrame,
    *,
    group_key: str,
    pseudotime_key: str,
    labels: Sequence[str] | None = None,
    x: np.ndarray | None = None,
    bw: float = 0.15,
    pad: float = 0.035,
    count_power: float = 0.3,
    normalize_pseudotime: bool | str = "auto",
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    r"""Build tapered pseudotime density profiles for categorical groups.

    Parameters
    ----------
    obs
        Observation table containing group labels and pseudotime values.
    group_key
        Column in ``obs`` containing cell-state or subtype labels.
    pseudotime_key
        Column in ``obs`` containing pseudotime values.
    labels
        Explicit label order to compute. If omitted, categorical order in
        ``obs[group_key]`` is respected when available.
    x
        Pseudotime grid. Defaults to ``np.linspace(0, 1, 800)``.
    bw
        Bandwidth passed to :class:`scipy.stats.gaussian_kde`.
    pad
        Extra taper padding beyond the 5th-95th percentile interval.
    count_power
        Exponent used to scale profiles by group abundance. Lower values
        preserve the visibility of smaller groups.
    normalize_pseudotime
        Whether to min-max normalize pseudotime values before KDE. The default
        ``"auto"`` normalizes when ``x`` is not supplied and the observed
        pseudotime range falls outside ``[0, 1]``. This keeps Monocle-style
        pseudotime scales compatible with the default ``0-1`` stream grid.

    Returns
    -------
    tuple[np.ndarray, dict[str, np.ndarray]]
        Grid coordinates and one tapered density profile per label.
    """
    if group_key not in obs.columns:
        raise KeyError(f"{group_key!r} not found in obs columns")
    if pseudotime_key not in obs.columns:
        raise KeyError(f"{pseudotime_key!r} not found in obs columns")

    x_was_none = x is None
    if x_was_none:
        x = np.linspace(0.0, 1.0, 800)
    else:
        x = np.asarray(x, dtype=float)

    groups = obs[group_key].astype(str)
    if labels is None:
        labels = _ordered_groups(obs, group_key)

    all_time = obs[pseudotime_key].to_numpy(dtype=float)
    all_time = all_time[np.isfinite(all_time)]
    do_normalize = False
    if normalize_pseudotime == "auto":
        do_normalize = bool(
            x_was_none
            and all_time.size > 0
            and (np.nanmin(all_time) < 0.0 or np.nanmax(all_time) > 1.0)
        )
    else:
        do_normalize = bool(normalize_pseudotime)
    if do_normalize and all_time.size > 0:
        time_min = float(np.nanmin(all_time))
        time_max = float(np.nanmax(all_time))
        time_range = time_max - time_min
    else:
        time_min = 0.0
        time_range = 0.0

    size_factor = groups.value_counts().pow(count_power).to_dict()
    profiles: dict[str, np.ndarray] = {}
    for label in labels:
        mask = groups == str(label)
        values = obs.loc[mask, pseudotime_key].to_numpy(dtype=float)
        if do_normalize and time_range > 0:
            values = (values - time_min) / time_range
        profiles[str(label)] = tapered_kde(values, x, bw=bw, pad=pad) * float(size_factor.get(str(label), 1.0))

    return x, profiles


def make_branch_centerline(
    x: np.ndarray,
    *,
    amplitude: float,
    center: float,
    steepness: float,
    power: float = 1.1,
    baseline: float = 0.0,
) -> np.ndarray:
    r"""Create a smooth centerline that bends away from the trunk."""
    x = np.asarray(x, dtype=float)
    return baseline + amplitude * (sigmoid_curve(x, center, steepness) ** power)


def _copy_branches(branches: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for branch in branches:
        center = np.asarray(branch["center"], dtype=float)
        layers = [(str(label), np.asarray(width, dtype=float).copy()) for label, width in branch["layers"]]
        copied.append({"center": center.copy(), "layers": layers})
    return copied


def _collect_branch_labels(
    branches: Sequence[Mapping[str, Any]],
    *,
    label_positions: Mapping[str, tuple[float, float, float]] | None = None,
) -> list[str]:
    labels: list[str] = []
    for branch in branches:
        for label, _ in branch["layers"]:
            if label not in labels:
                labels.append(str(label))
    if label_positions is not None:
        for label in label_positions:
            if label not in labels:
                labels.append(str(label))
    return labels


def _resolve_branch_palette(
    labels: Sequence[str],
    palette: Mapping[str, str] | Sequence[str] | str | None,
) -> dict[str, str]:
    labels = [str(label) for label in labels]
    if not labels:
        return {}

    if palette is None:
        if len(labels) <= len(palette_28):
            colors = list(palette_28[: len(labels)])
        elif len(labels) <= len(palette_56):
            colors = list(palette_56[: len(labels)])
        elif len(labels) <= len(palette_112):
            colors = list(palette_112[: len(labels)])
        else:
            cmap = plt.get_cmap("tab20", len(labels))
            colors = [to_hex(cmap(i), keep_alpha=True) for i in range(len(labels))]
        return dict(zip(labels, colors))

    if isinstance(palette, Mapping):
        resolved = dict(palette)
        if any(label not in resolved for label in labels):
            fallback = _resolve_branch_palette(labels, None)
            fallback.update(resolved)
            resolved = fallback
        return {label: resolved[label] for label in labels}

    if isinstance(palette, str):
        cmap = plt.get_cmap(palette, len(labels))
        return {label: to_hex(cmap(i), keep_alpha=True) for i, label in enumerate(labels)}

    colors = list(palette)
    if not colors:
        raise ValueError("Palette sequence must contain at least one colour.")
    if len(colors) < len(labels):
        colors = [colors[i % len(colors)] for i in range(len(labels))]
    return {label: colors[i] for i, label in enumerate(labels)}


def _stack_branch(
    ax: Axes,
    x: np.ndarray,
    center: np.ndarray,
    layers: Sequence[tuple[str, np.ndarray]],
    palette: Mapping[str, str],
    *,
    min_visible_width: float = 1e-4,
) -> None:
    total = np.zeros_like(x)
    for _, width in layers:
        total += width

    cumulative = np.zeros_like(x)
    for label, width in layers:
        lower = center - total / 2.0 + cumulative
        upper = lower + width
        mask = width > min_visible_width
        if mask.sum() < 5:
            cumulative += width
            continue
        ax.fill_between(
            x,
            lower,
            upper,
            where=mask,
            color=palette[label],
            linewidth=0,
            interpolate=True,
            zorder=3,
        )
        cumulative += width


def _scale_branch_widths(
    branches: list[dict[str, Any]],
    x: np.ndarray,
    *,
    scale_to: float | str | None,
) -> None:
    if scale_to is None:
        return

    totals = []
    for branch in branches:
        total = np.zeros_like(x)
        for _, width in branch["layers"]:
            total += width
        totals.append(float(total.max()))
    max_total = max(totals) if totals else 0.0
    if max_total <= 0:
        return

    if scale_to == "auto":
        scale_to = 0.32
    elif isinstance(scale_to, str):
        raise ValueError("`scale_to` must be a number, 'auto', or None.")

    scale = scale_to / max_total
    for branch in branches:
        branch["layers"] = [(label, width * scale) for label, width in branch["layers"]]


def _branch_y_bounds(
    x: np.ndarray,
    branches: Sequence[Mapping[str, Any]],
) -> tuple[float, float]:
    lower_values = []
    upper_values = []
    for branch in branches:
        center = np.asarray(branch["center"], dtype=float)
        total = np.zeros_like(x)
        for _, width in branch["layers"]:
            total += np.asarray(width, dtype=float)
        lower_values.append(center - total / 2.0)
        upper_values.append(center + total / 2.0)

    if not lower_values or not upper_values:
        return -0.5, 0.5

    y_min = float(np.nanmin(np.concatenate(lower_values)))
    y_max = float(np.nanmax(np.concatenate(upper_values)))
    if not np.isfinite(y_min) or not np.isfinite(y_max):
        return -0.5, 0.5
    if y_min == y_max:
        y_min -= 0.25
        y_max += 0.25
    return y_min, y_max


def _auto_ylim_and_axis_y(
    x: np.ndarray,
    branches: Sequence[Mapping[str, Any]],
    *,
    ylim: tuple[float, float] | None,
    axis_y: float | str | None,
) -> tuple[tuple[float, float], float | None]:
    y_min, y_max = _branch_y_bounds(x, branches)
    span = max(y_max - y_min, 0.2)

    resolved_axis_y = axis_y
    if axis_y == "auto":
        resolved_axis_y = y_min - span * 0.16
    elif isinstance(axis_y, str):
        raise ValueError("`axis_y` must be a number, 'auto', or None.")

    if ylim is None:
        bottom = y_min - span * 0.30
        top = y_max + span * 0.18
        if resolved_axis_y is not None:
            bottom = min(bottom, float(resolved_axis_y) - span * 0.10)
        ylim = (float(bottom), float(top))
    return ylim, resolved_axis_y


def _auto_branch_label_positions(
    x: np.ndarray,
    branches: Sequence[Mapping[str, Any]],
    *,
    fontsize: float = 12,
) -> dict[str, tuple[float, float, float]]:
    positions: dict[str, tuple[float, float, float]] = {}
    for branch in branches:
        center = np.asarray(branch["center"], dtype=float)
        total = np.zeros_like(x)
        for _, width in branch["layers"]:
            total += width

        cumulative = np.zeros_like(x)
        for label, width in branch["layers"]:
            width = np.asarray(width, dtype=float)
            if not np.any(np.isfinite(width)) or np.nanmax(width) <= 0:
                cumulative += width
                continue
            idx = int(np.nanargmax(width))
            y = center[idx] - total[idx] / 2.0 + cumulative[idx] + width[idx] / 2.0
            positions[str(label)] = (float(x[idx]), float(y), float(fontsize))
            cumulative += width
    return positions


def _profile_peak_positions(
    x: np.ndarray,
    profiles: Mapping[str, np.ndarray],
    labels: Sequence[str],
) -> dict[str, float]:
    peaks: dict[str, float] = {}
    for label in labels:
        profile = np.asarray(profiles[str(label)], dtype=float)
        if profile.size == 0 or not np.any(np.isfinite(profile)) or np.nanmax(profile) <= 0:
            peaks[str(label)] = np.nan
            continue
        peaks[str(label)] = float(x[int(np.nanargmax(profile))])
    return peaks


def _infer_stream_groups(
    x: np.ndarray,
    profiles: Mapping[str, np.ndarray],
    labels: Sequence[str],
    *,
    trunk_groups: Sequence[str] | None,
    branch_groups: Mapping[str, float] | None,
    branch_center: float,
    branch_amplitude: float,
    n_branches: int,
) -> tuple[list[str], dict[str, float]]:
    labels = [str(label) for label in labels]
    if trunk_groups is not None:
        trunk = [str(group) for group in trunk_groups]
    else:
        peaks = _profile_peak_positions(x, profiles, labels)
        trunk = [
            label
            for label in labels
            if np.isfinite(peaks.get(label, np.nan)) and peaks[label] <= branch_center
        ]
        if len(trunk) == len(labels):
            trunk = labels[:-1]
        if not trunk:
            n_trunk = max(1, int(np.ceil(len(labels) * 0.5)))
            trunk = labels[:n_trunk]

    if branch_groups is not None:
        branches = {str(group): float(amplitude) for group, amplitude in branch_groups.items()}
    else:
        branch_labels = [label for label in labels if label not in set(trunk)]
        if not branch_labels:
            branch_labels = labels[-1:]
            trunk = [label for label in trunk if label not in branch_labels]
        n_branches = max(1, int(n_branches))
        if n_branches == 1:
            amplitudes = [branch_amplitude]
        else:
            amplitudes = np.linspace(branch_amplitude, -branch_amplitude, n_branches).tolist()
        branches = {
            label: float(amplitudes[i % len(amplitudes)])
            for i, label in enumerate(branch_labels)
        }

    return trunk, branches


def _branch_streamplot_from_annotations(
    obs: pd.DataFrame,
    *,
    group_key: str,
    pseudotime_key: str,
    trunk_groups: Sequence[str] | None = None,
    branch_groups: Mapping[str, float] | None = None,
    labels: Sequence[str] | None = None,
    branch_center: float = 0.56,
    branch_steepness: float = 11.0,
    branch_power: float = 1.1,
    branch_amplitude: float = 0.28,
    n_branches: int = 2,
    bw: float = 0.15,
    pad: float = 0.035,
    count_power: float = 0.3,
    normalize_pseudotime: bool | str = "auto",
    palette: Mapping[str, str] | Sequence[str] | str | None = None,
    label_positions: Mapping[str, tuple[float, float, float]] | str | None = "auto",
    label_fontsize: float = 12,
    **kwargs,
) -> tuple[Figure, Axes]:
    r"""Plot a branch stream plot from cell annotations.

    This convenience wrapper handles the repetitive pieces needed for common
    trajectory tutorials: KDE profiles are computed from ``obs``, early groups
    are stacked on a shared centerline, and later groups bend away as terminal
    ribbons. Provide ``trunk_groups`` and ``branch_groups`` only when you want
    to override the automatic layout.
    """
    if labels is None:
        labels = _ordered_groups(obs, group_key)
    labels = [str(label) for label in labels]

    x, profiles = compute_group_kde_profiles(
        obs,
        group_key=group_key,
        pseudotime_key=pseudotime_key,
        labels=labels,
        bw=bw,
        pad=pad,
        count_power=count_power,
        normalize_pseudotime=normalize_pseudotime,
    )
    trunk_groups, branch_groups = _infer_stream_groups(
        x,
        profiles,
        labels,
        trunk_groups=trunk_groups,
        branch_groups=branch_groups,
        branch_center=branch_center,
        branch_amplitude=branch_amplitude,
        n_branches=n_branches,
    )

    branches: list[dict[str, Any]] = [
        {
            "center": np.zeros_like(x),
            "layers": [(group, profiles[group]) for group in trunk_groups],
        }
    ]
    branch_layers_by_amplitude: dict[float, list[str]] = {}
    for group, amplitude in branch_groups.items():
        branch_layers_by_amplitude.setdefault(amplitude, []).append(group)

    for amplitude, groups in branch_layers_by_amplitude.items():
        branches.append(
            {
                "center": make_branch_centerline(
                    x,
                    amplitude=amplitude,
                    center=branch_center,
                    steepness=branch_steepness,
                    power=branch_power,
                ),
                "layers": [(group, profiles[group]) for group in groups],
            }
        )

    scale_to = kwargs.pop("scale_to", "auto")
    _scale_branch_widths(branches, x, scale_to=scale_to)
    if label_positions == "auto":
        label_positions = _auto_branch_label_positions(x, branches, fontsize=label_fontsize)

    return branch_streamplot(
        x,
        branches,
        palette=palette,
        label_positions=label_positions,
        scale_to=None,
        **kwargs,
    )


@register_function(
    aliases=["branch_streamplot", "branch stream plot", "branch river plot", "分支流图", "伪时间分支图"],
    category="pl",
    description="Plot branch-aware pseudotime ribbons from obs annotations or precomputed lineage widths.",
    examples=[
        "ov.pl.branch_streamplot(adata.obs, group_key='clusters', pseudotime_key='pseudotime', show=False)",
        "ov.pl.branch_streamplot(x, branches, palette=ov.pl.palette_28, label_positions=labels)",
    ],
    related=["pl.dynamic_trends", "pl.add_streamplot", "single.TrajInfer"],
)
def branch_streamplot(
    x: np.ndarray | pd.DataFrame | Any,
    branches: Sequence[Mapping[str, Any]] | None = None,
    palette: Mapping[str, str] | Sequence[str] | str | None = None,
    *,
    group_key: str | None = None,
    pseudotime_key: str | None = None,
    labels: Sequence[str] | None = None,
    trunk_groups: Sequence[str] | None = None,
    branch_groups: Mapping[str, float] | None = None,
    branch_center: float = 0.56,
    branch_steepness: float = 11.0,
    branch_power: float = 1.1,
    branch_amplitude: float = 0.28,
    n_branches: int = 2,
    bw: float = 0.15,
    pad: float = 0.035,
    count_power: float = 0.3,
    normalize_pseudotime: bool | str = "auto",
    label_positions: Mapping[str, tuple[float, float, float]] | str | None = None,
    figsize: tuple[float, float] = (7.0, 3.5),
    xlim: tuple[float, float] = (-0.02, 1.03),
    ylim: tuple[float, float] | None = None,
    xlabel: str = "Pseudotime",
    xticks: Sequence[float] | None = None,
    axis_y: float | str | None = "auto",
    axis_arrowprops: Mapping[str, Any] | None = None,
    scale_to: float | str | None = "auto",
    min_visible_width: float = 1e-4,
    label_fontsize: float = 12,
    label_fontweight: str = "semibold",
    label_outline_width: float = 5.0,
    label_outline_alpha: float = 0.92,
    tick_labelsize: float = 13,
    xlabel_fontsize: float = 18,
    ax: Axes | None = None,
    show: bool = False,
    save: str | Path | None = None,
    save_pdf: str | Path | None = None,
) -> tuple[Figure, Axes]:
    r"""Render a branch-aware pseudotime stream plot.

    The main entry point accepts an ``obs`` table plus ``group_key`` and
    ``pseudotime_key`` and automatically builds the ribbon layout. Advanced
    users can still pass a pseudotime grid and precomputed branch definitions.

    Parameters
    ----------
    x
        Observation table, or a one-dimensional pseudotime grid shared by all
        precomputed branches.
    branches
        Optional sequence of branch dictionaries for advanced precomputed
        layouts. Each entry must contain:

        - ``center``: array-like centerline with the same length as ``x``
        - ``layers``: ordered ``[(label, width), ...]`` ribbons for that branch

    palette
        Color mapping for labels. Accepts a ``dict``, color sequence, matplotlib
        colormap name, or ``None``. When omitted, omicverse palettes are used.
    group_key
        Column in ``x.obs`` or ``x`` containing cell-state labels when
        plotting directly from annotations.
    pseudotime_key
        Column in ``x.obs`` or ``x`` containing pseudotime values when
        plotting directly from annotations.
    labels
        Optional label order. Categorical order in ``group_key`` is used when
        omitted.
    trunk_groups
        Labels to place on the shared centerline when plotting from
        annotations. If omitted, groups are inferred from KDE peak locations.
    branch_groups
        Optional mapping from label to branch amplitude. Positive and negative
        amplitudes bend branches in opposite directions.
    branch_center, branch_steepness, branch_power, branch_amplitude
        Parameters controlling the automatic branch centerlines.
    n_branches
        Number of branch amplitudes used when ``branch_groups`` is inferred.
    bw, pad, count_power
        KDE bandwidth, taper padding, and abundance scaling used for
        annotation-derived ribbon widths.
    normalize_pseudotime
        Whether to min-max normalize observed pseudotime before estimating KDE
        profiles. The default ``"auto"`` normalizes only when the default
        0-1 grid is used with values outside that range.
    label_positions
        Optional mapping ``label -> (x, y, fontsize)`` for direct text labels.
    figsize
        Figure size used when ``ax`` is not provided.
    xlim, ylim
        Plot limits.
    xlabel
        X-axis label.
    xticks
        Tick locations for pseudotime.
    axis_y
        Y coordinate of the arrow-style pseudotime axis. Set to ``None`` to hide it.
    axis_arrowprops
        Additional keyword arguments passed to ``Axes.annotate`` for the axis arrow.
    scale_to
        Optional maximum branch thickness after rescaling all ribbons together.
    min_visible_width
        Ribbons thinner than this threshold are omitted for visual stability.
    label_fontweight, label_outline_width, label_outline_alpha
        Text styling for direct labels.
    tick_labelsize, xlabel_fontsize
        Axis text sizes.
    ax
        Existing matplotlib axes. When omitted, a new figure is created.
    show
        Whether to call :func:`matplotlib.pyplot.show`.
    save, save_pdf
        Optional output paths.

    Returns
    -------
    tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]
        Figure and axes containing the branch stream plot.
    """
    if isinstance(x, pd.DataFrame) or hasattr(x, "obs"):
        if group_key is None or pseudotime_key is None:
            raise TypeError(
                "`group_key` and `pseudotime_key` are required when the first "
                "argument is an AnnData object or obs DataFrame."
            )
        obs = x if isinstance(x, pd.DataFrame) else x.obs
        if palette is None and not isinstance(x, pd.DataFrame):
            plot_labels = [str(label) for label in (labels if labels is not None else _ordered_groups(obs, group_key))]
            uns_colors = getattr(x, "uns", {}).get(f"{group_key}_colors")
            if uns_colors is not None and len(uns_colors) >= len(plot_labels):
                palette = dict(zip(plot_labels, uns_colors))
        return _branch_streamplot_from_annotations(
            obs,
            group_key=group_key,
            pseudotime_key=pseudotime_key,
            trunk_groups=trunk_groups,
            branch_groups=branch_groups,
            labels=labels,
            branch_center=branch_center,
            branch_steepness=branch_steepness,
            branch_power=branch_power,
            branch_amplitude=branch_amplitude,
            n_branches=n_branches,
            bw=bw,
            pad=pad,
            count_power=count_power,
            normalize_pseudotime=normalize_pseudotime,
            palette=palette,
            label_positions="auto" if label_positions is None else label_positions,
            label_fontsize=label_fontsize,
            figsize=figsize,
            xlim=xlim,
            ylim=ylim,
            xlabel=xlabel,
            xticks=xticks,
            axis_y=axis_y,
            axis_arrowprops=axis_arrowprops,
            scale_to=scale_to,
            min_visible_width=min_visible_width,
            label_fontweight=label_fontweight,
            label_outline_width=label_outline_width,
            label_outline_alpha=label_outline_alpha,
            tick_labelsize=tick_labelsize,
            xlabel_fontsize=xlabel_fontsize,
            ax=ax,
            show=show,
            save=save,
            save_pdf=save_pdf,
        )

    x = np.asarray(x, dtype=float)
    if x.ndim != 1:
        raise ValueError("`x` must be a one-dimensional pseudotime grid.")
    if not branches:
        raise ValueError("`branches` must contain at least one branch definition.")

    if xticks is None:
        xticks = np.linspace(0.0, 1.0, 6)

    working_branches = _copy_branches(branches)
    label_position_map = None if label_positions == "auto" else label_positions
    branch_labels = _collect_branch_labels(working_branches, label_positions=label_position_map)
    palette_map = _resolve_branch_palette(branch_labels, palette)

    _scale_branch_widths(working_branches, x, scale_to=scale_to)
    ylim, axis_y = _auto_ylim_and_axis_y(
        x,
        working_branches,
        ylim=ylim,
        axis_y=axis_y,
    )

    created_fig = ax is None
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    for branch in working_branches:
        center = np.asarray(branch["center"], dtype=float)
        if center.shape != x.shape:
            raise ValueError("Each branch centerline must have the same shape as `x`.")
        for _, width in branch["layers"]:
            if np.asarray(width, dtype=float).shape != x.shape:
                raise ValueError("Each branch ribbon width must have the same shape as `x`.")
        _stack_branch(
            ax,
            x,
            center,
            branch["layers"],
            palette_map,
            min_visible_width=min_visible_width,
        )

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_yticks([])
    ax.set_xticks(xticks)
    ax.tick_params(axis="x", labelsize=tick_labelsize, length=0)
    ax.set_xlabel(xlabel, fontsize=xlabel_fontsize)

    for side in ["left", "right", "top", "bottom"]:
        ax.spines[side].set_visible(False)

    if axis_y is not None:
        arrowprops = {"arrowstyle": "->", "lw": 2.0, "color": "black"}
        if axis_arrowprops is not None:
            arrowprops.update(axis_arrowprops)
        ax.annotate(
            "",
            xy=(xlim[1] - 0.01, axis_y),
            xytext=(xlim[0] + 0.01, axis_y),
            arrowprops=arrowprops,
            annotation_clip=False,
            zorder=10,
        )

    if label_positions == "auto":
        label_positions = _auto_branch_label_positions(x, working_branches)
    if isinstance(label_positions, str):
        raise ValueError("`label_positions` must be a mapping, 'auto', or None.")
    if label_positions is not None:
        for label, (lx, ly, fontsize) in label_positions.items():
            text = ax.text(
                lx,
                ly,
                label,
                color=palette_map[label],
                fontsize=fontsize,
                fontweight=label_fontweight,
                ha="center",
                va="center",
                zorder=11,
            )
            text.set_path_effects(
                [pe.withStroke(linewidth=label_outline_width, foreground="white", alpha=label_outline_alpha)]
            )

    if created_fig:
        fig.tight_layout()
    if save is not None:
        fig.savefig(Path(save), dpi=300, bbox_inches="tight")
    if save_pdf is not None:
        fig.savefig(Path(save_pdf), dpi=300, bbox_inches="tight")
    if show:
        plt.show()

    return fig, ax
