"""LpProblem 测试 — 问题容器的建模行为。

镜像 src/minipulp/problem.py。
"""

import pytest

import minipulp as mp
from minipulp import LpConstraint, LpProblem, LpVariable


class TestProblemConstruction:
    def test_default_construction(self):
        prob = LpProblem()
        assert prob.name == "problem"
        assert prob.sense == mp.LpMinimize
        assert prob.objective is None
        assert prob.constraints == {}
        assert prob.status == mp.LpStatusNotSolved

    def test_maximize_problem(self):
        prob = LpProblem("demo", mp.LpMaximize)
        assert prob.sense == mp.LpMaximize

    def test_status_msg(self):
        prob = LpProblem()
        assert prob.status_msg == "Not Solved"


class TestIaddSyntax:
    """+= 语法糖：表达式→目标，约束→添加约束。"""

    def test_iadd_sets_objective(self):
        x = LpVariable("x")
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x + 2 * x
        assert prob.objective is not None
        assert prob.objective.terms == {x: 5.0}

    def test_iadd_adds_constraint(self):
        x = LpVariable("x")
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x
        prob += x <= 10
        assert len(prob.constraints) == 1

    def test_iadd_mixed(self):
        x = LpVariable("x")
        y = LpVariable("y")
        prob = LpProblem("demo", mp.LpMaximize)
        prob += 3 * x + 2 * y
        prob += 2 * x + y <= 100
        prob += x + y <= 80
        prob += x <= 40
        assert prob.objective.terms == {x: 3.0, y: 2.0}
        assert len(prob.constraints) == 3

    def test_iadd_variable_as_objective(self):
        x = LpVariable("x")
        prob = LpProblem("demo", mp.LpMaximize)
        prob += x
        assert prob.objective.terms == {x: 1.0}

    def test_iadd_invalid_type(self):
        prob = LpProblem("demo")
        with pytest.raises(TypeError):
            prob += "not an expression"


class TestVariableCollection:
    """问题自动收集变量。"""

    def test_variables_collected_from_objective(self):
        x = LpVariable("x")
        y = LpVariable("y")
        prob = LpProblem("demo")
        prob += 3 * x + 2 * y
        names = {v.name for v in prob.variables()}
        assert names == {"x", "y"}

    def test_variables_collected_from_constraints(self):
        x = LpVariable("x")
        y = LpVariable("y")
        z = LpVariable("z")
        prob = LpProblem("demo")
        prob += x
        prob += x + y <= 10
        prob += y + z >= 5
        names = {v.name for v in prob.variables()}
        assert names == {"x", "y", "z"}

    def test_no_duplicate_variables(self):
        x = LpVariable("x")
        prob = LpProblem("demo")
        prob += x
        prob += x <= 10
        prob += x >= 0
        assert prob.numVariables() == 1

    def test_num_helpers(self):
        x = LpVariable("x")
        y = LpVariable("y")
        prob = LpProblem("demo")
        prob += x + y
        prob += x <= 10
        assert prob.numVariables() == 2
        assert prob.numConstraints() == 1


class TestConstraintNaming:
    def test_auto_constraint_name(self):
        x = LpVariable("x")
        prob = LpProblem("demo")
        prob += x
        prob += x <= 10
        prob += x >= 0
        names = list(prob.constraints.keys())
        assert names == ["c_0", "c_1"]

    def test_explicit_constraint_name(self):
        x = LpVariable("x")
        prob = LpProblem("demo")
        prob += x
        con = x <= 10
        prob.addConstraint(con, name="capacity")
        assert "capacity" in prob.constraints


class TestValidation:
    def test_valid_without_objective(self):
        prob = LpProblem("demo")
        assert not prob.valid()

    def test_valid_with_objective(self):
        x = LpVariable("x")
        prob = LpProblem("demo")
        prob += x
        assert prob.valid()


class TestSolve:
    def test_solve_with_default_solver(self):
        x = LpVariable("x", lowBound=0)
        prob = LpProblem("demo", mp.LpMaximize)
        prob += x
        prob += x <= 10
        status = prob.solve()
        assert status == mp.LpStatusOptimal
        assert x.varValue == 10.0