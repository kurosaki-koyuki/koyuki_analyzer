from __future__ import annotations

import warnings
from math import ceil
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .._registry import register_function
from .._settings import Colors, EMOJI


def _normalize_gene_list(genes, fitted) -> list[str]:
    available = list(dict.fromkeys(fitted["gene"].astype(str)))
    if genes is None:
        return available
    if isinstance(genes, str):
        genes = [genes]
    genes = [str(gene) for gene in genes]
    missing = [gene for gene in genes if gene not in available]
    if missing:
        raise KeyError(f"Genes not present in fitted trend table: {missing}.")
    return genes


def _default_colors() -> list[str]:
    colors = plt.rcParams["axes.prop_cycle"].by_key().get("color", [])
    if not colors:
        colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"]
    return list(colors)


def _resolve_palette(labels: Sequence[str], palette=None) -> dict[str, str]:
    if palette is None:
        if len(labels) == 1:
            return {labels[0]: "#3C5488"}
        colors = _default_colors()
        return {label: colors[i % len(colors)] for i, label in enumerate(labels)}
    if isinstance(palette, str):
        cmap = plt.get_cmap(palette)
        if len(labels) == 1:
            return {labels[0]: cmap(0.6)}
        return {label: cmap(i / max(len(labels) - 1, 1)) for i, label in enumerate(labels)}
    if isinstance(palette, dict):
        return {label: palette[label] for label in labels}
    palette = list(palette)
    return {label: palette[i % len(palette)] for i, label in enumerate(labels)}


def _resolve_linestyles(labels: Sequence[str], linestyles=None) -> dict[str, str]:
    if linestyles is None:
        base = ["-", "--", ":", "-."]
        return {label: base[i % len(base)] for i, label in enumerate(labels)}
    if isinstance(linestyles, dict):
        return {label: linestyles[label] for label in labels}
    linestyles = list(linestyles)
    return {label: linestyles[i % len(linestyles)] for i, label in enumerate(labels)}


def _resolve_named_plot_value(value, *keys):
    if not isinstance(value, dict):
        return value
    normalized = {}
    for key, item in value.items():
        normalized[str(key)] = item
    for key in keys:
        if key is None:
            continue
        key = str(key)
        if key in normalized:
            return normalized[key]
    return normalized.get("default")


def _series_label(group_name: str, gene_name: str, compare_features: bool, compare_groups: bool) -> str:
    if compare_features and compare_groups:
        return f"{group_name} | {gene_name}"
    if compare_features:
        return gene_name
    return group_name


def _default_panel_title(
    panel_mode: str,
    panel_label: str,
    *,
    gene_list: Sequence[str],
    group_list: Sequence[str],
    compare_features: bool,
    compare_groups: bool,
):
    if panel_mode == "groups":
        if compare_features and len(gene_list) > 1 and len(group_list) == 1:
            return ""
        return panel_label
    return panel_label


def _draw_legend(
    axis,
    *,
    legend: bool,
    legend_outside: bool,
    legend_loc: str | int | None,
    legend_bbox_to_anchor: tuple | None,
    legend_fontsize: float | str | None,
    legend_ncol: int,
):
    if not legend:
        return False, False
    handles, labels = axis.get_legend_handles_labels()
    if not labels:
        return False, False
    dedup = dict(zip(labels, handles))
    outside_layout = False

    if legend_loc is None:
        if legend_outside:
            legend_loc = "center left"
            legend_bbox_to_anchor = (1.02, 0.5) if legend_bbox_to_anchor is None else legend_bbox_to_anchor
            outside_layout = True
        else:
            legend_loc = "best"
    elif isinstance(legend_loc, str) and legend_loc in {"right margin", "right"}:
        legend_loc = "center left"
        legend_bbox_to_anchor = (1.02, 0.5) if legend_bbox_to_anchor is None else legend_bbox_to_anchor
        outside_layout = True
    elif legend_bbox_to_anchor is not None:
        outside_layout = True

    legend_kwargs = {
        "frameon": False,
        "loc": legend_loc,
        "ncol": legend_ncol,
    }
    if legend_bbox_to_anchor is not None:
        legend_kwargs["bbox_to_anchor"] = legend_bbox_to_anchor
        legend_kwargs["borderaxespad"] = 0.0
    if legend_fontsize is not None:
        legend_kwargs["fontsize"] = legend_fontsize

    axis.legend(dedup.values(), dedup.keys(), **legend_kwargs)
    return True, outside_layout


