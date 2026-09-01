"""minipulp — 从零实现 PuLP 的教学复刻。

顶层导出建模所需的全部公开 API，使用方式与 PuLP 兼容::

    import minipulp as mp
    x = mp.LpVariable("x", lowBound=0)
    prob = mp.LpProblem("demo", mp.LpMaximize)
    prob += 3 * x
    prob.solve()
"""

from .constants import (
    LpBinary,
    LpCat,
    LpContinuous,
    LpConstraintSense,
    LpInteger,
    LpMaximize,
    LpMinimize,
    LpSense,
    LpStatus,
    LpStatusInfeasible,
    LpStatusNotSolved,
    LpStatusOptimal,
    LpStatusToMsg,
    LpStatusUnbounded,
    LpStatusUndefined,
)
from .elements import LpAffineExpression, LpElement, LpVariable, lpSum
from .constraints import LpConstraint
from .problem import LpProblem
from .lp_io import write_lp

__all__ = [
    "LpSense",
    "LpCat",
    "LpConstraintSense",
    "LpStatus",
    "LpMinimize",
    "LpMaximize",
    "LpContinuous",
    "LpInteger",
    "LpBinary",
    "LpStatusOptimal",
    "LpStatusInfeasible",
    "LpStatusUnbounded",
    "LpStatusNotSolved",
    "LpStatusUndefined",
    "LpStatusToMsg",
    "LpElement",
    "LpVariable",
    "LpAffineExpression",
    "lpSum",
    "LpConstraint",
    "LpProblem",
    "write_lp",
]

__version__ = "0.1.0"