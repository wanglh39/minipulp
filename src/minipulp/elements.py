"""变量与表达式系统 — minipulp 的代数核心。

本模块实现线性规划建模的"代数层"，是理解 PuLP 设计哲学的入口。
核心三类对象构成一个闭包：

    LpVariable ⊂ LpAffineExpression
    LpAffineExpression + LpAffineExpression → LpAffineExpression
    c * LpAffineExpression → LpAffineExpression

即：变量的任意线性组合仍是仿射表达式。这一闭包性质是整个库
能用 ``{var: coef}`` 字典表示任意表达式的数学基础。

继承关系
---------
本库采用 PuLP 的继承设计::

    LpElement ──> LpAffineExpression ──> LpVariable

变量"是一个"单变量表达式（``terms = {self: 1}, const = 0``）。
这一数学事实让运算符重载只需在 ``LpAffineExpression`` 写一次，
``LpVariable`` 自动继承全部代数能力。

运算符重载一览
---------------
==================  ===========================  ==========================
表达式              调用的运算符                  结果
==================  ===========================  ==========================
``3 * x``           ``int.__mul__`` 失败 → ``x.__rmul__(3)``  ``AffExpr({x:3})``
``x + y``           ``x.__add__(y)``             ``AffExpr({x:1, y:1})``
``x + 5``           ``x.__add__(5)``             ``AffExpr({x:1}, c=5)``
``3*x + 2*y``       两次 mul + 一次 add          ``AffExpr({x:3, y:2})``
``x <= 5``          ``x.__le__(5)``              ``LpConstraint(x-5, LE)``
``x == y``          ``x.__eq__(y)``              ``LpConstraint(x-y, EQ)``
==================  ===========================  ==========================

详见 docs/principles/operator-overloading.md。
"""

from __future__ import annotations

from numbers import Number as _Number
from typing import Union

from .constants import LpCat, LpConstraintSense

NumberLike = Union[int, float]

_ZERO = 0.0


def _is_number(obj) -> bool:
    """判断是否为数值（int/float，不含 bool）。"""
    return isinstance(obj, _Number) and not isinstance(obj, bool)


class LpElement:
    """所有可参与代数运算对象的基类。

    定义运算符协议。子类通过重载这些方法，让 ``3 * x + 2 * y`` 这样的
    Python 表达式直接构造出 ``LpAffineExpression({x: 3, y: 2})`` 对象，
    而非做数值计算——这是"代数表达式即代码"的核心机制。

    关于 ``__eq__`` 的特殊性
    ------------------------
    建模库必须重载 ``__eq__`` 以支持 ``x == y`` 构造等式约束。但这会
    覆盖默认的相等性判断，影响对象作为字典 key 的行为。本库的处理：

    1. ``__hash__`` 基于 ``name``（变量）或 ``id``（表达式），保证可哈希。
    2. 字典查找时，Python 先用 ``is``（指针相等）判断，再用 ``__eq__``。
       同一变量对象作为 key 时 ``is`` 命中，不会误触发 ``__eq__``。
    3. 不同变量 ``name`` 不同 → ``hash`` 不同 → 不会触发 ``__eq__``。

    因此只要不创建同名变量，字典行为安全。
    """

    name: str = ""

    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __add__(self, other):
        raise NotImplementedError

    def __radd__(self, other):
        raise NotImplementedError

    def __sub__(self, other):
        raise NotImplementedError

    def __rsub__(self, other):
        raise NotImplementedError

    def __mul__(self, other):
        raise NotImplementedError

    def __rmul__(self, other):
        raise NotImplementedError

    def __truediv__(self, other):
        raise NotImplementedError

    def __neg__(self):
        raise NotImplementedError

    def __le__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.LE)

    def __ge__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.GE)

    def __eq__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.EQ)


