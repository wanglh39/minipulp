"""高级功能测试：批量变量、矩阵变量、lpSum 优化、运输问题。

镜像 src/minipulp/elements.py 的新增 API。
"""

import pytest

import minipulp as mp
from minipulp import LpVariable, lpSum
from minipulp.solvers import SimplexCore


class TestVariableDicts:
    """LpVariable.dicts 批量创建变量字典。"""

    def test_basic_dicts(self):
        x = LpVariable.dicts("x", range(3), lowBound=0)
        assert len(x) == 3
        assert x[0].name == "x_0"
        assert x[1].name == "x_1"
        assert x[2].name == "x_2"

    def test_dicts_bounds(self):
        x = LpVariable.dicts("x", range(2), lowBound=0, upBound=10)
        assert x[0].lowBound == 0
        assert x[0].upBound == 10

    def test_dicts_integer(self):
        x = LpVariable.dicts("x", range(2), cat=mp.LpInteger)
        assert x[0].cat == mp.LpInteger

    def test_dicts_with_string_indices(self):
        x = LpVariable.dicts("x", ["a", "b", "c"], lowBound=0)
        assert x["a"].name == "x_a"
        assert x["c"].name == "x_c"

    def test_dicts_in_problem(self):
        x = LpVariable.dicts("x", range(3), lowBound=0)
        prob = mp.LpProblem("p", mp.LpMaximize)
        prob += lpSum(x[i] for i in range(3))
        prob += lpSum(x[i] for i in range(3)) <= 10
        prob.solve(solver=SimplexCore())
        assert prob.status == mp.LpStatusOptimal
        assert pytest.approx(sum(x[i].varValue for i in range(3)), abs=1e-6) == 10.0


class TestVariableMatrix:
    """LpVariable.matrix 二维变量矩阵。"""

    def test_basic_matrix(self):
        x = LpVariable.matrix("x", range(2), range(3), lowBound=0)
        assert len(x) == 2
        assert len(x[0]) == 3
        assert x[0][0].name == "x_0_0"
        assert x[1][2].name == "x_1_2"

    def test_matrix_bounds(self):
        x = LpVariable.matrix("x", range(2), range(2), lowBound=0, upBound=5)
        assert x[0][0].lowBound == 0
        assert x[1][1].upBound == 5


class TestLpSumOptimized:
    """lpSum 优化版本：直接合并字典。"""

    def test_lpsum_merge(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = lpSum([3 * x, 2 * y, 5])
        assert expr.terms == {x: 3.0, y: 2.0}
        assert expr.const == 5.0

    def test_lpsum_with_dict_vars(self):
        x = LpVariable.dicts("x", range(4), lowBound=0)
        expr = lpSum(x[i] for i in range(4))
        assert len(expr.terms) == 4
        for i in range(4):
            assert x[i] in expr.terms
            assert expr.terms[x[i]] == 1.0

    def test_lpsum_coefficients(self):
        x = LpVariable.dicts("x", range(3), lowBound=0)
        costs = [3, 2, 5]
        expr = lpSum(costs[i] * x[i] for i in range(3))
        assert expr.terms[x[0]] == 3.0
        assert expr.terms[x[1]] == 2.0
        assert expr.terms[x[2]] == 5.0

    def test_lpsum_empty(self):
        expr = lpSum([])
        assert expr.terms == {}
        assert expr.const == 0.0


class TestTransportationProblem:
    """经典运输问题：批量变量的实际用途。

    2 个供应点，3 个需求点：

        供应: A=30, B=40
        需求: 1=20, 2=30, 3=20
        成本:
            A→1: 2, A→2: 3, A→3: 4
            B→1: 3, B→2: 2, B→3: 1

    最小化总运输成本。
    """

    def test_transportation(self):
        supply = {"A": 30, "B": 40}
        demand = {1: 20, 2: 30, 3: 20}
        cost = {
            ("A", 1): 2, ("A", 2): 3, ("A", 3): 4,
            ("B", 1): 3, ("B", 2): 2, ("B", 3): 1,
        }

        x = {}
        for s in supply:
            for d in demand:
                x[(s, d)] = LpVariable(f"x_{s}_{d}", lowBound=0)

        prob = mp.LpProblem("transport", mp.LpMinimize)
        prob += lpSum(cost[(s, d)] * x[(s, d)] for s in supply for d in demand)

        for s in supply:
            prob += lpSum(x[(s, d)] for d in demand) <= supply[s]

        for d in demand:
            prob += lpSum(x[(s, d)] for s in supply) >= demand[d]

        prob.solve(solver=SimplexCore())
        assert prob.status == mp.LpStatusOptimal

        total = sum(x[(s, d)].varValue for s in supply for d in demand)
        assert pytest.approx(total, abs=1e-6) == 70.0

        for d in demand:
            delivered = sum(x[(s, d)].varValue for s in supply)
            assert pytest.approx(delivered, abs=1e-6) == demand[d]