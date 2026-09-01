"""表达式系统测试 — 运算符重载的核心行为。

镜像 src/minipulp/elements.py，按"构造 → 运算 → 约束 → 边界"组织。
"""

import pytest

import minipulp as mp
from minipulp import LpAffineExpression, LpConstraint, LpVariable, lpSum
from minipulp.constants import LpConstraintSense


class TestVariableConstruction:
    """变量构造与属性。"""

    def test_basic_variable(self):
        x = LpVariable("x")
        assert x.name == "x"
        assert x.lowBound is None
        assert x.upBound is None
        assert x.cat == mp.LpContinuous
        assert x.varValue is None

    def test_bounded_variable(self):
        x = LpVariable("x", lowBound=0, upBound=10)
        assert x.lowBound == 0
        assert x.upBound == 10

    def test_integer_variable(self):
        x = LpVariable("x", cat=mp.LpInteger)
        assert x.cat == mp.LpInteger

    def test_binary_variable(self):
        x = LpVariable("x", cat=mp.LpBinary)
        assert x.cat == mp.LpBinary

    def test_variable_is_single_term_expression(self):
        """变量在数学上是 {self: 1} 的单变量表达式。"""
        x = LpVariable("x")
        assert x.terms == {x: 1.0}
        assert x.const == 0.0

    def test_variable_hashable_by_name(self):
        """变量可作字典 key，hash 基于 name。"""
        x = LpVariable("x")
        d = {x: 3.0}
        assert d[x] == 3.0


class TestScalarMultiplication:
    """标量乘法：3 * x 与 x * 3 都应得到 {x: 3}。"""

    def test_rmul_left_scalar(self):
        """3 * x：int.__mul__(x) 失败，回退到 x.__rmul__(3)。"""
        x = LpVariable("x")
        expr = 3 * x
        assert isinstance(expr, LpAffineExpression)
        assert expr.terms == {x: 3.0}
        assert expr.const == 0.0

    def test_mul_right_scalar(self):
        """x * 3：直接调 x.__mul__(3)。"""
        x = LpVariable("x")
        expr = x * 3
        assert expr.terms == {x: 3.0}

    def test_mul_float(self):
        x = LpVariable("x")
        expr = 2.5 * x
        assert expr.terms == {x: 2.5}

    def test_mul_zero(self):
        x = LpVariable("x")
        expr = 0 * x
        assert expr.terms == {}
        assert expr.const == 0.0

    def test_mul_negative(self):
        x = LpVariable("x")
        expr = -3 * x
        assert expr.terms == {x: -3.0}

    def test_mul_variable_raises(self):
        """两个变量相乘是非线性的，必须报错。"""
        x = LpVariable("x")
        y = LpVariable("y")
        with pytest.raises(TypeError, match="非线性"):
            x * y


