from __future__ import annotations

import importlib.util
import matplotlib
import numpy as np
import pandas as pd
import sys
import types
from pathlib import Path

matplotlib.use("Agg")


class _FakePerturbResult:
    target = "target_gene"
    mode = "ko"
    backend = "test_backend"

    def __init__(self, transitions: pd.DataFrame):
        self._transitions = transitions

    def cluster_transitions(self, *, adata, cluster_col):
        return self._transitions


def _load_perturbation_module(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    registry = types.ModuleType("omicverse._registry")
    registry.register_function = lambda *args, **kwargs: (lambda func: func)
    monkeypatch.setitem(sys.modules, "omicverse", types.ModuleType("omicverse"))
    monkeypatch.setitem(sys.modules, "omicverse.pl", types.ModuleType("omicverse.pl"))
    monkeypatch.setitem(sys.modules, "omicverse._registry", registry)

    spec = importlib.util.spec_from_file_location(
        "omicverse.pl._perturbation",
        root / "omicverse" / "pl" / "_perturbation.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_perturb_sankey_ribbons_stay_within_destination_bars(monkeypatch):
    _perturbation = _load_perturbation_module(monkeypatch)

    clusters = [f"cluster_{i}" for i in range(7)]
    ct = pd.DataFrame(
        [
            [0.996, 0.000, 0.000, 0.000, 0.004, 0.000, 0.000],
            [0.000, 0.902, 0.046, 0.003, 0.010, 0.039, 0.000],
            [0.000, 0.065, 0.826, 0.059, 0.000, 0.000, 0.050],
            [0.000, 0.004, 0.106, 0.885, 0.000, 0.000, 0.005],
            [0.031, 0.052, 0.000, 0.000, 0.889, 0.028, 0.000],
            [0.000, 0.257, 0.000, 0.000, 0.133, 0.610, 0.000],
            [0.000, 0.000, 0.039, 0.005, 0.000, 0.000, 0.956],
        ],
        index=clusters,
        columns=clusters,
    )
    ribbons = []
    real_make_ribbon = _perturbation._make_sankey_ribbon

    def capture_ribbon(**kwargs):
        ribbons.append(kwargs)
        return real_make_ribbon(**kwargs)

    monkeypatch.setattr(_perturbation, "_make_sankey_ribbon", capture_ribbon)
    fig, _ = _perturbation.perturb_sankey(
        _FakePerturbResult(ct),
        adata=None,
        cluster_col="main_cluster",
        min_flow=0.03,
    )

    n = len(ct.index)
    src_sizes = np.full(n, 1.0 / n, dtype=float)
    expected_right_sizes = (ct.to_numpy(dtype=float) * src_sizes[:, None]).sum(axis=0)
    y_pad = 0.005
    right_tops = np.cumsum(expected_right_sizes + y_pad)
    right_bottoms = right_tops - expected_right_sizes

    assert ribbons
    for ribbon in ribbons:
        j = np.flatnonzero(np.isclose(right_bottoms, ribbon["y0_dst"], atol=1e-12) |
                           ((right_bottoms - 1e-12 <= ribbon["y0_dst"]) &
                            (ribbon["y0_dst"] <= right_tops + 1e-12)))[0]
        assert ribbon["y0_dst"] >= right_bottoms[j] - 1e-12
        assert ribbon["y1_dst"] <= right_tops[j] + 1e-12

    fig.clf()
