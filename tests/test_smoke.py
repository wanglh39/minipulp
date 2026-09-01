"""冒烟测试：验证包可导入、公开 API 齐全。

镜像 src/minipulp/__init__.py 的导出。
"""
import minipulp as mp


def test_package_importable():
    assert mp.__version__ == "0.1.0"


def test_public_api_exists():
    expected = [
        "LpVariable", "LpAffineExpression", "LpElement",
        "LpConstraint", "LpProblem",
        "LpMinimize", "LpMaximize", "LpSense",
        "LpContinuous", "LpInteger", "LpBinary", "LpCat",
        "LpStatus", "LpStatusOptimal", "LpStatusInfeasible",
        "LpStatusUnbounded", "LpStatusNotSolved",
    ]
    for name in expected:
        assert hasattr(mp, name), f"missing public API: {name}"


def test_variable_construction():
    x = mp.LpVariable("x", lowBound=0, upBound=10)
    assert x.name == "x"
    assert x.lowBound == 0
    assert x.upBound == 10
    assert x.cat == mp.LpContinuous
    assert x.varValue is None


def test_problem_construction():
    prob = mp.LpProblem("demo", mp.LpMaximize)
    assert prob.name == "demo"
    assert prob.sense == mp.LpMaximize
    assert prob.status == mp.LpStatusNotSolved
    assert prob.status_msg == "Not Solved"