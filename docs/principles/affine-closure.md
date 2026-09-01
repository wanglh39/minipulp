# 仿射表达式的闭包性

> 原则三的数学基础：为什么一个 `{var: coef}` 字典就够了？

---

## 什么是仿射表达式

仿射表达式是变量的一次齐次多项式加常数：

$$
f(x_1, \ldots, x_n) = c_1 x_1 + c_2 x_2 + \cdots + c_n x_n + b
$$

特例：

- 常数 $b$ 是仿射表达式（所有 $c_i = 0$）
- 变量 $x$ 是仿射表达式（$c_1 = 1$，其余为 0，$b = 0$）
- $3x + 2y + 5$ 是仿射表达式

---

## 闭包性

**仿射表达式在加法和数乘下封闭**：

$$
\alpha \cdot f(x) + \beta \cdot g(x) = \text{仿射表达式}
$$

证明：设 $f = \sum c_i x_i + b$，$g = \sum d_i x_i + e$，则

$$
\alpha f + \beta g = \sum (\alpha c_i + \beta d_i) x_i + (\alpha b + \beta e)
$$

系数 $\alpha c_i + \beta d_i$ 和常数 $\alpha b + \beta e$ 都是标量，结果仍是仿射表达式。$\blacksquare$

---

## 为什么这很重要

闭包性意味着：**无论怎么线性组合，结果永远是一个字典 + 一个常数**。

```
变量 x          → {x: 1},  const=0
3 * x           → {x: 3},  const=0
3*x + 2*y       → {x: 3, y: 2},  const=0
3*x + 2*y + 5   → {x: 3, y: 2},  const=5
2*(3*x + 2*y)   → {x: 6, y: 4},  const=0
```

**对比非线性情况**：如果允许 $x \cdot y$，结果 $xy$ 不是仿射表达式，闭包性被破坏。你必须用表达式树（AST）来表示：

```
    *
   / \
  x   y
```

然后每次运算都要递归遍历树。这正是非线性规划建模库（如 Pyomo）比线性规划库复杂得多的原因。

**线性规划的"线性"二字，在工程上的价值就是闭包性 → 扁平字典表示 → 极简实现。**

---

## 在 minipulp 中的体现

```python
class LpAffineExpression:
    def __init__(self, terms: dict, const: float = 0):
        self.terms = terms    # {LpVariable: coef}
        self.const = const    # 常数项
```

运算符重载就是字典合并：

```python
def __add__(self, other):
    merged = dict(self.terms)
    for var, coef in other.terms.items():
        merged[var] = merged.get(var, 0) + coef  # 系数相加
    return LpAffineExpression(merged, self.const + other.const)
```

没有树，没有递归，没有 AST。一个字典合并操作就是全部。

---

## 零系数消除

闭包性的一个推论：$x - x = 0$，变量项应消去。

```python
x = LpVariable("x")
expr = x - x
assert expr.terms == {}       # 变量项消去
assert expr.const == 0.0      # 只剩常数
```

构造时自动剔除零系数：

```python
self.terms = {var: coef for var, coef in terms.items() if coef != 0}
```

这保持字典的**规范化**——零系数项不存储，避免冗余。