class LpAffineExpression(LpElement):
    """仿射表达式：``sum(coef_i * var_i) + const``。

    内部表示为 ``{LpVariable: float}`` 字典 + 一个常数项 ``const``。
    这种表示的合法性来自仿射表达式在加法、数乘下的**闭包性**：

    - 两个仿射表达式相加，结果仍是仿射表达式（字典系数相加）。
    - 仿射表达式乘以常数，结果仍是仿射表达式（系数同乘）。

    因此无需表达式树，一个扁平字典就够了。这是 PuLP 能用极简代码
    表示任意线性表达式的数学根因。详见
    docs/principles/affine-closure.md。

    Parameters
    ----------
    terms : dict[LpVariable, float] | None
        变量到系数的映射。None 表示空（纯常数）。
    const : float, default 0.0
        常数项。

    Attributes
    ----------
    terms : dict[LpVariable, float]
        变量系数字典。构造时会剔除零系数项以保持规范化。
    const : float
        常数项。
    """

    def __init__(self, terms: dict | None = None, const: NumberLike = _ZERO) -> None:
        if terms is None:
            self.terms: dict = {}
        else:
            self.terms = {var: float(coef) for var, coef in terms.items() if coef != 0}
        self.const: float = float(const)

    def _new(self, terms: dict, const: NumberLike) -> "LpAffineExpression":
        """工厂方法：子类（LpVariable）运算后降级为普通表达式。"""
        return LpAffineExpression(terms, const)

    def __add__(self, other) -> "LpAffineExpression":
        if _is_number(other):
            return self._new(self.terms, self.const + other)
        if isinstance(other, LpAffineExpression):
            merged = dict(self.terms)
            for var, coef in other.terms.items():
                new_coef = merged.get(var, _ZERO) + coef
                if new_coef != 0:
                    merged[var] = new_coef
                else:
                    merged.pop(var, None)
            return self._new(merged, self.const + other.const)
        return NotImplemented

    def __radd__(self, other) -> "LpAffineExpression":
        return self.__add__(other)

    def __sub__(self, other) -> "LpAffineExpression":
        if _is_number(other):
            return self._new(self.terms, self.const - other)
        if isinstance(other, LpAffineExpression):
            merged = dict(self.terms)
            for var, coef in other.terms.items():
                new_coef = merged.get(var, _ZERO) - coef
                if new_coef != 0:
                    merged[var] = new_coef
                else:
                    merged.pop(var, None)
            return self._new(merged, self.const - other.const)
        return NotImplemented

    def __rsub__(self, other) -> "LpAffineExpression":
        if _is_number(other):
            return self._new(
                {var: -coef for var, coef in self.terms.items()},
                other - self.const,
            )
        return NotImplemented

    def __mul__(self, other) -> "LpAffineExpression":
        if _is_number(other):
            if other == 0:
                return self._new({}, _ZERO)
            return self._new(
                {var: coef * other for var, coef in self.terms.items()},
                self.const * other,
            )
        if isinstance(other, LpAffineExpression):
            if not self.terms or not other.terms:
                if self.terms:
                    return self._new({}, _ZERO)
                return self._new(
                    {var: coef * self.const for var, coef in other.terms.items()},
                    self.const * other.const,
                )
            raise TypeError(
                "不能将两个含变量的表达式相乘（非线性），"
                "线性规划只允许仿射表达式"
            )
        return NotImplemented

    def __rmul__(self, other) -> "LpAffineExpression":
        return self.__mul__(other)

    def __truediv__(self, other) -> "LpAffineExpression":
        if _is_number(other):
            if other == 0:
                raise ZeroDivisionError("表达式除以零")
            return self.__mul__(1.0 / other)
        return NotImplemented

    def __neg__(self) -> "LpAffineExpression":
        return self._new(
            {var: -coef for var, coef in self.terms.items()},
            -self.const,
        )

    def value(self) -> float | None:
        """在变量已被求解（``varValue`` 已回填）时计算表达式的值。

        任一变量未求解则返回 None。
        """
        total = self.const
        for var, coef in self.terms.items():
            if var.varValue is None:
                return None
            total += coef * var.varValue
        return total

    def is_constant(self) -> bool:
        """是否为纯常数（无变量项）。"""
        return not self.terms

    def __repr__(self) -> str:
        if not self.terms:
            return f"{self.const}"
        parts = []
        for var, coef in self.terms.items():
            if coef == 1:
                parts.append(f"{var.name}")
            elif coef == -1:
                parts.append(f"-{var.name}")
            else:
                parts.append(f"{coef}*{var.name}")
        s = " + ".join(parts)
        if self.const:
            s += f" + {self.const}"
        return s

    def __str__(self) -> str:
        return self.__repr__()


class LpVariable(LpAffineExpression):
    """决策变量 — 单变量仿射表达式的语法糖。

    数学上，变量 ``x`` 就是仿射表达式 ``1 * x + 0``，即
    ``terms = {x: 1}, const = 0``。因此 ``LpVariable`` 继承
    ``LpAffineExpression``，构造时把自己作为单项系数为 1 的表达式。

    这带来的关键好处：运算符重载只在 ``LpAffineExpression`` 写一次，
    ``LpVariable`` 自动获得 ``x + y``、``3 * x``、``x <= 5`` 等全部
    代数能力。

    Parameters
    ----------
    name : str
        变量名。同时作为 ``__hash__`` 的依据，因此同名变量会被
        字典视为同一 key——不要创建同名变量。
    lowBound : float | None, default None
        下界。None 表示无下界（负无穷）。
    upBound : float | None, default None
        上界。None 表示无上界（正无穷）。
    cat : LpCat, default LpContinuous
        变量类别（连续 / 整数 / 二元）。

    Attributes
    ----------
    varValue : float | None
        求解后由求解器回填的解值。求解前为 None。
    """

    def __init__(
        self,
        name: str,
        lowBound: NumberLike | None = None,
        upBound: NumberLike | None = None,
        cat: LpCat = LpCat.CONTINUOUS,
    ) -> None:
        self.name = name
        self.lowBound = lowBound
        self.upBound = upBound
        self.cat = cat
        self.varValue: NumberLike | None = None
        self.terms: dict = {self: 1.0}
        self.const: float = _ZERO

    def _new(self, terms: dict, const: NumberLike) -> "LpAffineExpression":
        """变量参与运算后降级为普通表达式，不再保留变量属性。"""
        return LpAffineExpression(terms, const)

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


def lpSum(vector: list) -> LpAffineExpression:
    """对一组仿射表达式求和，等价于 ``sum(vector)`` 但语义更明确。

    PuLP 提供 ``lpSum`` 作为批量求和的推荐方式，避免在循环中
    反复构造中间表达式对象。本教学版直接用 ``sum`` 亦可，
    此函数主要为了 API 对齐。

    Examples
    --------
    >>> x = LpVariable("x"); y = LpVariable("y")
    >>> lpSum([3*x, 2*y, 5])
    3.0*x + 2.0*y + 5.0
    """
    if not vector:
        return LpAffineExpression()
    result = LpAffineExpression()
    for item in vector:
        result = result + item
    return result
