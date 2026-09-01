"""C++ 两阶段单纯形法求解器 — pybind11 绑定层（L1）。

本模块将 ``core/_native``（C++ 编译的 pybind11 扩展）包装为 ``LpSolver``，
与 ``SimplexCore``（纯 Python）共享提取/回填逻辑，仅替换核心计算。

设计意图：展示"同一建模层、可插拔计算层"范式——
换求解器只需改 ``prob.solve(solver=...)`` 一行，建模代码不变。

与 ``simplex_py.py`` 对照阅读：算法逻辑完全相同，仅语言不同。
"""

from __future__ import annotations

from ..constants import LpStatus
from .base import LpSolver
from .simplex_py import SimplexCore


class SimplexCpp(SimplexCore):
    """C++ 两阶段单纯形法求解器。

    继承 ``SimplexCore`` 的提取/回填逻辑，仅覆盖 ``_solve`` 调用 C++ 核心。
    适合中等规模 LP（变量数 < 1000），比纯 Python 版快 10-50x。

    Examples
    --------
    >>> import minipulp as mp
    >>> from minipulp.solvers import SimplexCpp
    >>> x = mp.LpVariable("x", lowBound=0)
    >>> prob = mp.LpProblem("demo", mp.LpMaximize)
    >>> prob += 3 * x
    >>> prob += x <= 10
    >>> prob.solve(solver=SimplexCpp())
    >>> x.varValue
    10.0
    """

    name = "SimplexCpp"

    def __init__(self, verbose: bool = False) -> None:
        super().__init__(verbose=verbose)

    def available(self) -> bool:
        try:
            from ..core import _native
            return True
        except ImportError:
            return False

    def _solve(self, std: dict) -> tuple[LpStatus, list[float]]:
        from ..core import _native

        cost = std["cost"]
        rows = std["rows"]
        rhs = std["rhs"]
        senses = std["senses"]
        n = std["n"]
        m = len(rows)

        if m == 0:
            return self._solve_no_constraints(std)

        senses_int = [int(s) for s in senses]

        status_code, solution = _native.solve_simplex(cost, rows, rhs, senses_int)

        status = LpStatus(status_code)
        return status, solution[:n]