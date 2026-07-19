"""Vendored geosketch (Hie et al., Cell Systems 2019).

Original repo: https://github.com/brianhie/geosketch (MIT License).
Vendored verbatim with one modification:

- ``utils.py``: ``fbpca.pca`` and ``sklearn.random_projection.SparseRandomProjection``
  imports moved inside ``reduce_dimensionality()`` so the package imports
  without those optional deps.
"""

from .sketch import *

__version__ = "1.3"
