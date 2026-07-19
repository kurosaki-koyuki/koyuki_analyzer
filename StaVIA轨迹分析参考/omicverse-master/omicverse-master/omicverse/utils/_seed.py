"""Global random-seed control for reproducible omicverse runs (issue #807).

One call seeds every RNG backend omicverse touches — Python ``random``,
NumPy, PyTorch (CPU + CUDA), and MLX (Apple) — and records the seed in
``ov.settings.seed`` so downstream steps can pick it up. Functions that
already expose a ``random_state``/``seed`` argument still honour an explicit
value; ``set_seed`` fixes the *global* generators those functions fall back
on (and the non-seedable corners of the GPU paths).
"""
from __future__ import annotations

import os
import random as _random


class _SeedDefault:
    """Sentinel default for ``random_state`` args that should follow the
    global seed (``ov.settings.seed``) when one has been set, else 0."""

    def __repr__(self):  # pragma: no cover - cosmetic
        return "<ov.seed-default>"


SEED_DEFAULT = _SeedDefault()


def resolve_random_state(random_state=SEED_DEFAULT, fallback: int = 0):
    """Resolve a ``random_state`` argument against the global seed.

    * An explicit value (int / ``RandomState`` / ``None``) is returned as-is.
    * The :data:`SEED_DEFAULT` sentinel resolves to ``ov.settings.seed`` if
      :func:`set_seed` has set one, otherwise ``fallback`` (0). This lets
      ``ov.set_seed(s)`` drive every ``ov.pp`` function's default seed without
      passing ``random_state`` to each call, while keeping any explicit value.
    """
    if isinstance(random_state, _SeedDefault):
        try:
            from .._settings import settings

            if getattr(settings, "seed", None) is not None:
                return settings.seed
        except Exception:  # noqa: BLE001
            pass
        return fallback
    return random_state


def set_seed(seed: int = 0, *, deterministic: bool = False,
             verbose: bool = True) -> int:
    """Seed all RNGs used by omicverse for reproducible results.

    Seeds Python ``random``, ``PYTHONHASHSEED``, NumPy, PyTorch (CPU + every
    CUDA device) and MLX (if installed). Optionally forces deterministic GPU
    kernels.

    Parameters
    ----------
    seed
        The seed value (default ``0``).
    deterministic
        If ``True``, also request deterministic algorithms on GPU
        (``cudnn.deterministic=True``, ``cudnn.benchmark=False`` and
        ``torch.use_deterministic_algorithms(True, warn_only=True)``). This
        trades some speed for bit-level reproducibility and is off by default.
    verbose
        Print a short confirmation.

    Returns
    -------
    int
        The seed that was set.

    Examples
    --------
    >>> import omicverse as ov
    >>> ov.set_seed(0)              # at the top of your script / notebook
    >>> # ... ov.pp.neighbors / ov.pp.umap / ov.pp.leiden now reproducible
    """
    seed = int(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    _random.seed(seed)

    backends = ["python"]

    try:
        import numpy as np

        np.random.seed(seed)
        backends.append("numpy")
    except Exception:  # noqa: BLE001
        pass

    try:
        import torch

        torch.manual_seed(seed)
        backends.append("torch")
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            backends.append("cuda")
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            try:
                torch.use_deterministic_algorithms(True, warn_only=True)
            except Exception:  # noqa: BLE001
                pass
            # cuBLAS determinism for matmul on CUDA >= 10.2
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            backends.append("deterministic")
    except Exception:  # noqa: BLE001
        pass

    try:
        import mlx.core as mx

        mx.random.seed(seed)
        backends.append("mlx")
    except Exception:  # noqa: BLE001
        pass

    # Record globally so other code can read ov.settings.seed.
    try:
        from .._settings import settings

        settings.seed = seed
    except Exception:  # noqa: BLE001
        pass

    if verbose:
        try:
            from .._settings import Colors, EMOJI

            print(f"{Colors.GREEN}{EMOJI.get('done', '✓')} "
                  f"Global seed set to {seed} "
                  f"[{', '.join(backends)}]{Colors.ENDC}")
        except Exception:  # noqa: BLE001
            print(f"Global seed set to {seed} [{', '.join(backends)}]")
    return seed
