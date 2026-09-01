"""CBC 命令行求解器测试。

镜像 src/minipulp/solvers/cbc_cmd.py。
需要 cbc 可执行文件在 PATH 中。
"""

import shutil

import pytest

import minipulp as mp
from minipulp import LpProblem, LpVariable
from minipulp.solvers import PULP_CBC_CMD

pytestmark = pytest.mark.skipif(
    shutil.which("cbc") is None,
    reason="cbc not found in PATH",
)


def solve(prob, **kwargs):
    return prob.solve(solver=PULP_CBC_CMD(**kwargs))


class TestCBCAvailability:
    def test_available(self):
        solver = PULP_CBC_CMD()
        assert solver.available()


class TestCBCBasic:
    def test_maximize(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += 3 * x + 2 * y
        prob += 2 * x + y <= 100
        prob += x + y <= 80
        prob += x <= 40
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(20.0, abs=1e-4)
        assert y.varValue == pytest.approx(60.0, abs=1e-4)
        assert prob.objective.value() == pytest.approx(180.0, abs=1e-4)

    def test_minimize(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("p", mp.LpMinimize)
        prob += 2 * x + 3 * y
        prob += 3 * x + y >= 6
        prob += x + 2 * y >= 4
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(1.6, abs=1e-4)
        assert y.varValue == pytest.approx(1.2, abs=1e-4)


class TestCBCInteger:
    """CBC 支持整数规划（这是它相比 SimplexCore 的优势）。"""

    def test_integer_variable(self):
        x = LpVariable("x", lowBound=0, cat=mp.LpInteger)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x
        prob += x <= 10.5
        assert solve(prob) == mp.LpStatusOptimal
        assert x.varValue == pytest.approx(10.0, abs=1e-4)

    def test_binary_variable(self):
        x = LpVariable("x", cat=mp.LpBinary)
        y = LpVariable("y", cat=mp.LpBinary)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x + y
        prob += x + y <= 1
        assert solve(prob) == mp.LpStatusOptimal
        assert prob.objective.value() == pytest.approx(1.0, abs=1e-4)


class TestCBCInfeasible:
    def test_infeasible(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("p", mp.LpMaximize)
        prob += x
        prob += x <= 5
        prob += x >= 10
        status = solve(prob)
        assert status in (mp.LpStatusInfeasible, mp.LpStatusNotSolved)


class TestCBCSolverInterface:
    def test_name(self):
        assert PULP_CBC_CMD().name == "PULP_CBC_CMD"

    def test_custom_path(self):
        path = shutil.which("cbc")
        solver = PULP_CBC_CMD(path=path)
        assert solver.available()