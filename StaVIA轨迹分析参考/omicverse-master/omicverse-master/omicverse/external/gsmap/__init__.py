from __future__ import annotations

"""Vendored gsMap integration core for OmicVerse."""

from ._config import (
    CauchyCombinationConfig,
    DiagnosisConfig,
    FindLatentRepresentationsConfig,
    GenerateLdscoreConfig,
    LatentToGeneConfig,
    ReportConfig,
    SpatialLdscConfig,
)
from .cauchy_combination import run_cauchy_combination
from .diagnosis import run_diagnosis
from .find_latent_representation import run_find_latent_representation
from .generate_ldscore import run_generate_ldscore
from .latent_to_gene import run_latent_to_gene
from .report import run_report
from .spatial_ldsc import run_spatial_ldsc

__all__ = [
    "CauchyCombinationConfig",
    "DiagnosisConfig",
    "FindLatentRepresentationsConfig",
    "GenerateLdscoreConfig",
    "LatentToGeneConfig",
    "ReportConfig",
    "SpatialLdscConfig",
    "run_cauchy_combination",
    "run_diagnosis",
    "run_find_latent_representation",
    "run_generate_ldscore",
    "run_latent_to_gene",
    "run_report",
    "run_spatial_ldsc",
]
