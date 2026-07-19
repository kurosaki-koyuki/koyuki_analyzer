import importlib

import numpy as np


def test_jackknife_import_does_not_change_numpy_error_handling():
    import omicverse.external.gsmap._jackknife as jackknife

    original = np.seterr(all="warn")
    try:
        importlib.reload(jackknife)
        assert np.geterr() == {"divide": "warn", "over": "warn", "under": "warn", "invalid": "warn"}
    finally:
        np.seterr(**original)
