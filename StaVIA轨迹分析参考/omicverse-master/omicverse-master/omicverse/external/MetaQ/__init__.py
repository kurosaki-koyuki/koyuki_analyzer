"""Vendored MetaQ (Li et al., Nat Commun 2025).

Original repo: https://github.com/XLearning-SCU/MetaQ (MIT License).
Vendored verbatim with the following modifications:

- ``engine.py``: ``from model import reconstruction_loss`` →
  ``from .model import reconstruction_loss`` so the package works without
  being added to ``sys.path``.
- ``model.py``: ``einops.rearrange("n d -> d n")`` replaced with
  ``Tensor.t()`` to avoid an einops dependency.

CLI / file-I/O helpers (``MetaQ.py`` script, ``load_data(args)`` in
``data_utils``) are intentionally **not** vendored — omicverse drives the
training loop directly from an in-memory AnnData via
``ov.single.MetaCell(method='metaq')``.
"""

from . import model
from . import engine
from . import data_utils

from .model import (
    MetaQ,
    Quantizer,
    Encoder,
    Decoder,
    Decoder_ATAC,
    get_decoder,
    negative_binomial_loss,
    poisson_loss,
    reconstruction_loss,
)
from .engine import train_one_epoch, warm_one_epoch, inference
from .data_utils import MetaQDataset, preprocess, compute_metacell

__all__ = [
    "MetaQ",
    "Quantizer",
    "Encoder",
    "Decoder",
    "Decoder_ATAC",
    "get_decoder",
    "negative_binomial_loss",
    "poisson_loss",
    "reconstruction_loss",
    "train_one_epoch",
    "warm_one_epoch",
    "inference",
    "MetaQDataset",
    "preprocess",
    "compute_metacell",
]
