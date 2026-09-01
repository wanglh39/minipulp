# Phase 1 — 表达式系统

> 运算符重载如何把 `3*x + 2*y` 变成 `LpAffineExpression({x: 3, y: 2})`。
>
> 本篇对应 `src/minipulp/elements.py`，是整个库的代数核心。

---

## 目录

- [设计哲学](#设计哲学)
- [类层次结构](#类层次结构)
- [LpElement — 运算符协议](#lpelement--运算符协议)
- [LpAffineExpression — 仿射表达式](#lpaffineexpression--仿射表达式)
- [LpVariable — 决策变量](#lpvariable--决策变量)
- [运算符重载详解](#运算符重载详解)
- [闭包性证明](#闭包性证明)
- [哈希与相等性](#哈希与相等性)
- [lpSum — 高效求和](#lpsum--高效求和)
- [批量变量创建](#批量变量创建)
- [完整示例](#完整示例)

---

## 设计哲学

PuLP 最具辨识度的特征是：**建模代码几乎和数学公式一模一样**。

```python
# 数学公式：max 3x + 2y  s.t. 2x + y <= 100
# Python 代码：
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
```

这不是字符串解析——`3 * x + 2 * y` 是真正的 Python 表达式，
通过**运算符重载**构造出 `LpAffineExpression({x: 3, y: 2})` 对象。

核心思想：**代数表达式即代码**。变量是对象，运算是方法调用，结果是表达式对象。

---

## 类层次结构

```
LpElement                    # 基类：定义运算符协议
  └── LpAffineExpression     # 仿射表达式：{var: coef} 字典 + 常数项
        └── LpVariable       # 决策变量：单变量表达式 {self: 1}
```

**继承关系的设计意图**：

- `LpElement` 定义运算符协议（`__add__`, `__mul__`, `__le__` 等）
- `LpAffineExpression` 实现所有代数运算（加法、数乘、比较）
- `LpVariable` 继承 `LpAffineExpression`，自动获得全部代数能力

变量"是一个"单变量表达式（`terms = {self: 1}, const = 0`）。
这一数学事实让运算符重载只需在 `LpAffineExpression` 写一次。

---

## LpElement — 运算符协议

`LpElement` 是所有可参与代数运算对象的基类：

```python
class LpElement:
    name: str = ""

    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __add__(self, other): raise NotImplementedError
    def __radd__(self, other): raise NotImplementedError
    def __sub__(self, other): raise NotImplementedError
    def __rsub__(self, other): raise NotImplementedError
    def __mul__(self, other): raise NotImplementedError
    def __rmul__(self, other): raise NotImplementedError
    def __truediv__(self, other): raise NotImplementedError
    def __neg__(self): raise NotImplementedError

    def __le__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.LE)

    def __ge__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.GE)

    def __eq__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

**比较运算符**（`__le__`, `__ge__`, `__eq__`）在基类实现，
因为它们的逻辑对所有子类相同：构造 `LpConstraint` 对象。

**延迟导入**：`from .constraints import LpConstraint` 在方法内部导入，
避免 `elements.py` 和 `constraints.py` 之间的循环导入。

---

## LpAffineExpression — 仿射表达式

### 内部表示

```python
class LpAffineExpression(LpElement):
    def __init__(self, terms: dict | None = None, const: float = 0.0):
        if terms is None:
            self.terms = {}
        else:
            self.terms = {var: float(coef) for var, coef in terms.items() if coef != 0}
        self.const = float(const)
```

仿射表达式 $\sum_i c_i x_i + c_0$ 用两个属性表示：

- `terms: dict[LpVariable, float]` — 变量到系数的映射
- `const: float` — 常数项

**规范化**：构造时剔除零系数项（`if coef != 0`），保持表示唯一性。

### 为什么用字典而非表达式树？

传统计算机代数系统用**表达式树**表示表达式：

```
    +              树结构需要递归遍历，
   / \             每次运算创建新节点，
  *   *            求值、化简都很复杂。
 / \ / \
3  x 2  y
```

PuLP 用**扁平字典**表示：

```
{x: 3, y: 2}  ←  3*x + 2*y
```

这之所以可行，是因为**仿射表达式在加法和数乘下封闭**：

- 两个仿射表达式相加 → 仍是仿射表达式（字典系数相加）
- 仿射表达式乘以常数 → 仍是仿射表达式（系数同乘）

无需树结构，一个字典就够了。这是 PuLP 极简代码的数学根因。

### `_new` 工厂方法

```python
def _new(self, terms: dict, const: float) -> "LpAffineExpression":
    return LpAffineExpression(terms, const)
```

`LpVariable` 覆盖此方法，使运算结果降级为普通表达式：

```python
# LpVariable._new
def _new(self, terms, const):
    return LpAffineExpression(terms, const)  # 不再是 LpVariable
```

**为什么？** `x + y` 的结果是 `LpAffineExpression({x:1, y:1})`，
不是 `LpVariable`——它有两个变量，不是单变量表达式。

---

## LpVariable — 决策变量

### 构造

```python
class LpVariable(LpAffineExpression):
    def __init__(self, name, lowBound=None, upBound=None, cat=LpCat.CONTINUOUS):
        self.name = name
        self.lowBound = lowBound
        self.upBound = upBound
        self.cat = cat
        self.varValue = None        # 求解后回填
        self.terms = {self: 1.0}    # 单变量表达式：1 * x
        self.const = 0.0
```

变量 `x` 就是仿射表达式 `1 * x + 0`，即 `terms = {x: 1}, const = 0`。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 变量名，同时作为哈希依据 |
| `lowBound` | `float \| None` | 下界，None 表示无下界 |
| `upBound` | `float \| None` | 上界，None 表示无上界 |
| `cat` | `LpCat` | 变量类别（连续/整数/二元） |
| `varValue` | `float \| None` | 求解后回填的解值，求解前为 None |
| `terms` | `dict` | `{self: 1.0}` — 单变量表达式 |
| `const` | `float` | `0.0` — 无常数项 |

### 变量类别

```python
x = mp.LpVariable("x", lowBound=0)                          # 连续变量
z = mp.LpVariable("z", lowBound=0, upBound=10, cat=mp.LpInteger)  # 整数变量
b = mp.LpVariable("b", cat=mp.LpBinary)                     # 二元变量 (0 或 1)
```

| 类别 | 含义 | 求解器支持 |
|------|------|---------|
| `LpContinuous` | 连续变量，取值范围 [lb, ub] | SimplexCore, SimplexCpp, CBC |
| `LpInteger` | 整数变量，取值范围 [lb, ub] ∩ ℤ | CBC |
| `LpBinary` | 二元变量，取值 {0, 1} | CBC |

---

## 运算符重载详解

### 标量乘法：`3 * x`

```python
# Python 先尝试 int.__mul__(3, x) → NotImplemented
# 然后调用 x.__rmul__(3)
def __mul__(self, other):
    if _is_number(other):
        return self._new(
            {var: coef * other for var, coef in self.terms.items()},
            self.const * other,
        )
```

```
3 * x  →  x.__rmul__(3)  →  LpAffineExpression({x: 3.0})
```

### 加法：`x + y`

```python
def __add__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const + other)
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)
        for var, coef in other.terms.items():
            new_coef = merged.get(var, 0.0) + coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)  # 系数为 0 则删除
        return self._new(merged, self.const + other.const)
```

```
x + y  →  x.__add__(y)  →  LpAffineExpression({x: 1, y: 1})
```

**字典合并**：遍历 `other.terms`，系数相加。若结果为 0 则删除该项（规范化）。

### 减法：`x - y`

```python
def __sub__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const - other)
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)
        for var, coef in other.terms.items():
            new_coef = merged.get(var, 0.0) - coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)
        return self._new(merged, self.const - other.const)
```

### 反向减法：`5 - x`

```python
def __rsub__(self, other):
    if _is_number(other):
        return self._new(
            {var: -coef for var, coef in self.terms.items()},
            other - self.const,
        )
```

```
5 - x  →  x.__rsub__(5)  →  LpAffineExpression({x: -1}, const=5)
```

### 除法：`x / 3`

```python
def __truediv__(self, other):
    if _is_number(other):
        if other == 0:
            raise ZeroDivisionError("表达式除以零")
        return self.__mul__(1.0 / other)
```

除以常数等价于乘以倒数。

### 负号：`-x`

```python
def __neg__(self):
    return self._new(
        {var: -coef for var, coef in self.terms.items()},
        -self.const,
    )
```

### 乘法陷阱：`x * y` 是非法的

```python
def __mul__(self, other):
    ...
    if isinstance(other, LpAffineExpression):
        if not self.terms or not other.terms:
            # 其中一个是纯常数
            ...
        raise TypeError(
            "不能将两个含变量的表达式相乘（非线性），"
            "线性规划只允许仿射表达式"
        )
```

**线性规划只允许仿射表达式**。`x * y` 是二次项，超出 LP 范畴。
尝试相乘会抛出 `TypeError`。

### 比较运算符：`x + y <= 10`

```python
# LpElement.__le__
def __le__(self, other):
    return LpConstraint(self - other, LpConstraintSense.LE)
```

```
x + y <= 10
  → (x + y).__le__(10)
  → LpConstraint((x+y) - 10, LE)
  → LpConstraint(lhs={x:1, y:1, const:-10}, sense=LE)
```

约束被归一化为 `lhs <= 0` 形式（右端项移到左边）。

### 运算符总览

| 表达式 | Python 调用链 | 结果 |
|--------|-------------|------|
| `3 * x` | `int.__mul__` 失败 → `x.__rmul__(3)` | `AffExpr({x:3})` |
| `x + y` | `x.__add__(y)` | `AffExpr({x:1, y:1})` |
| `x + 5` | `x.__add__(5)` | `AffExpr({x:1}, c=5)` |
| `5 - x` | `x.__rsub__(5)` | `AffExpr({x:-1}, c=5)` |
| `x / 2` | `x.__truediv__(2)` | `AffExpr({x:0.5})` |
| `-x` | `x.__neg__()` | `AffExpr({x:-1})` |
| `3*x + 2*y` | 两次 mul + 一次 add | `AffExpr({x:3, y:2})` |
| `x <= 5` | `x.__le__(5)` | `LpConstraint(x-5, LE)` |
| `x == y` | `x.__eq__(y)` | `LpConstraint(x-y, EQ)` |
| `x * y` | `x.__mul__(y)` | **TypeError** |

---

## 闭包性证明

**定理**：仿射表达式在加法、减法、数乘下封闭。

**证明**：

设 $f = \sum_i a_i x_i + a_0$，$g = \sum_j b_j x_j + b_0$。

1. **加法**：$f + g = \sum_i (a_i + b_i) x_i + (a_0 + b_0)$ — 仍是仿射表达式 ✓
2. **减法**：$f - g = \sum_i (a_i - b_i) x_i + (a_0 - b_0)$ — 仍是仿射表达式 ✓
3. **数乘**：$c \cdot f = \sum_i (c \cdot a_i) x_i + (c \cdot a_0)$ — 仍是仿射表达式 ✓

因此，任意变量的线性组合仍是仿射表达式，可以用 `{var: coef}` 字典表示。
无需表达式树，无需递归求值——一个扁平字典就够了。

**推论**：`LpAffineExpression` 的所有运算符返回 `LpAffineExpression`，
不会产生其他类型（除了比较运算符返回 `LpConstraint`）。

---

## 哈希与相等性

### 问题

建模库必须重载 `__eq__` 以支持 `x == y` 构造等式约束。
但这会覆盖默认的相等性判断，影响对象作为字典 key 的行为。

### 解决方案

```python
class LpElement:
    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __eq__(self, other):
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

1. `__hash__` 基于 `name`（变量）或 `id`（表达式），保证可哈希
2. 字典查找时，Python 先用 `is`（指针相等）判断，再用 `__eq__`
3. 同一变量对象作为 key 时 `is` 命中，不会误触发 `__eq__`
4. 不同变量 `name` 不同 → `hash` 不同 → 不会触发 `__eq__`

**安全条件**：不要创建同名变量。只要变量名唯一，字典行为安全。

```python
x = mp.LpVariable("x")
y = mp.LpVariable("y")

d = {x: 3, y: 5}  # 安全：x 和 y 是不同对象，hash 不同
d[x]  # 返回 3：先 is 匹配，命中
```

---

## lpSum — 高效求和

### 问题：`sum()` 的性能瓶颈

```python
# sum([3*x, 2*y, 5]) 展开为：
# ((3*x) + (2*y)) + 5
# 每次调用 __add__，都创建一个新的 LpAffineExpression
```

对 N 个表达式求和，`sum()` 需要 N-1 次构造，每次拷贝并合并字典。

### `lpSum` 优化

```python
def lpSum(vector: list) -> LpAffineExpression:
    if not vector:
        return LpAffineExpression()
    merged: dict = {}
    const = 0.0
    for item in vector:
        if _is_number(item):
            const += item
        elif isinstance(item, LpAffineExpression):
            for var, coef in item.terms.items():
                new_coef = merged.get(var, 0.0) + coef
                if new_coef != 0:
                    merged[var] = new_coef
                else:
                    merged.pop(var, None)
            const += item.const
    return LpAffineExpression(merged, const)
```

直接遍历所有表达式，一次性合并到同一个字典——只构造一次。

### 复杂度对比

| 方法 | 时间复杂度 | 中间对象数 |
|------|-----------|---------|
| `sum(vector)` | $O(N \cdot \bar{T})$ | $N-1$ |
| `lpSum(vector)` | $O(\sum T_i)$ | $1$ |

对 500 个变量的求和，`lpSum` 比 `sum` 快约 5-10x。

---

## 批量变量创建

### `LpVariable.dicts` — 一维变量字典

```python
@classmethod
def dicts(cls, name, indices, lowBound=None, upBound=None, cat=LpContinuous) -> dict:
    return {i: cls(f"{name}_{i}", lowBound, upBound, cat) for i in indices}
```

```python
x = mp.LpVariable.dicts("x", range(3), lowBound=0)
# x[0].name == "x_0", x[1].name == "x_1", x[2].name == "x_2"
# x[0].lowBound == 0
```

索引可以是任意可哈希对象：

```python
routes = mp.LpVariable.dicts("route",
    [("北京", "上海"), ("北京", "广州"), ("上海", "广州")],
    lowBound=0)
# routes[("北京", "上海")] 是一个变量
```

### `LpVariable.matrix` — 二维变量矩阵

```python
@classmethod
def matrix(cls, name, rows, cols, lowBound=None, upBound=None, cat=LpContinuous) -> dict:
    return {
        r: {c: cls(f"{name}_{r}_{c}", lowBound, upBound, cat) for c in cols}
        for r in rows
    }
```

```python
x = mp.LpVariable.matrix("x", range(2), range(3), lowBound=0)
# x[0][0].name == "x_0_0"
# x[1][2].name == "x_1_2"
```

### 命名规则

| 方法 | 变量名格式 | 示例 |
|------|---------|------|
| `dicts` | `{name}_{index}` | `x_0`, `x_1` |
| `matrix` | `{name}_{row}_{col}` | `x_0_0`, `x_1_2` |

---

## 完整示例

### 生产计划

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)  # 产品 A 产量
y = mp.LpVariable("y", lowBound=0)  # 产品 B 产量

prob = mp.LpProblem("production", mp.LpMaximize)
prob += 3 * x + 2 * y          # max 3x + 2y
prob += 2 * x + y <= 100       # 原料约束
prob += x + y <= 80            # 工时约束
prob += x <= 40                # 市场约束

prob.solve()
print(f"x = {x.varValue}, y = {y.varValue}")  # x = 20, y = 60
print(f"obj = {prob.objective.value()}")       # obj = 180
```

### 运输问题（使用 dicts + lpSum）

```python
import minipulp as mp

supply = {"f1": 30, "f2": 40}      # 工厂供应量
demand = {"c1": 20, "c2": 25, "c3": 25}  # 客户需求量
cost = {
    ("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4,
    ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1,
}

# x[i][j] = 从工厂 i 运到客户 j 的量
x = mp.LpVariable.matrix("x", supply.keys(), demand.keys(), lowBound=0)

prob = mp.LpProblem("transport", mp.LpMinimize)
prob += mp.lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)

for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) <= supply[i]  # 供应约束

for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) >= demand[j]  # 需求约束

prob.solve()
print(f"总成本: {prob.objective.value()}")
```

---

## 测试

```bash
uv run pytest tests/test_elements.py -v
```

43 个测试覆盖：变量构造、标量乘法、加减除、复合表达式、约束构造、lpSum、value 求值。

---

## 总结

Phase 1 实现了 minipulp 的代数核心：

| 类 | 职责 | 关键属性 |
|---|------|---------|
| `LpElement` | 运算符协议 | `__le__`, `__ge__`, `__eq__` |
| `LpAffineExpression` | 仿射表达式 | `terms: dict`, `const: float` |
| `LpVariable` | 决策变量 | `lowBound`, `upBound`, `cat`, `varValue` |

**核心设计**：

1. **字典表示**：`{var: coef}` 扁平字典，无需表达式树
2. **闭包性**：仿射表达式在加法、数乘下封闭
3. **继承复用**：运算符只在 `LpAffineExpression` 实现，`LpVariable` 自动继承
4. **运算符重载**：`3*x + 2*y` 直接构造表达式对象
