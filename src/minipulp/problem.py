"""问题容器 — 线性规划问题的建模层。

``LpProblem`` 是用户建模的入口，职责清晰分为三层：

1. **收集** — 用 ``+=`` 语法糖或显式方法添加目标函数与约束。
2. **表示** — 维护变量表、约束表，提供 ``variables()`` 等查询。
3. **委托** — ``solve(solver)`` 把问题交给求解器，求解器回填解值。

``+=`` 语法糖的设计
--------------------
PuLP 最具辨识度的 API 是 ``prob += expr``，它根据 ``expr`` 的类型
自动判断是设置目标还是添加约束：

- ``prob += 3*x + 2*y``  →  表达式 → 设置目标函数
- ``prob += 2*x + y <= 100``  →  约束 → 添加约束

这一重载让建模代码读起来几乎和数学公式一致::

    prob = LpProblem("demo", LpMaximize)
    prob += 3*x + 2*y           #  max 3x + 2y
    prob += 2*x + y <= 100      #  s.t. 2x + y ≤ 100
"""

from __future__ import annotations

from .constants import LpSense, LpStatus, LpStatusToMsg
from .constraints import LpConstraint
from .elements import LpAffineExpression, LpVariable


class LpProblem:
    """线性规划问题容器。

    Parameters
    ----------
    name : str, default "problem"
        问题名，用于 LP 文件输出与日志。
    sense : LpSense, default LpMinimize
        目标方向（``LpMinimize`` / ``LpMaximize``）。

    Attributes
    ----------
    objective : LpAffineExpression | None
        目标函数。未设置时为 None。
    constraints : dict[str, LpConstraint]
        约束字典，键为约束名。
    status : LpStatus
        求解状态，初始为 ``NOT_SOLVED``。
    """

    def __init__(self, name: str = "problem", sense: LpSense = LpSense.MINIMIZE) -> None:
        self.name = name
        self.sense = sense
        self.objective: LpAffineExpression | None = None
        self.constraints: dict[str, LpConstraint] = {}
        self.status: LpStatus = LpStatus.NOT_SOLVED
        self._variables: dict[str, LpVariable] = {}

    @property
    def status_msg(self) -> str:
        """求解状态的可读消息。"""
        return LpStatusToMsg.get(self.status, "Unknown")

    def __iadd__(self, other) -> "LpProblem":
        """``+=`` 语法糖：表达式→目标，约束→添加约束。

        这是 PuLP 风格建模的核心语法::

            prob += 3*x + 2*y          # 设置目标
            prob += 2*x + y <= 100     # 添加约束
        """
        if isinstance(other, LpConstraint):
            self.addConstraint(other)
        elif isinstance(other, LpAffineExpression):
            self.setObjective(other)
        elif isinstance(other, LpVariable):
            self.setObjective(other)
        else:
            raise TypeError(
                f"不支持的 += 操作数类型 {type(other).__name__}，"
                "只支持 LpAffineExpression（目标）或 LpConstraint（约束）"
            )
        return self

    def addVariable(self, var: LpVariable) -> None:
        """注册一个变量到问题变量表。

        重复添加同名变量会被忽略（按 name 去重）。
        """
        if var.name not in self._variables:
            self._variables[var.name] = var

    def addConstraint(self, constraint: LpConstraint, name: str | None = None) -> None:
        """添加约束。

        Parameters
        ----------
        constraint : LpConstraint
            约束对象，通常由 ``<=``/``>=``/``==`` 运算符构造。
        name : str | None
            约束名。None 时自动分配 ``c_N``。
        """
        if name is None:
            if constraint.name is None:
                name = f"c_{len(self.constraints)}"
            else:
                name = constraint.name
        constraint.name = name
        self.constraints[name] = constraint
        for var in constraint.terms:
            self.addVariable(var)

    def setObjective(self, expr: LpAffineExpression | LpVariable) -> None:
        """设置目标函数。

        Parameters
        ----------
        expr : LpAffineExpression | LpVariable
            目标表达式。若是 ``LpVariable``，会被当作单变量表达式。
        """
        if isinstance(expr, LpVariable):
            expr = LpAffineExpression({expr: 1.0})
        elif not isinstance(expr, LpAffineExpression):
            raise TypeError(
                f"目标函数必须是 LpAffineExpression，得到 {type(expr).__name__}"
            )
        self.objective = expr
        for var in expr.terms:
            self.addVariable(var)

    def variables(self) -> list[LpVariable]:
        """返回问题中所有变量（按添加顺序）。"""
        return list(self._variables.values())

    def numVariables(self) -> int:
        return len(self._variables)

    def numConstraints(self) -> int:
        return len(self.constraints)

    def solve(self, solver=None) -> LpStatus:
        """求解问题。

        Parameters
        ----------
        solver : LpSolver | None
            求解器实例。None 时使用默认求解器（Phase 3/4 实现）。

        Returns
        -------
        LpStatus
            求解状态码。
        """
        if solver is None:
            solver = _get_default_solver()
        self.status = solver.solve(self)
        return self.status

    def valid(self) -> bool:
        """检查问题是否已完整建模（有目标函数）。"""
        return self.objective is not None

    def __repr__(self) -> str:
        return f"{self.name}: {self.status_msg}"


def _get_default_solver():
    """获取默认求解器。

    优先级：SimplexCpp（C++，快 10-50x）→ SimplexCore（纯 Python，零依赖）。
    """
    from .solvers import SimplexCpp, SimplexCore
    cpp = SimplexCpp()
    if cpp.available():
        return cpp
    return SimplexCore()