class TestAddition:
    """加法：表达式合并。"""

    def test_add_two_variables(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = x + y
        assert expr.terms == {x: 1.0, y: 1.0}
        assert expr.const == 0.0

    def test_add_scalar(self):
        x = LpVariable("x")
        expr = x + 5
        assert expr.terms == {x: 1.0}
        assert expr.const == 5.0

    def test_radd_scalar(self):
        x = LpVariable("x")
        expr = 5 + x
        assert expr.terms == {x: 1.0}
        assert expr.const == 5.0

    def test_add_expressions(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = (3 * x + 2 * y) + (x + 4 * y)
        assert expr.terms == {x: 4.0, y: 6.0}

    def test_add_cancels_to_zero(self):
        """x - x 应消去变量项，只剩常数。"""
        x = LpVariable("x")
        expr = x + (-1 * x)
        assert expr.terms == {}
        assert expr.const == 0.0


class TestSubtraction:
    """减法。"""

    def test_sub_two_variables(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = x - y
        assert expr.terms == {x: 1.0, y: -1.0}

    def test_sub_scalar(self):
        x = LpVariable("x")
        expr = x - 5
        assert expr.terms == {x: 1.0}
        assert expr.const == -5.0

    def test_rsub_scalar(self):
        """5 - x → {-x: 1} + 5。"""
        x = LpVariable("x")
        expr = 5 - x
        assert expr.terms == {x: -1.0}
        assert expr.const == 5.0

    def test_sub_expressions(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = (3 * x + 2 * y) - (x + y)
        assert expr.terms == {x: 2.0, y: 1.0}


class TestDivisionAndNegation:
    """除法与取负。"""

    def test_truediv_scalar(self):
        x = LpVariable("x")
        expr = x / 4
        assert expr.terms == {x: 0.25}

    def test_truediv_zero_raises(self):
        x = LpVariable("x")
        with pytest.raises(ZeroDivisionError):
            x / 0

    def test_neg(self):
        x = LpVariable("x")
        expr = -x
        assert expr.terms == {x: -1.0}

    def test_neg_expression_with_const(self):
        x = LpVariable("x")
        expr = -(3 * x + 5)
        assert expr.terms == {x: -3.0}
        assert expr.const == -5.0


class TestComplexExpression:
    """复合表达式构造：模拟真实建模场景。"""

    def test_linear_combination(self):
        x = LpVariable("x")
        y = LpVariable("y")
        z = LpVariable("z")
        expr = 3 * x + 2 * y - z + 10
        assert expr.terms == {x: 3.0, y: 2.0, z: -1.0}
        assert expr.const == 10.0

    def test_repeated_addition_accumulates(self):
        x = LpVariable("x")
        expr = 3 * x
        expr = expr + 2 * x
        expr = expr + x
        assert expr.terms == {x: 6.0}

    def test_scalar_mul_distributes(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = 2 * (3 * x + 4 * y)
        assert expr.terms == {x: 6.0, y: 8.0}

    def test_is_constant(self):
        x = LpVariable("x")
        assert not (3 * x).is_constant()
        assert LpAffineExpression({}, 5).is_constant()


class TestConstraintConstruction:
    """约束构造：<=, >=, == 运算符。"""

    def test_le_constraint(self):
        x = LpVariable("x")
        c = x <= 5
        assert isinstance(c, LpConstraint)
        assert c.sense == LpConstraintSense.LE
        assert c.terms == {x: 1.0}
        assert c.constant == -5.0

    def test_ge_constraint(self):
        x = LpVariable("x")
        c = x >= 3
        assert c.sense == LpConstraintSense.GE
        assert c.constant == -3.0

    def test_eq_constraint(self):
        x = LpVariable("x")
        y = LpVariable("y")
        c = x + y == 10
        assert c.sense == LpConstraintSense.EQ
        assert c.terms == {x: 1.0, y: 1.0}
        assert c.constant == -10.0

    def test_complex_constraint(self):
        """3*x + 2*y <= 100 归一化为 3*x + 2*y - 100 <= 0。"""
        x = LpVariable("x")
        y = LpVariable("y")
        c = 3 * x + 2 * y <= 100
        assert c.sense == LpConstraintSense.LE
        assert c.terms == {x: 3.0, y: 2.0}
        assert c.constant == -100.0

    def test_constraint_repr(self):
        x = LpVariable("x")
        c = x <= 5
        assert "<=" in repr(c)


class TestLpSum:
    """lpSum 批量求和。"""

    def test_lpsum_basic(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = lpSum([3 * x, 2 * y, 5])
        assert expr.terms == {x: 3.0, y: 2.0}
        assert expr.const == 5.0

    def test_lpsum_empty(self):
        expr = lpSum([])
        assert expr.terms == {}
        assert expr.const == 0.0

    def test_lpsum_single(self):
        x = LpVariable("x")
        expr = lpSum([3 * x])
        assert expr.terms == {x: 3.0}


class TestValueEvaluation:
    """value() 方法在变量已求解时计算表达式值。"""

    def test_value_with_solved_vars(self):
        x = LpVariable("x")
        y = LpVariable("y")
        x.varValue = 10.0
        y.varValue = 20.0
        expr = 3 * x + 2 * y + 5
        assert expr.value() == 75.0

    def test_value_with_unsolved_vars(self):
        x = LpVariable("x")
        expr = 3 * x
        assert expr.value() is None

    def test_value_of_constant(self):
        expr = LpAffineExpression({}, 42.0)
        assert expr.value() == 42.0


class TestRepr:
    """字符串表示。"""

    def test_variable_repr(self):
        x = LpVariable("x")
        assert repr(x) == "x"

    def test_expression_repr(self):
        x = LpVariable("x")
        y = LpVariable("y")
        expr = 3 * x + 2 * y + 5
        r = repr(expr)
        assert "x" in r and "y" in r and "5.0" in r

    def test_unit_coefficient_repr(self):
        x = LpVariable("x")
        expr = x + 5
        assert "1.0*" not in repr(expr)