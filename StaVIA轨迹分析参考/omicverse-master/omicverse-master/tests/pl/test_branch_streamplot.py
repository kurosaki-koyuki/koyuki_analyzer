"""Tests for branch-aware pseudotime stream plots."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import omicverse as ov
from omicverse.pl._branch_streamplot import compute_group_kde_profiles, make_branch_centerline, tapered_kde


def test_compute_group_kde_profiles_respects_categorical_order():
    obs = pd.DataFrame(
        {
            "state": pd.Categorical(["late", "early", "mid", "early", "late"], categories=["early", "mid", "late"]),
            "pt": [0.8, 0.1, 0.5, 0.2, 0.9],
        }
    )
    x, profiles = compute_group_kde_profiles(obs, group_key="state", pseudotime_key="pt")
    assert np.isclose(x[0], 0.0)
    assert list(profiles.keys()) == ["early", "mid", "late"]


def test_compute_group_kde_profiles_handles_tied_pseudotime():
    obs = pd.DataFrame(
        {
            "state": ["tied", "tied", "tied", "tied", "spread", "spread", "spread"],
            "pt": [0.5, 0.5, 0.5, 0.5, 0.2, 0.35, 0.55],
        }
    )
    x, profiles = compute_group_kde_profiles(obs, group_key="state", pseudotime_key="pt")
    assert np.isclose(x[0], 0.0)
    assert np.allclose(profiles["tied"], 0.0)
    assert profiles["spread"].max() > 0.0


def test_compute_group_kde_profiles_auto_normalizes_monocle_scale():
    obs = pd.DataFrame(
        {
            "state": ["early"] * 5 + ["late"] * 5,
            "pt": [2, 5, 8, 11, 14, 75, 82, 90, 96, 110],
        }
    )
    x, profiles = compute_group_kde_profiles(obs, group_key="state", pseudotime_key="pt")
    assert np.isclose(x[0], 0.0)
    assert np.isclose(x[-1], 1.0)
    assert profiles["early"].max() > 0.0
    assert profiles["late"].max() > 0.0
    assert x[profiles["early"].argmax()] < x[profiles["late"].argmax()]


def test_tapered_kde_uses_x_range_for_non_normalized_pseudotime():
    x = np.linspace(0.0, 10.0, 200)
    values = np.array([7.8, 8.0, 8.2, 8.4, 8.6])
    profile = tapered_kde(values, x)
    assert profile.max() > 0.0
    assert x[profile.argmax()] > 7.0


def test_branch_streamplot_uses_ov_palette_defaults():
    x = np.linspace(0.0, 1.0, 128)
    branches = [
        {
            "center": np.zeros_like(x),
            "layers": [
                ("A", np.exp(-((x - 0.2) ** 2) / 0.01)),
                ("B", np.exp(-((x - 0.45) ** 2) / 0.015)),
            ],
        },
        {
            "center": make_branch_centerline(x, amplitude=0.35, center=0.55, steepness=10.0),
            "layers": [("C", np.exp(-((x - 0.75) ** 2) / 0.02))],
        },
    ]
    fig, ax = ov.pl.branch_streamplot(
        x,
        branches,
        label_positions={"A": (0.18, 0.02, 12), "C": (0.78, 0.3, 12)},
        show=False,
    )
    assert fig is not None
    assert ax.get_xlabel() == "Pseudotime"
    assert len(ax.collections) > 0
    plt.close(fig)


def test_branch_streamplot_can_save_outputs(tmp_path):
    x = np.linspace(0.0, 1.0, 100)
    lower = make_branch_centerline(x, amplitude=-0.25, center=0.55, steepness=10.0)
    widths = np.exp(-((x - 0.65) ** 2) / 0.03)
    out_png = tmp_path / "branch_streamplot.png"
    out_pdf = tmp_path / "branch_streamplot.pdf"
    fig, ax = ov.pl.branch_streamplot(
        x,
        [{"center": lower, "layers": [("A", widths), ("B", widths * 0.6)]}],
        save=out_png,
        save_pdf=out_pdf,
        show=False,
    )
    assert out_png.exists()
    assert out_pdf.exists()
    assert ax is not None
    plt.close(fig)


def test_branch_streamplot_builds_common_branch_layout_from_annotations():
    obs = pd.DataFrame(
        {
            "state": pd.Categorical(
                ["early"] * 8 + ["mid"] * 8 + ["upper"] * 8 + ["lower"] * 8,
                categories=["early", "mid", "upper", "lower"],
                ordered=True,
            ),
            "pt": np.r_[
                np.linspace(0.02, 0.25, 8),
                np.linspace(0.25, 0.55, 8),
                np.linspace(0.58, 0.95, 8),
                np.linspace(0.60, 0.98, 8),
            ],
        }
    )
    fig, ax = ov.pl.branch_streamplot(
        obs,
        group_key="state",
        pseudotime_key="pt",
        trunk_groups=["early", "mid"],
        branch_groups={"upper": 0.25, "lower": -0.25},
        scale_to=0.2,
        show=False,
    )
    assert fig is not None
    assert len(ax.collections) > 0
    labels = {text.get_text() for text in ax.texts if text.get_text()}
    assert labels == {"early", "mid", "upper", "lower"}
    plt.close(fig)


def test_branch_streamplot_can_infer_layout_from_annotations():
    obs = pd.DataFrame(
        {
            "state": pd.Categorical(
                ["early"] * 8 + ["mid"] * 8 + ["upper"] * 8 + ["lower"] * 8,
                categories=["early", "mid", "upper", "lower"],
                ordered=True,
            ),
            "pt": np.r_[
                np.linspace(0.02, 0.25, 8),
                np.linspace(0.25, 0.50, 8),
                np.linspace(0.65, 0.95, 8),
                np.linspace(0.68, 0.98, 8),
            ],
        }
    )
    fig, ax = ov.pl.branch_streamplot(
        obs,
        group_key="state",
        pseudotime_key="pt",
        scale_to=0.2,
        show=False,
    )
    assert fig is not None
    assert len(ax.collections) > 0
    labels = {text.get_text() for text in ax.texts if text.get_text()}
    assert labels == {"early", "mid", "upper", "lower"}
    plt.close(fig)


def test_branch_streamplot_accepts_obs_dataframe_directly():
    obs = pd.DataFrame(
        {
            "state": pd.Categorical(
                ["early"] * 6 + ["late"] * 6,
                categories=["early", "late"],
                ordered=True,
            ),
            "pt": np.r_[np.linspace(0.05, 0.35, 6), np.linspace(0.65, 0.95, 6)],
        }
    )
    fig, ax = ov.pl.branch_streamplot(
        obs,
        group_key="state",
        pseudotime_key="pt",
        show=False,
    )
    assert fig is not None
    assert len(ax.collections) > 0
    plt.close(fig)


def test_branch_streamplot_auto_scales_annotation_layout():
    obs = pd.DataFrame(
        {
            "state": pd.Categorical(
                ["early"] * 10 + ["mid"] * 10 + ["late"] * 10,
                categories=["early", "mid", "late"],
                ordered=True,
            ),
            "pt": np.r_[
                np.linspace(0.02, 0.25, 10),
                np.linspace(0.35, 0.60, 10),
                np.linspace(0.70, 0.98, 10),
            ],
        }
    )
    fig, ax = ov.pl.branch_streamplot(
        obs,
        group_key="state",
        pseudotime_key="pt",
        show=False,
    )
    y_min, y_max = ax.get_ylim()
    assert y_max - y_min < 2.0
    assert ax.get_xlabel() == "Pseudotime"
    plt.close(fig)


def test_branch_streamplot_accepts_anndata_like_object_and_palette():
    obs = pd.DataFrame(
        {
            "state": pd.Categorical(
                ["early"] * 6 + ["late"] * 6,
                categories=["early", "late"],
                ordered=True,
            ),
            "pt": np.r_[np.linspace(0.05, 0.35, 6), np.linspace(0.65, 0.95, 6)],
        }
    )

    class MiniAnnData:
        def __init__(self, obs):
            self.obs = obs
            self.uns = {"state_colors": ["#111111", "#222222"]}

    fig, ax = ov.pl.branch_streamplot(
        MiniAnnData(obs),
        group_key="state",
        pseudotime_key="pt",
        show=False,
    )
    assert fig is not None
    facecolors = ax.collections[0].get_facecolors()
    assert len(facecolors) > 0
    plt.close(fig)
