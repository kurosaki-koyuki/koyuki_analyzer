"""Vendored graph neural network helpers used by gsMap latent learning."""

from .model import gat_model
from .train import model_trainer

__all__ = [
    "gat_model",
    "model_trainer",
]
