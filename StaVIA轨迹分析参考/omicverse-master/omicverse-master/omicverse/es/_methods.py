# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

from ._aucell import aucell
from ._gsea import gsea
from ._gsva import gsva
from ._mdt import mdt
from ._mlm import mlm
from ._ora import ora
from ._udt import udt
from ._ulm import ulm
from ._viper import viper
from ._waggr import waggr
from ._zscore import zscore

_methods = [
    aucell,
    gsea,
    gsva,
    mdt,
    mlm,
    ora,
    udt,
    ulm,
    viper,
    waggr,
    zscore,
]
