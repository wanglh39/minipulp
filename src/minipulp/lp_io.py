"""LP / MPS 文件格式读写 — 建模层与求解器层的中间表示。

LP 格式是 CPLEX 定义的人类可读线性规划格式，是建模库与求解器之间
最常用的文本通信协议。本模块实现 ``write_lp``，将 ``LpProblem``
序列化为标准 LP 格式文本。

CPLEX LP 格式结构
------------------

::

    \\ Problem name: demo
    Maximize
      obj: 3 x + 2 y
    Subject To
      c_0: 2 x + 1 y <= 100
    Bounds
      x >= 0
      y free
    General
      z
    Binary
      b
    End

各段语义：
- ``Maximize`` / ``Minimize`` : 目标函数
- ``Subject To`` : 约束（``<=`` / ``>=`` / ``=``）
- ``Bounds`` : 变量上下界（省略时默认 ``x >= 0``）
- ``General`` / ``Integer`` : 整数变量
- ``Binary`` : 0/1 变量
- ``End`` : 文件结束

详见 docs/principles/lp-format.md。
"""

from __future__ import annotations

from .constants import LpCat, LpConstraintSense, LpSense
from .problem import LpProblem

_CONSTRAINT_OP = {
    LpConstraintSense.LE: "<=",
    LpConstraintSense.EQ: "=",
    LpConstraintSense.GE: ">=",
}


def _format_coef(coef: float) -> str:
    """系数格式化：整数输出 3，浮点输出 3.5。"""
    if coef == int(coef):
        return str(int(coef))
    return str(coef)


def _format_terms(terms: dict) -> str:
    """将 ``{var: coef}`` 字典格式化为 ``3 x + 2 y`` 形式。"""
    if not terms:
        return "0"
    parts = []
    for var, coef in terms.items():
        if coef == 1.0:
            parts.append(f"+ {var.name}")
        elif coef == -1.0:
            parts.append(f"- {var.name}")
        elif coef < 0:
            parts.append(f"- {_format_coef(abs(coef))} {var.name}")
        else:
            parts.append(f"+ {_format_coef(coef)} {var.name}")
    s = " ".join(parts)
    if s.startswith("+ "):
        s = s[2:]
    return s


def write_lp(problem: LpProblem) -> str:
    """将问题序列化为 CPLEX LP 格式文本。

    Parameters
    ----------
    problem : LpProblem
        已建模的问题（需有目标函数）。

    Returns
    -------
    str
        LP 格式文本。

    Examples
    --------
    >>> import minipulp as mp
    >>> x = mp.LpVariable("x", lowBound=0)
    >>> prob = mp.LpProblem("demo", mp.LpMaximize)
    >>> prob += 3 * x
    >>> print(write_lp(prob))
    \\ Problem name: demo
    Maximize
      obj: 3 x
    Bounds
      x >= 0
    End
    """
    if not problem.valid():
        raise ValueError("问题未设置目标函数，无法导出")

    lines: list[str] = []
    lines.append(f"\\ Problem name: {problem.name}")

    sense_word = "Maximize" if problem.sense == LpSense.MAXIMIZE else "Minimize"
    lines.append(sense_word)
    obj_terms = _format_terms(problem.objective.terms)
    obj_const = problem.objective.const
    if obj_const:
        lines.append(f"  obj: {obj_terms} + {_format_coef(obj_const)}")
    else:
        lines.append(f"  obj: {obj_terms}")

    if problem.constraints:
        lines.append("Subject To")
        for name, con in problem.constraints.items():
            terms_str = _format_terms(con.terms)
            rhs = -con.constant
            op = _CONSTRAINT_OP[con.sense]
            lines.append(f"  {name}: {terms_str} {op} {_format_coef(rhs)}")

    integer_vars = []
    binary_vars = []
    bounded_lines = []
    for var in problem.variables():
        lb, ub = var.lowBound, var.upBound
        if lb is None and ub is None:
            bounded_lines.append(f"  {var.name} free")
        elif lb is not None and ub is not None:
            bounded_lines.append(f"  {lb} <= {var.name} <= {ub}")
        elif lb is not None:
            bounded_lines.append(f"  {var.name} >= {lb}")
        else:
            bounded_lines.append(f"  {var.name} <= {ub}")

        if var.cat == LpCat.INTEGER:
            integer_vars.append(var.name)
        elif var.cat == LpCat.BINARY:
            binary_vars.append(var.name)

    if bounded_lines:
        lines.append("Bounds")
        lines.extend(bounded_lines)

    if integer_vars:
        lines.append("General")
        for v in integer_vars:
            lines.append(f"  {v}")

    if binary_vars:
        lines.append("Binary")
        for v in binary_vars:
            lines.append(f"  {v}")

    lines.append("End")
    return "\n".join(lines)


def write_mps(problem: LpProblem) -> str:
    """将问题序列化为 MPS 固定格式文本。

    MPS 是更古老的列导向格式，Phase 4 实现以对接更多求解器。
    """
    raise NotImplementedError("Phase 4 实现")
