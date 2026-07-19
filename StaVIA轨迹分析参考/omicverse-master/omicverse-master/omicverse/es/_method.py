# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

from collections.abc import Callable

import pandas as pd

from ._datatype import DataType
from ._run import _run

class MethodMeta:
    def __init__(
        self,
        name: str,
        desc: str,
        func: Callable,
        stype: str,
        adj: bool,
        weight: bool,
        test: bool,
        limits: tuple,
        reference: str,
        func_torch: Callable | None = None,
    ):
        self.name = name
        self.desc = desc
        self.func = func
        self.stype = stype
        self.adj = adj
        self.weight = weight
        self.test = test
        self.limits = limits
        self.reference = reference
        # Optional torch GPU kernel — same signature as `func`. When
        # not None, callers can request `engine='gpu'` and the Method
        # will dispatch here instead.
        self.func_torch = func_torch

    def meta(self) -> pd.DataFrame:
        meta = pd.DataFrame(
            [
                {
                    "name": self.name,
                    "desc": self.desc,
                    "stype": self.stype,
                    "weight": self.weight,
                    "test": self.test,
                    "limits": self.limits,
                    "reference": self.reference,
                }
            ]
        )
        return meta

class Method(MethodMeta):
    def __init__(
        self,
        _method: MethodMeta,
    ):
        super().__init__(
            name=_method.name,
            desc=_method.desc,
            func=_method.func,
            stype=_method.stype,
            adj=_method.adj,
            weight=_method.weight,
            test=_method.test,
            limits=_method.limits,
            reference=_method.reference,
            func_torch=_method.func_torch,
        )
        self._method = _method
        self.__doc__ = self.func.__doc__

    def __call__(
        self,
        data: DataType,
        net: pd.DataFrame,
        tmin: int | float = 5,
        raw: bool = False,
        empty: bool = True,
        bsize: int | float = 250_000,
        verbose: bool = False,
        engine: str = 'auto',
        **kwargs,
    ):
        from ._engine import resolve_engine

        eng = resolve_engine(engine, has_torch_kernel=self.func_torch is not None)
        func = self.func_torch if eng == 'gpu' else self.func
        return _run(
            name=self.name,
            func=func,
            adj=self.adj,
            test=self.test,
            data=data,
            net=net,
            tmin=tmin,
            raw=raw,
            empty=empty,
            bsize=bsize,
            verbose=verbose,
            **kwargs,
        )

def _show_methods(methods):
    return pd.concat([method.meta() for method in methods]).reset_index(drop=True)
