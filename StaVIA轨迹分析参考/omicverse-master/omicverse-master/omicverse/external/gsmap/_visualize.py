from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
from scipy.spatial import KDTree


def load_ldsc(ldsc_input_file):
    """Load spatial-LDSC results and append -log10(p)."""

    ldsc = pd.read_csv(
        ldsc_input_file,
        compression="gzip",
        dtype={"spot": str, "p": float},
        index_col="spot",
        usecols=["spot", "p"],
    )
    ldsc["logp"] = -np.log10(ldsc.p)
    return ldsc


def load_st_coord(adata, feature_series: pd.Series, annotation):
    """Join spatial coordinates with one feature series and optional annotations."""

    if "spatial" not in adata.obsm:
        raise ValueError("spatial coordinates are not found in adata.obsm")

    spot_name = adata.obs_names.to_list()
    space_coord = adata.obsm["spatial"]
    if isinstance(space_coord, np.ndarray):
        space_coord = pd.DataFrame(space_coord, columns=["sx", "sy"], index=spot_name)
    else:
        space_coord = pd.DataFrame(space_coord.values, columns=["sx", "sy"], index=spot_name)

    feature_series = feature_series.loc[feature_series.index.intersection(space_coord.index)]
    space_coord_concat = pd.concat([space_coord.loc[feature_series.index], feature_series], axis=1)

    if annotation is not None:
        annotation_series = pd.Series(
            adata.obs[annotation].values,
            index=adata.obs_names,
            name="annotation",
        )
        space_coord_concat = pd.concat([space_coord_concat, annotation_series], axis=1)

    return space_coord_concat


def estimate_point_size_for_plot(coordinates, default_pixel_width=1000):
    """Estimate plot dimensions and point size from spatial coordinates."""

    tree = KDTree(coordinates)
    distances, _ = tree.query(coordinates, k=2)
    avg_min_distance = np.mean(distances[:, 1])
    width = np.max(coordinates[:, 0]) - np.min(coordinates[:, 0])
    height = np.max(coordinates[:, 1]) - np.min(coordinates[:, 1])

    scale_factor = default_pixel_width / max(width, height)
    pixel_width = width * scale_factor
    pixel_height = height * scale_factor
    point_size = np.ceil(avg_min_distance * scale_factor)
    return (pixel_width, pixel_height), point_size


def draw_scatter(
    space_coord_concat,
    title=None,
    fig_style="light",
    point_size=None,
    width=800,
    height=600,
    annotation=None,
    color_by="logp",
):
    """Draw a gsMap-style spatial scatter plot."""

    px.defaults.template = "plotly_dark" if fig_style == "dark" else "plotly_white"

    custom_color_scale = [
        (1, "#d73027"),
        (7 / 8, "#f46d43"),
        (6 / 8, "#fdae61"),
        (5 / 8, "#fee090"),
        (4 / 8, "#e0f3f8"),
        (3 / 8, "#abd9e9"),
        (2 / 8, "#74add1"),
        (1 / 8, "#4575b4"),
        (0, "#313695"),
    ]
    custom_color_scale.reverse()

    fig = px.scatter(
        space_coord_concat,
        x="sx",
        y="sy",
        color=color_by,
        symbol="annotation" if annotation is not None else None,
        title=title,
        color_continuous_scale=custom_color_scale,
        range_color=[0, max(space_coord_concat[color_by])],
    )

    if point_size is not None:
        fig.update_traces(marker=dict(size=point_size, symbol="circle"))

    fig.update_layout(
        autosize=False,
        width=width,
        height=height,
        legend=dict(yanchor="top", y=0.95, xanchor="left", x=1.0, font=dict(size=10)),
        coloraxis_colorbar=dict(
            orientation="h",
            x=0.5,
            y=-0.0,
            xanchor="center",
            yanchor="top",
            len=0.75,
            title=dict(text="-log10(p)" if color_by == "logp" else color_by, side="top"),
        ),
        margin=dict(l=0, r=0, t=20, b=10),
        title=dict(y=0.98, x=0.5, xanchor="center", yanchor="top", font=dict(size=20)),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        title=None,
        scaleanchor="y",
    )
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, title=None)
    fig.update_layout(height=width)
    return fig
