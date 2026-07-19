"""Pure-Python implementation of the SuperCell algorithm.

Reference
---------
Bilous et al., *Metacells untangle large and complex single-cell transcriptome
networks*. BMC Bioinformatics 23, 336 (2022).
https://doi.org/10.1186/s12859-022-04861-1

Original R implementation: https://github.com/GfellerLab/SuperCell

This module re-implements the core algorithm (kNN graph in PC space +
walktrap community detection) in ~50 lines of Python using
:mod:`igraph`, which is already an omicverse dependency.
"""

from .supercell import (
    SuperCell,
    supercell_partition,
)

__all__ = ["SuperCell", "supercell_partition"]
