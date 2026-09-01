"""纯 Python 单纯形法求解器测试。

镜像 src/minipulp/solvers/simplex_py.py。
用经典 LP 问题验证算法正确性。
"""

import pytest

import minipulp as mp
from minipulp import LpProblem, LpVariable
from minipulp.solvers import SimplexCore


def solve(prob):
    return prob.solve(solver=SimplexCore())


class TestBasicSolve:
    """基础求解：单变量问题。"""

    def test_maximize_single_var(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += 3 * x
        prob += x <= 10
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(10.0)

    def test_minimize_single_var(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("p", mp.LpMinimize)
        prob += 3 * x
        prob += x >= 5
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(5.0)

    def test_variable_lower_bound(self):
        x = LpVariable("x", lowBound=2)
        prob = LpProblem("p", mp.LpMinimize)
        prob += x
        prob += x >= 0
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(2.0)

    def test_variable_upper_bound(self):
        x = LpVariable("x", lowBound=0, upBound=10)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(10.0)


class TestProductionPlan:
    """经典生产计划问题：

        max  3x + 2y
        s.t. 2x + y <= 100
             x + y <= 80
             x    <= 40
             x, y >= 0

    最优解：x=20, y=60, obj=180
    """

    def test_production_plan(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("production", mp.LpMaximize)
        prob += 3 * x + 2 * y
        prob += 2 * x + y <= 100
        prob += x + y <= 80
        prob += x <= 40

        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(20.0, abs=1e-6)
        assert y.varValue == pytest.approx(60.0, abs=1e-6)
        assert prob.objective.value() == pytest.approx(180.0, abs=1e-6)


class TestEqualityConstraint:
    """等式约束。"""

    def test_equality(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x + y
        prob += x + y == 10
        prob += x <= 4
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(4.0, abs=1e-6)
        assert y.varValue == pytest.approx(6.0, abs=1e-6)


class TestGeConstraint:
    """>= 约束（需要剩余变量 + 人工变量）。"""

    def test_ge_constraint(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("p", mp.LpMinimize)
        prob += x
        prob += x >= 5
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(5.0, abs=1e-6)

    def test_mixed_constraints(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += 2 * x + y
        prob += x + y <= 10
        prob += x - y >= 2
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue + y.varValue == pytest.approx(10.0, abs=1e-6)
        assert x.varValue - y.varValue >= 2.0 - 1e-6
        assert prob.objective.value() == pytest.approx(20.0, abs=1e-6)


class TestInfeasible:
    """不可行问题。"""

    def test_infeasible_bounds(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x
        prob += x <= 5
        prob += x >= 10
        assert solve(prob) == mp.LpStatusInfeasible
        assert x.varValue is None

    def test_infeasible_equality(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x
        prob += x + y == 10
        prob += x + y == 20
        assert solve(prob) == mp.LpStatusInfeasible


class TestUnbounded:
    """无界问题。"""

    def test_unbounded_maximize(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x
        assert solve(prob) == mp.LpStatusUnbounded


class TestDietProblem:
    """经典饮食问题（最小化成本满足营养需求）。

    两种食物，两种营养：
        min  2x + 3y
        s.t. 3x + 1y >= 6   (营养 A)
             1x + 2y >= 4   (营养 B)
             x, y >= 0

    最优解：x=1.6, y=1.2, obj=6.8
    """

    def test_diet_problem(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("diet", mp.LpMinimize)
        prob += 2 * x + 3 * y
        prob += 3 * x + y >= 6
        prob += x + 2 * y >= 4
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(1.6, abs=1e-6)
        assert y.varValue == pytest.approx(1.2, abs=1e-6)
        assert prob.objective.value() == pytest.approx(6.8, abs=1e-6)


class TestSolverInterface:
    """求解器接口行为。"""

    def test_available(self):
        solver = SimplexCore()
        assert solver.available() is True

    def test_name(self):
        assert SimplexCore().name == "SimplexCore"

    def test_solve_without_objective_raises(self):
        prob = LpProblem("p")
        with pytest.raises(ValueError, match="目标函数"):
            prob.solve(solver=SimplexCore())