# 运算符重载机制

> 原则二的底层实现：`3 * x + 2 * y` 这行 Python 代码，每一步都在构造对象，而非做数值计算。

---

## Python 运算符重载回顾

Python 的运算符（`+`、`-`、`*`、`<=` 等）本质是方法调用：

| 表达式 | 实际调用 |
|--------|----------|
| `a + b` | `a.__add__(b)`，失败则 `b.__radd__(a)` |
| `a * b` | `a.__mul__(b)`，失败则 `b.__rmul__(a)` |
| `a <= b` | `a.__le__(b)` |
| `-a` | `a.__neg__()` |

关键机制：**若左操作数的 `__mul__` 返回 `NotImplemented`，Python 回退到右操作数的 `__rmul__`**。

---

## `3 * x` 的完整调用链

```python
x = LpVariable("x")
expr = 3 * x
```

逐步追踪：

1. Python 先尝试 `int.__mul__(3, x)`
2. `int` 不认识 `LpVariable`，返回 `NotImplemented`
3. Python 回退到 `x.__rmul__(3)`
4. `LpVariable` 继承自 `LpAffineExpression`，调用 `LpAffineExpression.__rmul__`
5. `__rmul__` 调 `__mul__`，检测到 `3` 是数值：

```python
def __mul__(self, other):
    if _is_number(other):
        return self._new(
            {var: coef * other for var, coef in self.terms.items()},
            self.const * other,
        )
```

6. `x.terms = {x: 1.0}`，乘以 3 得 `{x: 3.0}`
7. 返回 `LpAffineExpression({x: 3.0}, const=0.0)`

**结果：`expr` 是一个 `LpAffineExpression` 对象，`expr.terms = {x: 3.0}`。**

---

## `3 * x + 2 * y` 的完整调用链

```python
x = LpVariable("x")
y = LpVariable("y")
expr = 3 * x + 2 * y
```

等价于 `(3 * x) + (2 * y)`，分三步：

### 步骤 1：`3 * x` → `LpAffineExpression({x: 3.0})`

（同上）

### 步骤 2：`2 * y` → `LpAffineExpression({y: 2.0})`

（同理）

### 步骤 3：`(3*x).__add__(2*y)` → 合并字典

```python
def __add__(self, other):
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)          # {x: 3.0}
        for var, coef in other.terms.items():  # {y: 2.0}
            new_coef = merged.get(var, 0) + coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)
        return self._new(merged, self.const + other.const)
```

合并过程：

```
merged = {x: 3.0}           # 从 self 拷贝
遍历 other.terms = {y: 2.0}:
  y 不在 merged 中 → merged[y] = 2.0
merged = {x: 3.0, y: 2.0}
```

**结果：`expr.terms = {x: 3.0, y: 2.0}`，`expr.const = 0.0`。**

---

## `3 * x + 2 * y <= 100` 的完整调用链

```python
con = 3 * x + 2 * y <= 100
```

### 步骤 1-2：`3 * x + 2 * y` → `LpAffineExpression({x: 3.0, y: 2.0})`

（同上）

### 步骤 3：`__le__(100)` → 构造约束

```python
def __le__(self, other):
    from .constraints import LpConstraint
    return LpConstraint(self - other, LpConstraintSense.LE)
```

### 步骤 4：`self - 100` → 把右端项移到左边

```python
def __sub__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const - other)
```

`self.const - 100 = 0 - 100 = -100`

**结果：`LpConstraint(lhs=LpAffineExpression({x: 3.0, y: 2.0}, const=-100), sense=LE)`**

即 `3x + 2y - 100 <= 0`，归一化为齐次形式。

---

## `_new` 方法的作用

注意 `LpVariable` 和 `LpAffineExpression` 各有不同的 `_new`：

```python
class LpAffineExpression:
    def _new(self, terms, const):
        return LpAffineExpression(terms, const)  # 返回基类

class LpVariable(LpAffineExpression):
    def _new(self, terms, const):
        return LpAffineExpression(terms, const)  # 也返回基类，不是 LpVariable
```

**为什么？** 变量参与运算后（如 `3 * x`），结果不再是"单变量"，而是"多变量表达式"。`3 * x` 不应该是一个 `LpVariable`——它没有 `lowBound`、`upBound` 等属性。`_new` 确保运算结果**降级**为 `LpAffineExpression`。

---

## `__eq__` 的陷阱

重载 `__eq__` 返回 `LpConstraint` 而非 `bool`，会破坏 Python 的相等性语义：

```python
x == y  # 返回 LpConstraint，不是 True/False！
```

这影响字典 key 行为。我们的处理：

1. `__hash__` 基于 `name`（变量）或 `id`（表达式）
2. 字典查找时 Python 先用 `is`（指针相等）判断，再用 `__eq__`
3. 同一变量对象作为 key 时 `is` 命中，不触发 `__eq__`
4. 不同变量 `name` 不同 → `hash` 不同 → 不触发 `__eq__`

因此**只要不创建同名变量，字典行为安全**。

---

## 运算符重载一览表

| 表达式 | 调用 | 结果类型 | 结果内容 |
|--------|------|----------|----------|
| `3 * x` | `x.__rmul__(3)` | `LpAffineExpression` | `{x: 3}` |
| `x * 3` | `x.__mul__(3)` | `LpAffineExpression` | `{x: 3}` |
| `x + y` | `x.__add__(y)` | `LpAffineExpression` | `{x: 1, y: 1}` |
| `x + 5` | `x.__add__(5)` | `LpAffineExpression` | `{x: 1}, c=5` |
| `5 - x` | `x.__rsub__(5)` | `LpAffineExpression` | `{x: -1}, c=5` |
| `x / 4` | `x.__truediv__(4)` | `LpAffineExpression` | `{x: 0.25}` |
| `-x` | `x.__neg__()` | `LpAffineExpression` | `{x: -1}` |
| `x <= 5` | `x.__le__(5)` | `LpConstraint` | `x-5 <= 0` |
| `x == y` | `x.__eq__(y)` | `LpConstraint` | `x-y == 0` |
| `x * y` | `x.__mul__(y)` | **TypeError** | 非线性 |