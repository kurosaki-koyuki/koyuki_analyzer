"""Tests for the global random-seed control ov.set_seed (issue #807)."""
import numpy as np


def test_set_seed_exposed_and_records():
    import omicverse as ov

    ov.set_seed(123, verbose=False)
    assert ov.settings.seed == 123
    # settings method form
    ov.settings.set_seed(7, verbose=False)
    assert ov.settings.seed == 7


def test_numpy_reproducible():
    import omicverse as ov

    ov.set_seed(42, verbose=False)
    a = np.random.rand(5)
    ov.set_seed(42, verbose=False)
    b = np.random.rand(5)
    assert np.allclose(a, b)


def test_python_random_reproducible():
    import random

    import omicverse as ov

    ov.set_seed(1, verbose=False)
    a = [random.random() for _ in range(5)]
    ov.set_seed(1, verbose=False)
    b = [random.random() for _ in range(5)]
    assert a == b


def test_torch_reproducible_if_available():
    import omicverse as ov

    try:
        import torch
    except Exception:
        import pytest
        pytest.skip("torch not installed")
    ov.set_seed(5, verbose=False)
    a = torch.randn(4)
    ov.set_seed(5, verbose=False)
    b = torch.randn(4)
    assert torch.allclose(a, b)


def test_deterministic_flag_runs():
    import omicverse as ov

    # should not raise even when requesting deterministic algorithms
    seed = ov.set_seed(0, deterministic=True, verbose=False)
    assert seed == 0


def test_seed_propagates_to_pp_random_state():
    """ov.set_seed should drive the default random_state of pp functions."""
    import omicverse as ov
    from omicverse.utils._seed import SEED_DEFAULT, resolve_random_state

    ov.settings.seed = None
    assert resolve_random_state(SEED_DEFAULT) == 0          # no seed -> 0
    ov.set_seed(42, verbose=False)
    assert resolve_random_state(SEED_DEFAULT) == 42         # follows global seed
    assert resolve_random_state(7) == 7                     # explicit wins
    ov.settings.seed = None


def test_pca_exposes_random_state():
    import inspect

    import omicverse as ov

    assert "random_state" in inspect.signature(ov.pp.pca).parameters