def _is_categorical(values: pd.Series) -> bool:
    return isinstance(values.dtype, pd.CategoricalDtype) or \
        pd.api.types.is_object_dtype(values.dtype) or \
        pd.api.types.is_string_dtype(values.dtype) or \
        pd.api.types.is_bool_dtype(values.dtype)


@register_function(
    aliases=["dynamic_trends", "plot_gam_trends", "动态趋势图", "gam趋势图"],
    category="pl",
    description="Plot fitted pseudotime GAM trends from `ov.single.dynamic_features` for one or multiple genes across datasets.",
    examples=[
        "res = ov.single.dynamic_features({'A': adata_a, 'B': adata_b}, genes=['tbxta'], pseudotime='palantir_pseudotime')",
        "ov.pl.dynamic_trends(res, genes='tbxta', figsize=(2, 2))",
    ],
    related=["single.dynamic_features", "pl.dynamic_heatmap"],
)
def dynamic_trends(
    result,
    genes=None,
    *,
    groups=None,
    datasets=None,
    compare_features: bool = False,
    compare_groups: bool = False,
    add_line: bool = True,
    add_interval: bool = True,
    add_point: bool = False,
    point_color_by: str | None = None,
    point_palette=None,
    split_time: float | dict[str, float] | None = None,
    shared_trunk: bool = False,
    trunk_color: str = "#3C5488",
    trunk_alpha: float = 0.25,
    trunk_linewidth: float | None = None,
    line_palette=None,
    line_palcolor=None,
    line_style_by: str | None = None,
    line_styles=None,
    figsize: tuple = (3, 3),
    nrows: int | None = None,
    ncols: int | None = None,
    scatter_size: float = 8,
    scatter_alpha: float = 0.2,
    linewidth: float = 2.0,
    legend: bool = True,
    legend_outside: bool = True,
    legend_loc: str | int | None = None,
    legend_bbox_to_anchor: tuple | None = None,
    legend_fontsize: float | str | None = None,
    legend_ncol: int = 1,
    sharey: bool = False,
    xlabel: str = "Pseudotime",
    ylabel: str = "Expression",
    title=None,
    title_fontsize: float | None = None,
    add_grid: bool = True,
    grid_alpha: float = 0.3,
    grid_linewidth: float = 0.6,
    show: bool | None = None,
    return_axes: bool = False,
    return_fig: bool = False,
    ax=None,
    verbose: bool = True,
):
    """Plot GAM-fitted pseudotime trends for one or more genes.

    Parameters
    ----------
    result
        Result returned by :func:`ov.single.dynamic_features`.
    genes
        Gene name or list of gene names to plot. When ``None``, all fitted
        genes available in ``result`` are shown.
    groups
        Optional fitted group names to include when ``result`` contains
        multiple lineages, cell types, or conditions.
    datasets
        Backward-compatible alias of ``groups``. Prefer ``groups`` in new
        code.
    compare_features
        Whether to compare multiple selected features on the same panel. When
        enabled for a single fitted group, the default panel title is left
        blank to avoid generic titles such as ``adata``.
    compare_groups
        Whether to compare multiple fitted groups on the same panel. Groups are
        the fitted series labels returned by :func:`ov.single.dynamic_features`,
        for example lineages, cell types, or condition names.
    add_line
        Whether to draw the fitted GAM trend lines.
    add_interval
        Whether to draw confidence interval ribbons when available.
    add_point
        Whether to overlay observed expression values. This requires that
        ``result`` was computed with :func:`ov.single.dynamic_features` using
        ``store_raw=True``.
    point_color_by
        Optional column in the stored raw point table used to color observed
        points independently from the fitted line colors. This enables views
        such as a single global trend line with points colored by ``State`` or
        ``subtype``. Requires ``add_point=True`` and
        ``ov.single.dynamic_features(..., store_raw=True, raw_obs_keys=[...])``.
    point_palette
        Optional palette used when ``point_color_by`` is categorical.
    split_time
        Optional pseudotime position used to render branch-aware comparisons.
        When provided together with ``compare_groups=True``, each group trend
        is clipped to ``pseudotime >= split_time``. This can be supplied as a
        scalar applied to every panel, or as a mapping keyed by gene / panel
        name with an optional ``'default'`` fallback.
    shared_trunk
        Whether to draw a shared pre-split trunk when ``split_time`` is
        provided. The trunk is computed as the mean fitted curve across the
        compared groups for each gene before the split point, giving a generic
        branch-aware view that can be reused across Monocle, Slingshot,
        Palantir, CellRank, and other trajectory methods.
    trunk_color
        Color used for the shared trunk line when ``shared_trunk=True`` and a
        single feature is shown on a panel.
    trunk_alpha
        Alpha transparency used for the shared trunk confidence ribbon.
    trunk_linewidth
        Optional line width used for the shared trunk. Defaults to
        ``linewidth`` when unset.
    line_palette
        Optional named matplotlib colormap or palette-like sequence describing
        line colors.
    line_palcolor
        Explicit color mapping or sequence overriding ``line_palette``.
    line_style_by
        Optional semantic used to vary line styles when a comparison panel
        contains multiple series. Choose from ``'features'`` or ``'groups'``.
    line_styles
        Optional line-style mapping or sequence used with ``line_style_by``.
    figsize
        Size of each panel in inches. For multi-gene plots this is interpreted
        as the per-panel size before tiling.
    nrows
        Number of subplot rows for multi-panel layouts.
    ncols
        Number of subplot columns for multi-gene layouts.
    scatter_size
        Marker size used for observed points when ``add_point=True``.
    scatter_alpha
        Alpha transparency for observed points when ``add_point=True``.
    linewidth
        Line width for fitted trend curves.
    legend
        Whether to draw a legend on each axis.
    legend_outside
        Whether to place the legend outside the plotting area on the right.
        Kept for backward compatibility; prefer ``legend_loc`` in new code.
    legend_loc
        Legend location. Use ``'right margin'`` for the Scanpy/OmicVerse-style
        outside-right legend, or any Matplotlib legend location such as
        ``'best'`` or ``'upper center'``.
    legend_bbox_to_anchor
        Optional Matplotlib ``bbox_to_anchor`` used together with
        ``legend_loc`` for precise placement.
    legend_fontsize
        Optional legend font size.
    legend_ncol
        Number of legend columns.
    sharey
        Whether subplots should share the y-axis in multi-gene layouts.
    xlabel
        Label used for the x-axis.
    ylabel
        Label used for the y-axis.
    title
        Optional title applied to the plotted axis or axes. Pass a list/tuple
        to specify per-panel titles in multi-panel layouts. By default, panel
        titles use the plotted gene or group label automatically. Pass ``''``
        to hide titles explicitly.
    title_fontsize
        Font size used for panel or figure titles. When ``None``, matplotlib's
        default title size is used.
    add_grid
        Whether to draw a light background grid.
    grid_alpha
        Alpha transparency used for the background grid.
    grid_linewidth
        Line width used for the background grid.
    show
        Whether to call ``plt.show()`` before returning. By default, plots are
        shown only when neither ``return_fig`` nor ``return_axes`` is requested.
    return_axes
        Whether to return the created axis or axes. When ``False`` and
        ``return_fig=False``, the function returns ``None`` to avoid notebook
        repr noise.
    return_fig
        Whether to return the figure together with the created axes.
    ax
        Existing matplotlib axis used when plotting a single gene.
    verbose
        Whether to print a short plotting summary.

    Returns
    -------
    None | matplotlib.axes.Axes | list[matplotlib.axes.Axes] | tuple
        Returns ``None`` by default after drawing so notebook cells do not
        print raw axis representations. When ``return_axes=True``, returns the
        created axis or axes. When ``return_fig=True``, returns
        ``(figure, axes)``.
    """
    if not hasattr(result, "fitted"):
        raise TypeError("`result` must be the output of `ov.single.dynamic_features`.")

    groups = groups if groups is not None else datasets
    fitted = result.get_fitted(genes=genes, datasets=groups)
    if fitted.empty:
        raise ValueError("No fitted trends remained after filtering.")

    gene_list = _normalize_gene_list(genes, fitted)
    group_list = list(dict.fromkeys(fitted["dataset"].astype(str)))
    if verbose:
        print(f"\n{Colors.HEADER}{Colors.BOLD}{EMOJI['start']} Dynamic trend plotting:{Colors.ENDC}")
        print(f"   {Colors.CYAN}Features: {Colors.BOLD}{len(gene_list)}{Colors.ENDC}{Colors.CYAN} | Groups: {Colors.BOLD}{len(group_list)}{Colors.ENDC}")
        print(f"   {Colors.CYAN}compare_features={Colors.BOLD}{compare_features}{Colors.ENDC}{Colors.CYAN} | compare_groups={Colors.BOLD}{compare_groups}{Colors.ENDC}")
    if line_palcolor is None:
        line_palcolor = line_palette
    compare_groups = bool(compare_groups and len(group_list) > 1)

    raw = result.get_raw(genes=gene_list, datasets=groups) if add_point and hasattr(result, "get_raw") else None
    if add_point and raw is None:
        raise ValueError("`add_point=True` requires `ov.single.dynamic_features(..., store_raw=True)`.")
    if point_color_by is not None and not add_point:
        raise ValueError("`point_color_by` requires `add_point=True`.")
    if point_color_by is not None:
        if raw is None or point_color_by not in raw.columns:
            raise KeyError(
                f"`point_color_by={point_color_by!r}` was not found in the stored raw table. "
                "Re-run `ov.single.dynamic_features(..., store_raw=True, raw_obs_keys=[...])`."
            )
        point_values = raw[point_color_by]
        if not _is_categorical(point_values):
            raise ValueError("`point_color_by` currently supports categorical raw obs columns only.")
        point_labels = list(dict.fromkeys(point_values.dropna().astype(str)))
        # Prefer the captured scanpy palette
        # (``adata.uns[f'{point_color_by}_colors']``) if
        # ``dynamic_features(..., store_raw=True)`` recorded it AND the
        # user didn't pass an explicit ``point_palette``.
        captured = (result.config or {}).get("raw_obs_colors", {}) if hasattr(result, "config") else {}
        captured_order = (result.config or {}).get("raw_obs_category_order", {}) if hasattr(result, "config") else {}
        if point_palette is None and point_color_by in captured:
            colors = captured[point_color_by]
            order = captured_order.get(point_color_by, [])
            color_by_name = {c: colors[i] for i, c in enumerate(order) if i < len(colors)}
            point_color_map = {lbl: color_by_name.get(lbl, "#888888") for lbl in point_labels}
        else:
            point_color_map = _resolve_palette(point_labels, palette=point_palette)
    else:
        point_labels = []
        point_color_map = {}

    if line_style_by not in {None, "features", "groups"}:
        raise ValueError("`line_style_by` must be one of {None, 'features', 'groups'}.")
    if split_time is not None and not compare_groups:
        raise ValueError("`split_time` requires `compare_groups=True` so that branch-specific trends can be compared.")

    if compare_features and compare_groups:
        panel_mode = "combined"
        panel_labels = ["combined"]
    elif compare_features:
        panel_mode = "groups"
        panel_labels = group_list
    else:
        panel_mode = "features"
        panel_labels = gene_list

    if panel_mode == "combined":
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure
        axes = [ax]
    elif len(panel_labels) == 1:
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure
        axes = [ax]
    else:
        if nrows is None and ncols is None:
            ncols = min(3, len(panel_labels))
            nrows = int(ceil(len(panel_labels) / ncols))
        elif nrows is None:
            ncols = int(ncols)
            nrows = int(ceil(len(panel_labels) / ncols))
        elif ncols is None:
            nrows = int(nrows)
            ncols = int(ceil(len(panel_labels) / nrows))
        else:
            nrows = int(nrows)
            ncols = int(ncols)
            if nrows * ncols < len(panel_labels):
                raise ValueError("`nrows * ncols` must be large enough for the requested panels.")
        panel_width, panel_height = figsize
        fig, axes_arr = plt.subplots(
            nrows=nrows,
            ncols=ncols,
            figsize=(panel_width * ncols, panel_height * nrows),
            sharey=sharey,
        )
        axes = list(np.ravel(axes_arr))

    if panel_mode == "combined":
        color_labels = group_list if compare_groups else gene_list
        if line_style_by is None and compare_groups and len(gene_list) > 1:
            line_style_by = "features"
    elif panel_mode == "groups":
        color_labels = gene_list
    else:
        color_labels = group_list

    # Line palette: if the caller didn't pass an explicit
    # ``line_palcolor`` AND the labels correspond to groups for which
    # ``dynamic_features`` captured a scanpy palette
    # (``adata.uns[f'{groupby}_colors']``), use that — keeps the
    # per-lineage curves consistent with the cluster colour scheme.
    captured_lines = (result.config or {}).get("raw_obs_colors", {}) if hasattr(result, "config") else {}
    captured_order_lines = (result.config or {}).get("raw_obs_category_order", {}) if hasattr(result, "config") else {}
    groupby_used = (result.config or {}).get("groupby") if hasattr(result, "config") else None
    if (
        line_palcolor is None
        and color_labels is group_list
        and groupby_used is not None
        and groupby_used in captured_lines
    ):
        cols_line = captured_lines[groupby_used]
        ord_line = captured_order_lines.get(groupby_used, [])
        by_name = {c: cols_line[i] for i, c in enumerate(ord_line) if i < len(cols_line)}
        color_map = {lbl: by_name.get(lbl, "#888888") for lbl in color_labels}
    else:
        color_map = _resolve_palette(color_labels, palette=line_palcolor)
    if line_style_by == "groups":
        style_map = _resolve_linestyles(group_list, linestyles=line_styles)
    elif line_style_by == "features":
        style_map = _resolve_linestyles(gene_list, linestyles=line_styles)
    else:
        style_map = {}

    legend_drawn = False
    legend_uses_outside_layout = False

    for idx, panel_label in enumerate(panel_labels):
        axis = axes[0] if panel_mode == "combined" else axes[idx]
        if panel_mode == "combined":
            panel_genes = gene_list
            panel_groups = group_list
        elif panel_mode == "groups":
            panel_genes = gene_list
            panel_groups = [panel_label]
        else:
            panel_genes = [panel_label]
            panel_groups = group_list

        for gene in panel_genes:
            gene_fitted = fitted[fitted["gene"].astype(str) == gene]
            gene_raw = None if raw is None else raw[raw["gene"].astype(str) == gene]
            panel_split_time = _resolve_named_plot_value(split_time, gene, panel_label)
            if panel_split_time is not None:
                panel_split_time = float(panel_split_time)
            branch_mode = compare_groups and panel_split_time is not None

            if shared_trunk and branch_mode and add_line:
                trunk_parts = []
                for group_name in panel_groups:
                    trunk_fit = gene_fitted[
                        gene_fitted["dataset"].astype(str) == group_name
                    ].sort_values("pseudotime")
                    trunk_fit = trunk_fit[trunk_fit["pseudotime"] <= panel_split_time]
                    if not trunk_fit.empty:
                        trunk_parts.append(
                            trunk_fit[["pseudotime", "fitted", "lower", "upper"]].copy()
                        )
                if trunk_parts:
                    trunk_df = pd.concat(trunk_parts, ignore_index=True)
                    trunk_curve = (
                        trunk_df.groupby("pseudotime", sort=True)[
                            ["fitted", "lower", "upper"]
                        ]
                        .mean(numeric_only=True)
                        .reset_index()
                    )
                    trunk_label = (
                        f"trunk | {gene}"
                        if compare_features and len(panel_genes) > 1
                        else "trunk"
                    )
                    panel_trunk_color = (
                        color_map[gene]
                        if compare_features and len(panel_genes) > 1
                        else trunk_color
                    )
                    axis.plot(
                        trunk_curve["pseudotime"],
                        trunk_curve["fitted"],
                        color=panel_trunk_color,
                        linewidth=linewidth if trunk_linewidth is None else trunk_linewidth,
                        linestyle="-",
                        label=trunk_label,
                    )
                    if (
                        add_interval
                        and trunk_curve["lower"].notna().any()
                        and trunk_curve["upper"].notna().any()
                    ):
                        axis.fill_between(
                            trunk_curve["pseudotime"].to_numpy(dtype=float),
                            trunk_curve["lower"].to_numpy(dtype=float),
                            trunk_curve["upper"].to_numpy(dtype=float),
                            color=panel_trunk_color,
                            alpha=trunk_alpha,
                        )

            for group_name in panel_groups:
                dataset_fit = gene_fitted[gene_fitted["dataset"].astype(str) == group_name].sort_values("pseudotime")
                if dataset_fit.empty:
                    continue
                if branch_mode:
                    dataset_fit = dataset_fit[dataset_fit["pseudotime"] >= panel_split_time]
                    if dataset_fit.empty:
                        continue
                if panel_mode == "combined":
                    color = color_map[group_name] if compare_groups else color_map[gene]
                elif panel_mode == "groups":
                    color = color_map[gene]
                else:
                    color = color_map[group_name]

                if line_style_by == "groups":
                    linestyle = style_map[group_name]
                elif line_style_by == "features":
                    linestyle = style_map[gene]
                else:
                    linestyle = "-"

                label = _series_label(group_name, gene, compare_features, compare_groups)
                if panel_mode == "groups" and not compare_groups:
                    label = gene
                elif panel_mode == "features" and not compare_features:
                    label = group_name
                if point_color_by is not None and len(group_list) == 1 and not compare_features and not compare_groups:
                    label = "_nolegend_"

                if add_point and gene_raw is not None:
                    dataset_raw = gene_raw[gene_raw["dataset"].astype(str) == group_name]
                    if not dataset_raw.empty:
                        if branch_mode:
                            dataset_raw = dataset_raw[dataset_raw["pseudotime"] >= panel_split_time]
                        if dataset_raw.empty:
                            pass
                        elif point_color_by is None:
                            axis.scatter(
                                dataset_raw["pseudotime"],
                                dataset_raw["expression"],
                                s=scatter_size,
                                alpha=scatter_alpha,
                                color=color,
                                linewidths=0,
                            )
                        else:
                            # Suppress per-point legend entries when lines
                            # are providing the legend (compare_groups or
                            # compare_features). Otherwise the legend would
                            # mix line groups + every point category, which
                            # the lines already cover semantically.
                            suppress_point_legend = add_line and (
                                compare_groups or compare_features
                            )
                            point_series = dataset_raw[point_color_by]
                            for point_label in list(dict.fromkeys(point_series.dropna().astype(str))):
                                point_mask = point_series.astype(str).to_numpy() == point_label
                                if not np.any(point_mask):
                                    continue
                                axis.scatter(
                                    dataset_raw.loc[point_mask, "pseudotime"],
                                    dataset_raw.loc[point_mask, "expression"],
                                    s=scatter_size,
                                    alpha=scatter_alpha,
                                    color=point_color_map[point_label],
                                    linewidths=0,
                                    label="_nolegend_" if suppress_point_legend else point_label,
                                )
                if add_line:
                    axis.plot(
                        dataset_fit["pseudotime"],
                        dataset_fit["fitted"],
                        color=color,
                        linewidth=linewidth,
                        linestyle=linestyle,
                        label=label,
                    )
                if add_interval and dataset_fit["lower"].notna().any() and dataset_fit["upper"].notna().any():
                    axis.fill_between(
                        dataset_fit["pseudotime"].to_numpy(dtype=float),
                        dataset_fit["lower"].to_numpy(dtype=float),
                        dataset_fit["upper"].to_numpy(dtype=float),
                        color=color,
                        alpha=0.2,
                    )

        if panel_mode != "combined":
            if title is None:
                panel_title = _default_panel_title(
                    panel_mode,
                    panel_label,
                    gene_list=gene_list,
                    group_list=group_list,
                    compare_features=compare_features,
                    compare_groups=compare_groups,
                )
            elif isinstance(title, (list, tuple)):
                panel_title = title[idx]
            else:
                panel_title = title
            if title_fontsize is None:
                axis.set_title("" if panel_title is None else str(panel_title))
            else:
                axis.set_title("" if panel_title is None else str(panel_title), fontsize=title_fontsize)
            axis.set_xlabel(xlabel)
            axis.set_ylabel(ylabel)
            axis.grid(add_grid, alpha=grid_alpha, linewidth=grid_linewidth)
            drawn, outside_layout = _draw_legend(
                axis,
                legend=legend,
                legend_outside=legend_outside,
                legend_loc=legend_loc,
                legend_bbox_to_anchor=legend_bbox_to_anchor,
                legend_fontsize=legend_fontsize,
                legend_ncol=legend_ncol,
            )
            legend_drawn = drawn or legend_drawn
            legend_uses_outside_layout = outside_layout or legend_uses_outside_layout

    if panel_mode == "combined":
        axis = axes[0]
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        if title_fontsize is None:
            axis.set_title("" if title is None else str(title))
        else:
            axis.set_title("" if title is None else str(title), fontsize=title_fontsize)
        axis.grid(add_grid, alpha=grid_alpha, linewidth=grid_linewidth)
        drawn, outside_layout = _draw_legend(
            axis,
            legend=legend,
            legend_outside=legend_outside,
            legend_loc=legend_loc,
            legend_bbox_to_anchor=legend_bbox_to_anchor,
            legend_fontsize=legend_fontsize,
            legend_ncol=legend_ncol,
        )
        legend_drawn = drawn or legend_drawn
        legend_uses_outside_layout = outside_layout or legend_uses_outside_layout

    for axis in axes[len(panel_labels):]:
        axis.set_visible(False)

    fig.tight_layout(rect=(0, 0, 0.84, 1) if legend_drawn and legend_uses_outside_layout else None)
    axes_out = axes[0] if panel_mode == "combined" or len(panel_labels) == 1 else axes[: len(panel_labels)]
    if show is None:
        show = not return_fig and not return_axes
    if show:
        backend = plt.get_backend().lower()
        if "agg" in backend:
            fig.canvas.draw()
        else:
            plt.show()
    if return_fig:
        if verbose:
            print(f"{Colors.GREEN}{EMOJI['done']} Dynamic trend plotting completed!{Colors.ENDC}")
        return fig, axes_out
    if return_axes:
        if verbose:
            print(f"{Colors.GREEN}{EMOJI['done']} Dynamic trend plotting completed!{Colors.ENDC}")
        return axes_out
    if verbose:
        print(f"{Colors.GREEN}{EMOJI['done']} Dynamic trend plotting completed!{Colors.ENDC}")
    return None


plot_gam_trends = dynamic_trends
