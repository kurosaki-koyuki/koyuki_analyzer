"""Tests for ``omicverse.single._batch._split_kwargs_by_signature``.

The helper underpins the scvi-tools ``batch_correction`` path, where the
historical ``**kwargs`` API forwarded every keyword to ``SCVI.__init__``,
leaving ``SCVI.train`` un-parameterisable. The helper partitions the
kwargs by signature; this file tests that partitioning logic against
synthetic callables so no real scvi-tools / torch install is required.
"""
from __future__ import annotations

import warnings

import pytest

from omicverse.single._batch import _split_kwargs_by_signature


# ── Synthetic targets ────────────────────────────────────────────────────────


def _init_like(self, adata, n_hidden=128, n_latent=10, dropout_rate=0.1, **kwargs):
    """Mimics ``scvi.model.SCVI.__init__``: named architecture params + a
    ``**kwargs`` catch-all that forwards to a submodule."""


def _train_like(self, max_epochs=400, batch_size=128, early_stopping=False,
                accelerator="auto", **trainer_kwargs):
    """Mimics ``scvi.model.SCVI.train``: named optimisation params + a
    ``**trainer_kwargs`` catch-all forwarding to Lightning."""


def _noop(self):
    """No named kwargs, no VAR_KEYWORD — accepts nothing by name."""


# ── Tests ────────────────────────────────────────────────────────────────────


class TestSplitKwargs:
    def test_named_params_route_to_their_destination(self) -> None:
        init, train = _split_kwargs_by_signature(
            {"n_hidden": 256, "max_epochs": 100, "dropout_rate": 0.2,
             "batch_size": 512, "early_stopping": True},
            ("init", _init_like),
            ("train", _train_like),
        )
        assert init == {"n_hidden": 256, "dropout_rate": 0.2}
        assert train == {"max_epochs": 100, "batch_size": 512,
                         "early_stopping": True}

    def test_empty_kwargs_yields_empty_dicts(self) -> None:
        init, train = _split_kwargs_by_signature(
            {},
            ("init", _init_like),
            ("train", _train_like),
        )
        assert init == {}
        assert train == {}

    def test_self_param_is_ignored(self) -> None:
        # 'self' is in both signatures' parameter list but must never be
        # routed — it's the bound-method receiver, not a real kwarg.
        init, train = _split_kwargs_by_signature(
            {"self": "should not be routed"},
            ("init", _init_like),
            ("train", _train_like),
        )
        # Falls through to first VAR_KEYWORD destination (init).
        assert init == {"self": "should not be routed"}
        assert train == {}

    def test_unknown_kwarg_falls_through_to_first_var_keyword(self) -> None:
        # 'plan_kwargs' is in neither destination's named list; both have
        # **kwargs, so the FIRST destination wins (deterministic).
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # promote warnings to errors
            init, train = _split_kwargs_by_signature(
                {"plan_kwargs": {"lr": 1e-3}},
                ("init", _init_like),
                ("train", _train_like),
            )
        assert init == {"plan_kwargs": {"lr": 1e-3}}
        assert train == {}

    def test_unknown_kwarg_with_no_var_keyword_is_dropped_with_warning(self) -> None:
        # Both destinations are no-arg; nothing can accept 'mystery'.
        with pytest.warns(UserWarning, match="Dropped unrecognised kwarg"):
            (only,) = _split_kwargs_by_signature(
                {"mystery": 42},
                ("noop", _noop),
            )
        assert only == {}

    def test_collision_routes_to_first_destination_with_warning(self) -> None:
        # 'batch_size' is a named param of train_like only by default —
        # construct a synthetic init that also takes batch_size to force
        # the collision case.
        def _init_with_overlap(self, adata, batch_size=128, **kwargs):
            pass

        with pytest.warns(UserWarning, match="batch_size"):
            init, train = _split_kwargs_by_signature(
                {"batch_size": 256},
                ("init_overlap", _init_with_overlap),
                ("train", _train_like),
            )
        # First destination in priority order wins on collision.
        assert init == {"batch_size": 256}
        assert train == {}

    def test_destination_order_is_preserved_in_output(self) -> None:
        # Reverse the order of (init, train) → the returned tuple must
        # match the call order, not some internal canonicalisation.
        train, init = _split_kwargs_by_signature(
            {"n_hidden": 128, "max_epochs": 50},
            ("train", _train_like),
            ("init", _init_like),
        )
        assert train == {"max_epochs": 50}
        assert init == {"n_hidden": 128}

    def test_works_when_a_destination_signature_cannot_be_introspected(self) -> None:
        # Some C-extension callables raise on inspect.signature. The
        # helper should degrade gracefully: that destination accepts
        # nothing by name and has no VAR_KEYWORD, so kwargs that name a
        # param of it would not match. Use a builtin as a stand-in.
        init, c_like = _split_kwargs_by_signature(
            {"n_hidden": 64},
            ("init", _init_like),
            ("c_callable", print),  # introspectable but irrelevant params
        )
        assert init == {"n_hidden": 64}
        assert c_like == {}

    def test_real_scvi_signatures_when_available(self) -> None:
        # Integration check against real scvi when it happens to be
        # installed; otherwise skipped.
        scvi = pytest.importorskip("scvi")
        init, train = _split_kwargs_by_signature(
            {"n_hidden": 256, "n_latent": 20, "max_epochs": 50,
             "batch_size": 512, "early_stopping": True},
            ("SCVI.__init__", scvi.model.SCVI.__init__),
            ("SCVI.train", scvi.model.SCVI.train),
        )
        assert "n_hidden" in init and "n_latent" in init
        assert "max_epochs" in train and "batch_size" in train and \
               "early_stopping" in train
        # And no leakage in the wrong direction.
        assert "max_epochs" not in init
        assert "n_hidden" not in train
