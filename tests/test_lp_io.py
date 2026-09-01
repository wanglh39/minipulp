"""LP 文件格式导出测试。

镜像 src/minipulp/lp_io.py。
"""

import pytest

import minipulp as mp
from minipulp import LpProblem, LpVariable, write_lp


class TestWriteLpBasic:
    def test_minimize_problem(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo", mp.LpMinimize)
        prob += 3 * x
        lp = write_lp(prob)
        assert "Minimize" in lp
        assert "obj: 3 x" in lp
        assert "End" in lp

    def test_maximize_problem(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x
        lp = write_lp(prob)
        assert "Maximize" in lp

    def test_problem_name_in_header(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("my_problem", mp.LpMinimize)
        prob += x
        lp = write_lp(prob)
        assert "my_problem" in lp

    def test_no_objective_raises(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo")
        with pytest.raises(ValueError, match="目标函数"):
            write_lp(prob)


class TestWriteLpObjective:
    def test_multi_var_objective(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x + 2 * y
        lp = write_lp(prob)
        assert "3 x" in lp
        assert "2 y" in lp

    def test_objective_with_constant(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x + 10
        lp = write_lp(prob)
        assert "10" in lp


class TestWriteLpConstraints:
    def test_le_constraint(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo")
        prob += x
        prob += 2 * x <= 100
        lp = write_lp(prob)
        assert "Subject To" in lp
        assert "<=" in lp
        assert "100" in lp

    def test_ge_constraint(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo")
        prob += x
        prob += x >= 5
        lp = write_lp(prob)
        assert ">=" in lp
        assert "5" in lp

    def test_eq_constraint(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo")
        prob += x
        prob += x == 10
        lp = write_lp(prob)
        assert "=" in lp

    def test_constraint_name(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo")
        prob += x
        prob += x <= 10
        lp = write_lp(prob)
        assert "c_0" in lp

    def test_multi_constraints(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x + 2 * y
        prob += 2 * x + y <= 100
        prob += x + y <= 80
        prob += x <= 40
        lp = write_lp(prob)
        assert "c_0" in lp
        assert "c_1" in lp
        assert "c_2" in lp


class TestWriteLpBounds:
    def test_lower_bound(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo")
        prob += x
        lp = write_lp(prob)
        assert "Bounds" in lp
        assert "x >= 0" in lp

    def test_upper_bound(self):
        x = LpVariable("x", upBound=10)
        prob = LpProblem("demo")
        prob += x
        lp = write_lp(prob)
        assert "x <= 10" in lp

    def test_both_bounds(self):
        x = LpVariable("x", lowBound=0, upBound=10)
        prob = LpProblem("demo")
        prob += x
        lp = write_lp(prob)
        assert "0 <= x <= 10" in lp

    def test_free_variable(self):
        x = LpVariable("x")
        prob = LpProblem("demo")
        prob += x
        lp = write_lp(prob)
        assert "x free" in lp


class TestWriteLpIntegerBinary:
    def test_integer_variable(self):
        x = LpVariable("x", lowBound=0, cat=mp.LpInteger)
        prob = LpProblem("demo")
        prob += x
        lp = write_lp(prob)
        assert "General" in lp
        assert "x" in lp

    def test_binary_variable(self):
        x = LpVariable("x", cat=mp.LpBinary)
        prob = LpProblem("demo")
        prob += x
        lp = write_lp(prob)
        assert "Binary" in lp


class TestWriteLpComplete:
    def test_full_problem(self):
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x + 2 * y
        prob += 2 * x + y <= 100
        prob += x + y <= 80
        prob += x <= 40

        lp = write_lp(prob)
        lines = lp.split("\n")

        assert lines[0].startswith("\\ Problem name: demo")
        assert "Maximize" in lp
        assert "Subject To" in lp
        assert "Bounds" in lp
        assert lp.endswith("End")

        assert "3 x" in lp
        assert "2 y" in lp
        assert "100" in lp
        assert "80" in lp
        assert "40" in lp