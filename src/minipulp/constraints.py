"""约束对象 — 仿射表达式与零的比较关系。

约束是建模的第三类基本对象（变量、表达式、约束）。本模块定义
``LpConstraint``，它由 ``LpElement.__le__``/``__ge__``/``__eq__``
在运算符重载中自动构造，用户通常不直接实例化。

归一化约定
-----------
用户写的 ``3*x + 2*y <= 10`` 在内部被归一化为::

    LpConstraint(lhs=LpAffineExpression({x:3, y:2}, const=-10), sense=LE)

即 ``lhs <= 0`` 的齐次形式。这一归一化让求解器只需处理一种形式，
而非为 ``<=``/``>=``/``==`` 各写一套逻辑。详见
docs/principles/affine-closure.md。
"""

from __future__ import annotations

from .constants import LpConstraintSense
from .elements import LpAffineExpression

_CONSTRAINT_SYMBOL = {
    LpConstraintSense.LE: "<=",
    LpConstraintSense.EQ: "==",
    LpConstraintSense.GE: ">=",
}


class LpConstraint:
    """线性约束：``lhs (<=|==|>=) 0``。

    Parameters
    ----------
    lhs : LpAffineExpression
        归一化后的左侧表达式（已把右端项移到左边）。
    sense : LpConstraintSense, default LE
        比较方向。
    name : str | None
        约束名，用于 LP 文件输出。由 ``LpProblem`` 在添加时自动分配。

    Attributes
    ----------
    lhs : LpAffineExpression
        左侧表达式。
    sense : LpConstraintSense
        比较方向。
    name : str | None
        约束名。
    """

    def __init__(
        self,
        lhs: LpAffineExpression,
        sense: LpConstraintSense = LpConstraintSense.LE,
        name: str | None = None,
    ) -> None:
        self.lhs = lhs
        self.sense = sense
        self.name = name

    @property
    def expression(self) -> LpAffineExpression:
        """左侧表达式（归一化后，右端项已移到左边）。"""
        return self.lhs

    @property
    def constant(self) -> float:
        """左侧表达式的常数项（即负的右端项）。"""
        return self.lhs.const

    @property
    def terms(self) -> dict:
        """左侧表达式的变量系数字典。"""
        return self.lhs.terms

    def __repr__(self) -> str:
        return f"{self.lhs} {_CONSTRAINT_SYMBOL[self.sense]} 0"

    def __str__(self) -> str:
        return self.__repr__()
