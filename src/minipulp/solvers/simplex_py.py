"""纯 Python 两阶段单纯形法 — 教学求解器（L0）。

本模块用最透明的 Python 代码实现单纯形法，目标是让读者能逐步跟踪
每一个数值的变化，理解主元选择、转轴操作、基变量进出等核心概念。
不依赖 numpy，只用原生 list，算法逻辑完全暴露。

算法概要
--------
两阶段单纯形法处理一般线性规划::

    min (或 max)  c^T x
    s.t.          A x (<=, >=, ==) b
                  x >= lb  (下界)

步骤：

1. **标准化** — max 转 min；变量平移 ``x' = x - lb`` 使下界变 0；
   ``>=``/``==`` 约束加人工变量；``<=`` 约束加松弛变量。
2. **阶段一** — 最小化人工变量之和，求初始可行基。若最优值 > 0，
   原问题不可行。
3. **阶段二** — 从阶段一的可行基出发，最小化原目标。
4. **回填** — 把解值写回 ``LpVariable.varValue``。

单纯形表
--------
用分离的 ``A``（系数矩阵）和 ``b``（右端项）表示，``basis[i]``
记录第 i 行的基变量列号。基变量的值 = ``b[i]``，非基变量 = 0。

详见 docs/principles/simplex.md。
"""

from __future__ import annotations

import math

from ..constants import LpConstraintSense, LpSense, LpStatus
from ..problem import LpProblem
from .base import LpSolver

_EPS = 1e-9


def _is_zero(x: float) -> bool:
    return abs(x) < _EPS


