# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import pandas as pd

from ._datatype import DataType
from ._consensus import consensus
from ._methods import _methods

def decouple(
    data: DataType,
    net: pd.DataFrame,
    methods: str | list = "all",
    args: dict | None = None,
    cons: bool = False,
    **kwargs,
) -> dict | None:
    """
    Runs multiple enrichment methods sequentially.

    Parameters
    ----------
    %(data)s
    %(net)s
    methods
        List of methods to run.
    args
        Dictionary of dictionaries containing method-specific keyword arguments.
    cons
        Whether to get a consensus score across the used methods.
    %(tmin)s
    %(raw)s
    %(empty)s
    %(bsize)s
    %(verbose)s

    Returns
    -------
    Dictionary of results or as ``.obsm`` keys in the provided AnnData.

    Example
    -------
    .. code-block:: python

        import omicverse as ov

        adata, net = ov.es.toy_data()  # or your own (adata, net)
        ov.es.decouple(adata, net, tmin=3)
    """
    # Validate
    _mdict = {m.name: m for m in _methods}
    if isinstance(methods, str):
        if methods == "all":
            methods_list = list(_mdict.keys())
        else:
            methods_list = [methods]
    else:
        methods_list = list(methods)
    methods_set = set(methods_list)
    if args is None:
        args = {}
    assert methods_set.issubset(_mdict), (
        f"methods={methods_set} must be in decoupler.\nUse decoupler.mt.show_methods to check which ones are available"
    )
    assert all(k in methods_set for k in args), (
        f"All keys in args={args.keys()} must belong to a method in methods={methods_set}"
    )
    kwargs = kwargs.copy()
    kwargs.setdefault("verbose", False)
    # Run each method
    all_res: dict[str, float] = {}
    args = args.copy()
    for name in methods_set:
        mth = _mdict[name]
        arg = args.setdefault(name, {})
        res = mth(data=data, net=net, **arg, **kwargs)
        if res:
            res = {
                f"score_{mth.name}": res[0],
                f"padj_{mth.name}": res[1],
            }
            all_res = all_res | res
    if all_res:
        if cons:
            all_res["score_consensus"], all_res["padj_consensus"] = consensus(all_res, verbose=kwargs["verbose"])
        return all_res
    elif cons:
        consensus(data, verbose=kwargs["verbose"])
    return None