class SimplexCore(LpSolver):
    """纯 Python 两阶段单纯形法求解器。

    教学定位：代码透明、零依赖、可逐步跟踪。
    适合小规模 LP（变量数 < 100）。大规模问题请用 CBC/GLPK。

    Examples
    --------
    >>> import minipulp as mp
    >>> from minipulp.solvers import SimplexCore
    >>> x = mp.LpVariable("x", lowBound=0)
    >>> prob = mp.LpProblem("demo", mp.LpMaximize)
    >>> prob += 3 * x
    >>> prob += x <= 10
    >>> prob.solve(solver=SimplexCore())
    >>> x.varValue
    10.0
    """

    name = "SimplexCore"

    def __init__(self, verbose: bool = False) -> None:
        super().__init__()
        self.verbose = verbose

    def available(self) -> bool:
        return True

    def actualSolve(self, problem: LpProblem) -> LpStatus:
        if not problem.valid():
            raise ValueError("问题未设置目标函数")

        std = self._extract(problem)
        if std is None:
            return LpStatus.INFEASIBLE

        status, solution = self._solve(std)
        self._backfill(std, status, solution)
        return status

    def _extract(self, problem: LpProblem) -> dict | None:
        """从 LpProblem 提取矩阵表示并做变量平移。

        返回 dict 包含标准化后的 cost(rows)、A、b、约束方向、
        变量平移量 shifts、原始变量列表。
        """
        var_list = problem.variables()
        n = len(var_list)
        if n == 0:
            return None
        var_index = {var: i for i, var in enumerate(var_list)}

        cost = [0.0] * n
        obj = problem.objective
        for var, coef in obj.terms.items():
            cost[var_index[var]] = float(coef)
        if problem.sense == LpSense.MAXIMIZE:
            cost = [-c for c in cost]

        rows = []
        rhs = []
        senses = []
        for con in problem.constraints.values():
            row = [0.0] * n
            for var, coef in con.terms.items():
                row[var_index[var]] = float(coef)
            rows.append(row)
            rhs.append(float(-con.constant))
            senses.append(con.sense)

        shifts = [0.0] * n
        for i, var in enumerate(var_list):
            lb = var.lowBound
            if lb is not None:
                shifts[i] = float(lb)
                for r in range(len(rows)):
                    rhs[r] -= rows[r][i] * shifts[i]

        for i, var in enumerate(var_list):
            ub = var.upBound
            if ub is not None:
                row = [0.0] * n
                row[i] = 1.0
                rows.append(row)
                rhs.append(float(ub) - shifts[i])
                senses.append(LpConstraintSense.LE)

        return {
            "cost": cost,
            "rows": rows,
            "rhs": rhs,
            "senses": senses,
            "n": n,
            "shifts": shifts,
            "var_list": var_list,
        }

    def _solve(self, std: dict) -> tuple[LpStatus, list[float]]:
        """两阶段单纯形主流程，返回 (状态, 解向量)。"""
        cost = std["cost"]
        rows = std["rows"]
        rhs = std["rhs"]
        senses = std["senses"]
        n = std["n"]
        m = len(rows)

        if m == 0:
            return self._solve_no_constraints(std)

        A, b, basis, n_total, artificial_cols = self._build_tableau(
            rows, rhs, senses, n, m
        )

        if artificial_cols:
            phase1_cost = [0.0] * n_total
            for j in artificial_cols:
                phase1_cost[j] = 1.0

            status = self._simplex_loop(A, b, phase1_cost, basis, n_total, m)
            if status != LpStatus.OPTIMAL:
                return status, [0.0] * n

            art_value = sum(b[i] for i in range(m) if basis[i] in artificial_cols)
            if art_value > _EPS:
                return LpStatus.INFEASIBLE, [0.0] * n

            art_set = set(artificial_cols)
            for i in range(m):
                if basis[i] in art_set:
                    for j in range(n_total):
                        if j in art_set:
                            continue
                        if abs(A[i][j]) > _EPS:
                            self._pivot(A, b, i, j, m, n_total)
                            basis[i] = j
                            break

            for j in artificial_cols:
                for i in range(m):
                    A[i][j] = 0.0

        full_cost = [0.0] * n_total
        for j in range(n):
            full_cost[j] = cost[j]

        status = self._simplex_loop(A, b, full_cost, basis, n_total, m)
        if status != LpStatus.OPTIMAL:
            return status, [0.0] * n

        solution = [0.0] * n_total
        for i in range(m):
            solution[basis[i]] = b[i]
        return status, solution[:n]

    def _build_tableau(
        self,
        rows: list[list[float]],
        rhs: list[float],
        senses: list,
        n: int,
        m: int,
    ) -> tuple:
        """构造含松弛/剩余/人工变量的扩充矩阵与初始基。

        返回 (A, b, basis, n_total, artificial_cols)。

        预处理：若 ``b[i] < 0``，将该行乘以 -1 并翻转约束方向，
        保证右端项非负（单纯形法的要求）。
        """
        A = [list(r) for r in rows]
        b = list(rhs)
        senses = list(senses)

        for i in range(m):
            if b[i] < -_EPS:
                for j in range(n):
                    A[i][j] = -A[i][j]
                b[i] = -b[i]
                if senses[i] == LpConstraintSense.LE:
                    senses[i] = LpConstraintSense.GE
                elif senses[i] == LpConstraintSense.GE:
                    senses[i] = LpConstraintSense.LE

        n_total = n
        basis = [-1] * m
        artificial_cols = []

        for i in range(m):
            sense = senses[i]
            if sense == LpConstraintSense.LE:
                col = n_total
                for r in range(m):
                    A[r].append(1.0 if r == i else 0.0)
                basis[i] = col
                n_total += 1
            elif sense == LpConstraintSense.GE:
                col_surplus = n_total
                for r in range(m):
                    A[r].append(-1.0 if r == i else 0.0)
                n_total += 1
                col_art = n_total
                for r in range(m):
                    A[r].append(1.0 if r == i else 0.0)
                basis[i] = col_art
                artificial_cols.append(col_art)
                n_total += 1
            else:
                col_art = n_total
                for r in range(m):
                    A[r].append(1.0 if r == i else 0.0)
                basis[i] = col_art
                artificial_cols.append(col_art)
                n_total += 1

        return A, b, basis, n_total, artificial_cols

    def _simplex_loop(
        self,
        A: list[list[float]],
        b: list[float],
        cost: list[float],
        basis: list[int],
        n_total: int,
        m: int,
    ) -> LpStatus:
        """单纯形主循环。

        每次迭代：
        1. 算检验数 ``reduced[j] = cost[j] - sum(c_basis[i]*A[i][j])``
        2. 选进基列：第一个 ``reduced[j] < 0``（Bland 规则，避免循环）
        3. 选离基行：最小比值 ``b[i]/A[i][j]``（``A[i][j] > 0``）
        4. 无 ``A[i][j] > 0`` 则无界
        5. 转轴：主元行归一化，其余行消元
        """
        max_iter = 10000
        for _ in range(max_iter):
            c_basis = [cost[basis[i]] for i in range(m)]

            pivot_col = -1
            for j in range(n_total):
                reduced = cost[j] - sum(c_basis[i] * A[i][j] for i in range(m))
                if reduced < -_EPS:
                    pivot_col = j
                    break
            if pivot_col == -1:
                return LpStatus.OPTIMAL

            pivot_row = -1
            min_ratio = math.inf
            for i in range(m):
                if A[i][pivot_col] > _EPS:
                    ratio = b[i] / A[i][pivot_col]
                    if ratio < min_ratio - _EPS:
                        min_ratio = ratio
                        pivot_row = i
            if pivot_row == -1:
                return LpStatus.UNBOUNDED

            self._pivot(A, b, pivot_row, pivot_col, m, n_total)
            basis[pivot_row] = pivot_col

        return LpStatus.UNDEFINED

    def _pivot(
        self,
        A: list[list[float]],
        b: list[float],
        pr: int,
        pc: int,
        m: int,
        n_total: int,
    ) -> None:
        """转轴：以 A[pr][pc] 为主元归一化主元行，消元其余行。"""
        pivot_val = A[pr][pc]
        for j in range(n_total):
            A[pr][j] /= pivot_val
        b[pr] /= pivot_val

        for i in range(m):
            if i == pr:
                continue
            factor = A[i][pc]
            if _is_zero(factor):
                continue
            for j in range(n_total):
                A[i][j] -= factor * A[pr][j]
            b[i] -= factor * b[pr]

    def _solve_no_constraints(self, std: dict) -> tuple[LpStatus, list[float]]:
        """无约束问题：目标系数全 0 则任意解最优，否则无界。"""
        cost = std["cost"]
        n = std["n"]
        for c in cost:
            if abs(c) > _EPS:
                return LpStatus.UNBOUNDED, [0.0] * n
        return LpStatus.OPTIMAL, [0.0] * n

    def _backfill(self, std: dict, status: LpStatus, solution: list[float]) -> None:
        """把解值写回 LpVariable.varValue（加上平移量 shifts）。"""
        var_list = std["var_list"]
        shifts = std["shifts"]

        if status != LpStatus.OPTIMAL:
            for var in var_list:
                var.varValue = None
            return

        for i, var in enumerate(var_list):
            var.varValue = solution[i] + shifts[i]
