# Phase 2 — 约束与问题

> `LpProblem` 容器与 LP 文件格式导出。
>
> 本篇对应 `src/minipulp/problem.py`、`src/minipulp/constraints.py` 和 `src/minipulp/lp_io.py`。

---

## 目录

- [Phase 2 — 约束与问题](#phase-2--约束与问题)
  - [目录](#目录)
  - [LpConstraint — 约束对象](#lpconstraint--约束对象)
    - [归一化约定](#归一化约定)
    - [类定义](#类定义)
    - [三种约束方向](#三种约束方向)
    - [构造路径](#构造路径)
  - [LpProblem — 问题容器](#lpproblem--问题容器)
    - [职责](#职责)
    - [类定义](#类定义-1)
    - [属性](#属性)
    - [方法](#方法)
  - [+= 语法糖](#-语法糖)
    - [设计](#设计)
    - [使用示例](#使用示例)
    - [约束自动命名](#约束自动命名)
    - [变量自动注册](#变量自动注册)
  - [LP 文件格式导出](#lp-文件格式导出)
    - [CPLEX LP 格式](#cplex-lp-格式)
    - [格式结构](#格式结构)
    - [实现](#实现)
    - [系数格式化](#系数格式化)
  - [完整示例](#完整示例)
  - [LpConstraint 归一化深入讲解](#lpconstraint-归一化深入讲解)
  - [LpProblem 完整方法列表与示例](#lpproblem-完整方法列表与示例)
  - [+= 语法糖逐步追踪](#-语法糖逐步追踪)
  - [LP 文件导出完整代码讲解](#lp-文件导出完整代码讲解)
  - [约束自动命名详细说明](#约束自动命名详细说明)
  - [变量自动注册机制](#变量自动注册机制)
  - [建模示例：生产计划](#建模示例生产计划)
  - [建模示例：饮食问题](#建模示例饮食问题)
  - [建模示例：资源分配](#建模示例资源分配)
  - [测试](#测试)

---

## LpConstraint — 约束对象

### 归一化约定

用户写的 `3*x + 2*y <= 10` 在内部被归一化为：

```python
LpConstraint(lhs=LpAffineExpression({x:3, y:2}, const=-10), sense=LE)
```

即 `lhs <= 0` 的齐次形式。右端项移到左边，成为常数项的一部分。

**为什么归一化？** 求解器只需处理一种形式（`lhs <= 0`），
而非为 `<=`/`>=`/`==` 各写一套逻辑。

### 类定义

```python
class LpConstraint:
    def __init__(self, lhs: LpAffineExpression, sense=LpConstraintSense.LE, name=None):
        self.lhs = lhs        # 归一化后的左侧表达式
        self.sense = sense    # 比较方向
        self.name = name      # 约束名

    @property
    def expression(self) -> LpAffineExpression:
        return self.lhs

    @property
    def constant(self) -> float:
        return self.lhs.const  # 即负的右端项

    @property
    def terms(self) -> dict:
        return self.lhs.terms  # 左侧表达式的变量系数字典
```

`terms` 和 `constant` 属性是求解器提取矩阵表示时使用的接口。

### 三种约束方向

```python
con_le = 2 * x + y <= 100  # LpConstraintSense.LE (0)
con_ge = 3 * x + y >= 6    # LpConstraintSense.GE (2)
con_eq = x + y == 10       # LpConstraintSense.EQ (1)
```

| 约束 | sense 值 | 内部表示 |
|------|---------|---------|
| `2x + y <= 100` | `LE (0)` | `lhs={x:2, y:1, const:-100}, sense=LE` |
| `3x + y >= 6` | `GE (2)` | `lhs={x:3, y:1, const:-6}, sense=GE` |
| `x + y == 10` | `EQ (1)` | `lhs={x:1, y:1, const:-10}, sense=EQ` |

### 构造路径

用户通常不直接实例化 `LpConstraint`，而是通过运算符自动构造：

```python
# x + y <= 10 的构造过程：
# 1. x + y → LpAffineExpression({x:1, y:1})
# 2. (x+y) <= 10 → LpElement.__le__(10)
# 3. self - other → LpAffineExpression({x:1, y:1}, const=-10)
# 4. LpConstraint(lhs, LE)
con = x + y <= 10
print(con)  # 1.0*x + 1.0*y - 10.0 <= 0
```

---

## LpProblem — 问题容器

### 职责

`LpProblem` 是用户建模的入口，职责分为三层：

1. **收集** — 用 `+=` 语法糖添加目标函数与约束
2. **表示** — 维护变量表、约束表
3. **委托** — `solve(solver)` 把问题交给求解器

### 类定义

```python
class LpProblem:
    def __init__(self, name="problem", sense=LpSense.MINIMIZE):
        self.name = name                    # 问题名
        self.sense = sense                  # 目标方向
        self.objective = None               # 目标函数
        self.constraints = {}               # 约束字典
        self.status = LpStatus.NOT_SOLVED   # 求解状态
        self._variables = {}                # 变量表
```

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 问题名，用于 LP 文件输出 |
| `sense` | `LpSense` | 目标方向（MINIMIZE / MAXIMIZE） |
| `objective` | `LpAffineExpression \| None` | 目标函数 |
| `constraints` | `dict[str, LpConstraint]` | 约束字典 |
| `status` | `LpStatus` | 求解状态 |
| `status_msg` | `str` | 求解状态的可读消息 |

### 方法

| 方法 | 说明 |
|------|------|
| `addConstraint(con, name=None)` | 添加约束 |
| `setObjective(expr)` | 设置目标函数 |
| `variables()` | 返回所有变量列表 |
| `numVariables()` | 变量数 |
| `numConstraints()` | 约束数 |
| `solve(solver=None)` | 求解问题 |
| `valid()` | 检查是否已设置目标 |

---

## += 语法糖

### 设计

`+=` 是 PuLP 最具辨识度的 API。它根据右操作数的类型自动判断操作：

```python
def __iadd__(self, other) -> "LpProblem":
    if isinstance(other, LpConstraint):
        self.addConstraint(other)        # 约束 → 添加约束
    elif isinstance(other, LpAffineExpression):
        self.setObjective(other)         # 表达式 → 设置目标
    elif isinstance(other, LpVariable):
        self.setObjective(other)         # 变量 → 设置目标
    else:
        raise TypeError(...)
    return self
```

### 使用示例

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y          # 表达式 → 设置目标
prob += 2 * x + y <= 100       # 约束 → 添加约束
prob += x + y <= 80            # 约束 → 添加约束
```

这一重载让建模代码读起来几乎和数学公式一致：

```
数学：  max 3x + 2y  s.t. 2x + y ≤ 100, x + y ≤ 80
代码：  prob += 3*x + 2*y;  prob += 2*x + y <= 100;  prob += x + y <= 80
```

### 约束自动命名

```python
def addConstraint(self, constraint, name=None):
    if name is None:
        if constraint.name is None:
            name = f"c_{len(self.constraints)}"  # 自动分配 c_0, c_1, ...
        else:
            name = constraint.name
    constraint.name = name
    self.constraints[name] = constraint
    for var in constraint.terms:
        self.addVariable(var)  # 自动注册约束中的变量
```

约束名用于 LP 文件输出。未命名时自动分配 `c_0`, `c_1`, `c_2`, ...

### 变量自动注册

添加约束时，约束中出现的变量会自动注册到问题的变量表：
```python
for var in constraint.terms:
    self.addVariable(var)
```

设置目标函数时同理。用户无需手动注册变量。

---

## LP 文件格式导出

### CPLEX LP 格式

`write_lp` 将 `LpProblem` 序列化为 CPLEX LP 格式文本：

```
\ Project name: demo
Maximize
  obj: 3 x + 2 y
Subject To
  c_0: 2 x + 1 y <= 100
  c_1: 1 x + 1 y <= 80
Bounds
  x >= 0
  y >= 0
End
```

### 格式结构

| 段 | 语义 |
|---|------|
| `\ Project name:` | 注释行，问题名 |
| `Maximize` / `Minimize` | 目标函数 |
| `Subject To` | 约束列表 |
| `Bounds` | 变量上下界 |
| `General` / `Integer` | 整数变量 |
| `Binary` | 0/1 变量 |
| `End` | 文件结束 |

### 实现

```python
def write_lp(problem: LpProblem) -> str:
    lines = []
    lines.append(f"\\ Project name: {problem.name}")

    # 目标函数
    sense_word = "Maximize" if problem.sense == LpSense.MAXIMIZE else "Minimize"
    lines.append(sense_word)
    lines.append(f"  obj: {_format_terms(problem.objective.terms)}")

    # 约束
    if problem.constraints:
        lines.append("Subject To")
        for name, con in problem.constraints.items():
            terms_str = _format_terms(con.terms)
            rhs = -con.constant  # 右端项 = -常数项
            op = _CONSTRAINT_OP[con.sense]
            lines.append(f"  {name}: {terms_str} {op} {_format_coef(rhs)}")

    # 变量界
    bounded_lines = []
    for var in problem.variables():
        lb, ub = var.lowBound, var.upBound
        if lb is None and ub is None:
            bounded_lines.append(f"  {var.name} free")
        elif lb is not None and ub is not None:
            bounded_lines.append(f"  {lb} <= {var.name} <= {ub}")
        elif lb is not None:
            bounded_lines.append(f"  {var.name} >= {lb}")
        else:
            bounded_lines.append(f"  {var.name} <= {ub}")
    ...

    lines.append("End")
    return "\n".join(lines)
```

### 系数格式化

```python
def _format_coef(coef: float) -> str:
    if coef == int(coef):
        return str(int(coef))  # 整数输出 3
    return str(coef)           # 浮点输出 3.5

def _format_terms(terms: dict) -> str:
    parts = []
    for var, coef in terms.items():
        if coef == 1.0:
            parts.append(f"+ {var.name}")
        elif coef == -1.0:
            parts.append(f"- {var.name}")
        elif coef < 0:
            parts.append(f"- {_format_coef(abs(coef))} {var.name}")
        else:
            parts.append(f"+ {_format_coef(coef)} {var.name}")
    ...
```

特殊处理系数 1 和 -1（省略系数），使输出更接近数学写法。

---

## 完整示例

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("production", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

# 导出 LP 文件
print(mp.write_lp(prob))
# \ Project name: production
# Maximize
#   obj: 3 x + 2 y
# Subject To
#   c_0: 2 x + 1 y <= 100
#   c_1: 1 x + 1 y <= 80
#   c_2: 1 x <= 40
# Bounds
#   x >= 0
#   y >= 0
# End

prob.solve()
print(f"status: {prob.status_msg}")  # Optimal
print(f"x = {x.varValue}, y = {y.varValue}")  # x = 20, y = 60
```

---

## LpConstraint 归一化深入讲解

### 归一化的数学含义

用户书写的约束通常形式为 `lhs <sense> rhs`，其中 `lhs` 是变量表达式，`rhs` 是常数或表达式。归一化将其转换为 `lhs - rhs <sense> 0` 的齐次形式。

```
原始：3x + 2y <= 10
归一化：(3x + 2y) - 10 <= 0
内部：LpAffineExpression({x:3, y:2}, const=-10), sense=LE
```

### 为什么选择 `lhs <sense> 0` 而非 `lhs <sense> rhs`？

两种表示在数学上等价，但 `lhs <sense> 0` 有实现优势：

1. **统一形式**：所有约束的右端项都是 0，求解器只需处理一种形式
2. **矩阵表示简单**：约束矩阵 $Ax \leq b$ 中，$b$ 就是 `-const`，提取直接
3. **运算封闭**：约束相加、数乘后仍是齐次形式

### 归一化的实现细节

```python
# LpElement.__le__
def __le__(self, other):
    from .constraints import LpConstraint
    return LpConstraint(self - other, LpConstraintSense.LE)
```

`self - other` 完成归一化：

- `self` 是左侧表达式（如 `3*x + 2*y`）
- `other` 是右侧（如 `10`）
- `self - other` = `3*x + 2*y - 10` = `LpAffineExpression({x:3, y:2}, const=-10)`

### 不同约束方向的归一化

```python
# <= 约束
con = 2*x + y <= 100
# self - other = 2x + y - 100
# lhs = {x:2, y:1, const:-100}, sense=LE
# 含义：2x + y - 100 <= 0

# >= 约束
con = 3*x + y >= 6
# self - other = 3x + y - 6
# lhs = {x:3, y:1, const:-6}, sense=GE
# 含义：3x + y - 6 >= 0

# == 约束
con = x + y == 10
# self - other = x + y - 10
# lhs = {x:1, y:1, const:-10}, sense=EQ
# 含义：x + y - 10 == 0
```

### 表达式在两侧的约束

```python
# x + y <= z + w
con = x + y <= z + w
# self - other = (x + y) - (z + w) = x + y - z - w
# lhs = {x:1, y:1, z:-1, w:-1, const:0}, sense=LE
# 含义：x + y - z - w <= 0
```

归一化自动处理右侧是表达式的情况，`self - other` 的运算符重载完成合并。

### 从归一化形式恢复原始形式

LP 文件输出时，需要从 `lhs <sense> 0` 恢复 `terms <sense> rhs` 形式：

```python
# 内部：lhs = {x:2, y:1, const:-100}, sense=LE
# 输出：2 x + 1 y <= 100

# rhs = -const = -(-100) = 100
# terms = {x:2, y:1}
# 输出："{terms} {op} {rhs}" = "2 x + 1 y <= 100"
```

`rhs = -con.constant` 是因为 `const` 是移到左边的右端项的负值。

### 约束的常数项属性

```python
con = 2*x + y <= 100
print(con.constant)  # -100.0
print(con.terms)     # {x: 2.0, y: 1.0}
print(con.sense)     # LpConstraintSense.LE
```

`constant` 属性返回 `lhs.const`，即负的右端项。`terms` 返回 `lhs.terms`，即变量系数。这些属性是求解器提取矩阵表示的接口。

---

## LpProblem 完整方法列表与示例

### `__init__`

```python
def __init__(self, name="problem", sense=LpSense.MINIMIZE):
    self.name = name
    self.sense = sense
    self.objective = None
    self.constraints = {}
    self.status = LpStatus.NOT_SOLVED
    self._variables = {}
```

```python
# 默认最小化
prob1 = mp.LpProblem("p1")
# 显式最大化
prob2 = mp.LpProblem("p2", mp.LpMaximize)
# 最小化
prob3 = mp.LpProblem("p3", mp.LpMinimize)
```

### `setObjective`

```python
def setObjective(self, expr: LpAffineExpression) -> None:
    if isinstance(expr, LpVariable):
        expr = LpAffineExpression(expr.terms, expr.const)
    self.objective = expr
    for var in expr.terms:
        self.addVariable(var)
```

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

# 通过 setObjective 设置目标
prob.setObjective(3 * x + 2 * y)
# 等价于 prob += 3 * x + 2 * y
```

### `addConstraint`

```python
def addConstraint(self, constraint: LpConstraint, name: str = None) -> None:
    if name is None:
        if constraint.name is None:
            name = f"c_{len(self.constraints)}"
        else:
            name = constraint.name
    constraint.name = name
    self.constraints[name] = constraint
    for var in constraint.terms:
        self.addVariable(var)
```

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

# 自动命名
prob.addConstraint(2 * x + y <= 100)
# 约束名 = "c_0"

# 显式命名
prob.addConstraint(x + y <= 80, name="工时约束")
# 约束名 = "工时约束"
```

### `addVariable`

```python
def addVariable(self, var: LpVariable) -> None:
    if var.name not in self._variables:
        self._variables[var.name] = var
```

通常由 `addConstraint` 和 `setObjective` 自动调用，用户无需手动调用。

```python
# 自动注册
prob += 2 * x + y <= 100  # x 和 y 自动注册
# 手动注册（通常不需要）
prob.addVariable(x)
```

### `variables`

```python
def variables(self) -> list[LpVariable]:
    return list(self._variables.values())
```

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
prob += 3 * x + 2 * y
prob += x + y <= 10

vars = prob.variables()
print(vars)  # [x, y]（顺序可能不同）
```

### `numVariables` / `numConstraints`

```python
def numVariables(self) -> int:
    return len(self._variables)

def numConstraints(self) -> int:
    return len(self.constraints)
```

```python
print(prob.numVariables())   # 2
print(prob.numConstraints()) # 1
```

### `valid`

```python
def valid(self) -> bool:
    return self.objective is not None
```

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
print(prob.valid())  # False — 未设置目标

prob += 3 * x
print(prob.valid())  # True
```

### `solve`

```python
def solve(self, solver=None) -> LpStatus:
    if not self.valid():
        raise ValueError("未设置目标函数")
    if solver is None:
        solver = self._default_solver()
    self.status = solver.actualSolve(self)
    return self.status
```

```python
# 默认求解器
prob.solve()

# 指定求解器
from minipulp.solvers import PULP_CBC_CMD
prob.solve(solver=PULP_CBC_CMD(msg=True))  # 显示 CBC 输出
```

### `__iadd__`

```python
def __iadd__(self, other) -> "LpProblem":
    if isinstance(other, LpConstraint):
        self.addConstraint(other)
    elif isinstance(other, LpAffineExpression):
        self.setObjective(other)
    elif isinstance(other, LpVariable):
        self.setObjective(other)
    else:
        raise TypeError(f"不支持 += {type(other)}")
    return self
```

```python
prob += 3 * x + 2 * y        # 表达式 → 目标
prob += 2 * x + y <= 100     # 约束 → 添加
prob += x                    # 变量 → 目标（单变量）
```

### `__str__` / `__repr__`

```python
def __str__(self) -> str:
    sense = "max" if self.sense == LpSense.MAXIMIZE else "min"
    lines = [f"{self.name}:"]
    lines.append(f"  {sense} {self.objective}")
    for name, con in self.constraints.items():
        lines.append(f"  s.t. {name}: {con}")
    return "\n".join(lines)
```

```python
print(prob)
# demo:
#   max 3*x + 2*y
#   s.t. c_0: 2*x + y - 100 <= 0
```

---

## += 语法糖逐步追踪

### 追踪 1：`prob += 3 * x + 2 * y`

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
prob += 3 * x + 2 * y
```

**执行步骤**：

```
步骤 1: 计算 3 * x + 2 * y
  - 结果 = LpAffineExpression(terms={x:3.0, y:2.0}, const=0.0)
  - 类型：LpAffineExpression

步骤 2: prob += 结果
  - Python 调用 prob.__iadd__(结果)
  - LpProblem.__iadd__(self, other):
    - isinstance(other, LpConstraint) → False
    - isinstance(other, LpAffineExpression) → True
    - 调用 self.setObjective(other)
      - self.objective = other
      - 遍历 other.terms，注册变量 x, y
  - 返回 self
```

**结果**：`prob.objective = LpAffineExpression({x:3, y:2}, 0)`，`x` 和 `y` 注册到 `prob._variables`。

### 追踪 2：`prob += 2 * x + y <= 100`

```python
prob += 2 * x + y <= 100
```

**执行步骤**：

```
步骤 1: 计算 2 * x + y <= 100
  - 2 * x → LpAffineExpression({x:2}, 0)
  - (2*x) + y → LpAffineExpression({x:2, y:1}, 0)
  - (2*x+y) <= 100 → LpElement.__le__(100)
    - self - 100 → LpAffineExpression({x:2, y:1}, -100)
    - LpConstraint(lhs, LE)
  - 结果 = LpConstraint(lhs={x:2, y:1, const:-100}, sense=LE)
  - 类型：LpConstraint

步骤 2: prob += 结果
  - Python 调用 prob.__iadd__(结果)
  - LpProblem.__iadd__(self, other):
    - isinstance(other, LpConstraint) → True
    - 调用 self.addConstraint(other)
      - name = None, constraint.name = None
      - name = f"c_{len(self.constraints)}" = "c_0"
      - constraint.name = "c_0"
      - self.constraints["c_0"] = constraint
      - 遍历 constraint.terms，注册变量 x, y（已注册，跳过）
  - 返回 self
```

**结果**：`prob.constraints["c_0"] = LpConstraint(...)`。

### 追踪 3：连续 `+=` 约束

```python
prob += x + y <= 80  # 第二个约束
```

**执行步骤**：

```
步骤 1: 计算 x + y <= 80
  - 结果 = LpConstraint(lhs={x:1, y:1, const:-80}, sense=LE)

步骤 2: prob += 结果
  - addConstraint(other):
    - name = f"c_{len(self.constraints)}" = f"c_{1}" = "c_1"
    - （此时 self.constraints 已有 1 个约束 c_0）
    - constraint.name = "c_1"
    - self.constraints["c_1"] = constraint
```

**结果**：`prob.constraints` 现有 `c_0` 和 `c_1` 两个约束。

### 追踪 4：`prob += x`（单变量目标）

```python
prob += x
```

**执行步骤**：

```
步骤 1: x 是 LpVariable
  - 类型：LpVariable

步骤 2: prob += x
  - LpProblem.__iadd__(self, other):
    - isinstance(other, LpConstraint) → False
    - isinstance(other, LpAffineExpression) → True（LpVariable 继承）
    - 调用 self.setObjective(other)
      - self.objective = other（x 本身）
      - 注册变量 x
```

**结果**：`prob.objective = x`，即最大化 `x`。

### 追踪 5：类型错误

```python
try:
    prob += "invalid"
except TypeError as e:
    print(e)
    # 不支持 += <class 'str'>
```

**执行步骤**：

```
步骤 1: "invalid" 是 str
  - 类型：str

步骤 2: prob += "invalid"
  - LpProblem.__iadd__(self, other):
    - isinstance(other, LpConstraint) → False
    - isinstance(other, LpAffineExpression) → False
    - isinstance(other, LpVariable) → False
    - raise TypeError(f"不支持 += {type(other)}")
```

---

## LP 文件导出完整代码讲解

### `write_lp` 函数结构

```python
def write_lp(problem: LpProblem) -> str:
    lines = []

    # 1. 问题名注释
    lines.append(f"\\ Project name: {problem.name}")

    # 2. 目标函数
    sense_word = "Maximize" if problem.sense == LpSense.MAXIMIZE else "Minimize"
    lines.append(sense_word)
    obj_terms_str = _format_terms(problem.objective.terms)
    if problem.objective.const != 0:
        obj_terms_str += f" + {_format_coef(problem.objective.const)}"
    lines.append(f"  obj: {obj_terms_str}")

    # 3. 约束
    if problem.constraints:
        lines.append("Subject To")
        for name, con in problem.constraints.items():
            terms_str = _format_terms(con.terms)
            rhs = -con.constant
            op = _CONSTRAINT_OP[con.sense]
            lines.append(f"  {name}: {terms_str} {op} {_format_coef(rhs)}")

    # 4. 变量界
    bounds_lines = []
    general_lines = []
    binary_lines = []

    for var in problem.variables():
        # 整数/二元变量
        if var.cat == LpCat.BINARY:
            binary_lines.append(f"  {var.name}")
        elif var.cat == LpCat.INTEGER:
            general_lines.append(f"  {var.name}")

        # 界
        lb, ub = var.lowBound, var.upBound
        if var.cat == LpCat.BINARY:
            bounds_lines.append(f"  0 <= {var.name} <= 1")
        elif lb is None and ub is None:
            bounds_lines.append(f"  {var.name} free")
        elif lb is not None and ub is not None:
            bounds_lines.append(f"  {lb} <= {var.name} <= {ub}")
        elif lb is not None:
            bounds_lines.append(f"  {var.name} >= {lb}")
        else:
            bounds_lines.append(f"  {var.name} <= {ub}")

    if bounds_lines:
        lines.append("Bounds")
        lines.extend(bounds_lines)

    if general_lines:
        lines.append("General")
        lines.extend(general_lines)

    if binary_lines:
        lines.append("Binary")
        lines.extend(binary_lines)

    # 5. 结束
    lines.append("End")

    return "\n".join(lines)
```

### 段落详解

#### 问题名注释

```python
lines.append(f"\\ Project name: {problem.name}")
```

输出：`\ Project name: production`

`\` 是 LP 格式的注释符号，整行被求解器忽略。

#### 目标函数段

```python
sense_word = "Maximize" if problem.sense == LpSense.MAXIMIZE else "Minimize"
lines.append(sense_word)
lines.append(f"  obj: {obj_terms_str}")
```

输出：
```
Maximize
  obj: 3 x + 2 y
```

`obj` 是目标函数的名称（CPLEX LP 格式要求目标行有名字）。

#### 约束段

```python
if problem.constraints:
    lines.append("Subject To")
    for name, con in problem.constraints.items():
        terms_str = _format_terms(con.terms)
        rhs = -con.constant  # 右端项 = -常数项
        op = _CONSTRAINT_OP[con.sense]
        lines.append(f"  {name}: {terms_str} {op} {_format_coef(rhs)}")
```

输出：
```
Subject To
  c_0: 2 x + 1 y <= 100
  c_1: 1 x + 1 y <= 80
```

`rhs = -con.constant` 是因为内部存储是 `lhs - rhs <sense> 0`，`constant` 是 `-rhs`。

#### 界段

```python
for var in problem.variables():
    lb, ub = var.lowBound, var.upBound
    if lb is None and ub is None:
        bounds_lines.append(f"  {var.name} free")
    elif lb is not None and ub is not None:
        bounds_lines.append(f"  {lb} <= {var.name} <= {ub}")
    elif lb is not None:
        bounds_lines.append(f"  {var.name} >= {lb}")
    else:
        bounds_lines.append(f"  {var.name} <= {ub}")
```

四种情况：

| `lowBound` | `upBound` | 输出 |
|-----------|----------|------|
| None | None | `x free` |
| 0 | None | `x >= 0` |
| None | 10 | `x <= 10` |
| 0 | 10 | `0 <= x <= 10` |

#### 整数/二元段

```python
if general_lines:
    lines.append("General")
    lines.extend(general_lines)

if binary_lines:
    lines.append("Binary")
    lines.extend(binary_lines)
```

输出：
```
General
  z
Binary
  b
```

`General` 段列出整数变量，`Binary` 段列出 0/1 变量。

### 系数格式化函数

#### `_format_coef`

```python
def _format_coef(coef: float) -> str:
    if coef == int(coef):
        return str(int(coef))  # 整数输出 3
    return str(coef)           # 浮点输出 3.5
```

```python
_format_coef(3.0)   # "3"
_format_coef(3.5)   # "3.5"
_format_coef(-2.0)  # "-2"
_format_coef(0.5)   # "0.5"
```

整数系数输出为整数形式，避免 `3.0` 这样的冗余小数。

#### `_format_terms`

```python
def _format_terms(terms: dict) -> str:
    parts = []
    for var, coef in terms.items():
        if coef == 1.0:
            parts.append(f"+ {var.name}")
        elif coef == -1.0:
            parts.append(f"- {var.name}")
        elif coef < 0:
            parts.append(f"- {_format_coef(abs(coef))} {var.name}")
        else:
            parts.append(f"+ {_format_coef(coef)} {var.name}")
    if not parts:
        return "0"
    result = " ".join(parts)
    if result.startswith("+ "):
        result = result[2:]  # 去掉开头的 "+ "
    return result
```

```python
# 系数 1：省略系数
_format_terms({x: 1.0})  # "x"

# 系数 -1：省略系数
_format_terms({x: -1.0})  # "- x"

# 正系数
_format_terms({x: 3.0})  # "3 x"

# 负系数
_format_terms({x: -2.0})  # "- 2 x"

# 多项
_format_terms({x: 3.0, y: 2.0})  # "3 x + 2 y"
_format_terms({x: 3.0, y: -2.0})  # "3 x - 2 y"
```

特殊处理系数 1 和 -1（省略系数），使输出更接近数学写法。

### 完整导出示例

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0, upBound=10)
z = mp.LpVariable("z", lowBound=0, cat=mp.LpInteger)
b = mp.LpVariable("b", cat=mp.LpBinary)

prob = mp.LpProblem("mixed", mp.LpMaximize)
prob += 3 * x + 2 * y + z + 5 * b
prob += 2 * x + y + z <= 100
prob += x + y + b == 10
prob += z + 2 * b >= 5

print(mp.write_lp(prob))
```

输出：

```
\ Project name: mixed
Maximize
  obj: 3 x + 2 y + 1 z + 5 b
Subject To
  c_0: 2 x + 1 y + 1 z <= 100
  c_1: 1 x + 1 y + 1 b = 10
  c_2: 1 z + 2 b >= 5
Bounds
  x >= 0
  0 <= y <= 10
  z >= 0
  0 <= b <= 1
General
  z
Binary
  b
End
```

---

## 约束自动命名详细说明

### 命名策略

```python
def addConstraint(self, constraint, name=None):
    if name is None:
        if constraint.name is None:
            name = f"c_{len(self.constraints)}"
        else:
            name = constraint.name
    constraint.name = name
    self.constraints[name] = constraint
```

命名优先级：

1. **显式 `name` 参数**：`addConstraint(con, name="my_con")` → `"my_con"`
2. **约束自带名称**：`con = x + y <= 10; con.name = "foo"` → `"foo"`
3. **自动生成**：`c_0`, `c_1`, `c_2`, ...

### 自动命名的序号分配

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob += x + y <= 10  # c_0
prob += x - y <= 5   # c_1
prob += 2 * x + y <= 20  # c_2

print(list(prob.constraints.keys()))  # ['c_0', 'c_1', 'c_2']
```

序号基于 `len(self.constraints)`，即当前约束数。添加第 N 个约束时，序号为 N（从 0 开始）。

### 混合命名

```python
prob = mp.LpProblem("demo", mp.LpMaximize)

prob += x + y <= 10                    # c_0（自动）
prob.addConstraint(x - y <= 5, name="custom")  # custom（显式）
prob += 2 * x + y <= 20               # c_2（自动，跳过 c_1）

print(list(prob.constraints.keys()))  # ['c_0', 'custom', 'c_2']
```

注意：自动命名使用 `len(self.constraints)`，所以添加 `custom` 后，下一个自动名是 `c_2`（因为此时有 2 个约束）。

### 命名冲突

```python
prob += x + y <= 10  # c_0
prob.addConstraint(x - y <= 5, name="c_0")  # 覆盖！
```

如果显式名称与已有名称冲突，会覆盖原约束。这是用户责任，minipulp 不检查冲突。

### 命名最佳实践

```python
# 推荐：语义命名
prob.addConstraint(原料用量 <= 100, name="原料约束")
prob.addConstraint(工时用量 <= 80, name="工时约束")

# 推荐：自动命名（简单问题）
prob += 2 * x + y <= 100
prob += x + y <= 80

# 不推荐：无意义的显式命名
prob.addConstraint(2 * x + y <= 100, name="con1")
prob.addConstraint(x + y <= 80, name="con2")
```

---

## 变量自动注册机制

### 注册时机

变量在以下情况自动注册：

1. `setObjective(expr)` — 目标函数中的变量
2. `addConstraint(con)` — 约束中的变量

```python
def setObjective(self, expr):
    ...
    self.objective = expr
    for var in expr.terms:
        self.addVariable(var)  # 注册目标变量

def addConstraint(self, constraint, name=None):
    ...
    for var in constraint.terms:
        self.addVariable(var)  # 注册约束变量
```

### `addVariable` 实现

```python
def addVariable(self, var: LpVariable) -> None:
    if var.name not in self._variables:
        self._variables[var.name] = var
```

用变量名作为 key，避免重复注册。如果同名变量已存在，跳过（但这可能导致问题，参见 Phase 1 的同名变量陷阱）。

### 注册示例

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
z = mp.LpVariable("z", lowBound=0)

print(prob.numVariables())  # 0

prob += 3 * x + 2 * y  # 注册 x, y
print(prob.numVariables())  # 2

prob += x + y <= 10    # x, y 已注册，z 未出现
print(prob.numVariables())  # 2

prob += z <= 5         # 注册 z
print(prob.numVariables())  # 3
```

### 未注册变量的行为

```python
prob = mp.LpProblem("demo", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)  # 未使用

prob += 3 * x
prob += x <= 10

prob.solve()
print(y.varValue)  # None — y 未参与问题，求解器未赋值
```

未注册的变量不参与求解，`varValue` 保持 `None`。

### `variables()` 的顺序

```python
def variables(self) -> list[LpVariable]:
    return list(self._variables.values())
```

`_variables` 是字典，Python 3.7+ 字典保持插入顺序。`variables()` 返回变量按注册顺序排列。

```python
prob += 3 * x + 2 * y  # 先注册 x，后注册 y
print([v.name for v in prob.variables()])  # ['x', 'y']
```

---

## 建模示例：生产计划

### 问题描述

工厂生产两种产品 A 和 B。产品 A 利润 30 元/件，产品 B 利润 20 元/件。生产受原料、工时、市场约束。

### 数据

```python
profit = {"A": 30, "B": 20}
resource_usage = {
    "A": {"原料": 2, "工时": 3},
    "B": {"原料": 1, "工时": 2},
}
capacity = {"原料": 100, "工时": 80}
max_demand = {"A": 40, "B": None}  # B 无市场限制
```

### 数学模型

$$
\begin{aligned}
\max \quad & 30 x_A + 20 x_B \\
\text{s.t.} \quad & 2 x_A + 1 x_B \leq 100 \quad \text{(原料)} \\
& 3 x_A + 2 x_B \leq 80 \quad \text{(工时)} \\
& x_A \leq 40 \quad \text{(市场)} \\
& x_A, x_B \geq 0
\end{aligned}
$$

### 代码

```python
import minipulp as mp

# 数据
profit = {"A": 30, "B": 20}
resource_usage = {
    "A": {"原料": 2, "工时": 3},
    "B": {"原料": 1, "工时": 2},
}
capacity = {"原料": 100, "工时": 80}
max_demand = {"A": 40, "B": None}

# 变量
x = mp.LpVariable.dicts("x", profit.keys(), lowBound=0)

# 问题
prob = mp.LpProblem("production", mp.LpMaximize)
prob += mp.lpSum(profit[p] * x[p] for p in profit)

# 资源约束
for r in capacity:
    prob += mp.lpSum(resource_usage[p][r] * x[p] for p in profit) <= capacity[r]

# 市场约束
for p in profit:
    if max_demand[p] is not None:
        prob += x[p] <= max_demand[p]

# 求解
prob.solve()
print(f"最大利润: {prob.objective.value()}")
for p in profit:
    print(f"  {p}: {x[p].varValue:.1f} 件")
```

### LP 文件输出

```python
print(mp.write_lp(prob))
# \ Project name: production
# Maximize
#   obj: 30 x_A + 20 x_B
# Subject To
#   c_0: 2 x_A + 1 x_B <= 100
#   c_1: 3 x_A + 2 x_B <= 80
#   c_2: 1 x_A <= 40
# Bounds
#   x_A >= 0
#   x_B >= 0
# End
```

---

## 建模示例：饮食问题

### 问题描述

用最低成本配置满足营养需求的食谱。

### 数据

```python
foods = ["燕麦", "牛奶", "面包"]
nutrients = ["热量", "蛋白质"]

nutrition = {
    "燕麦": {"热量": 110, "蛋白质": 4},
    "牛奶": {"热量": 120, "蛋白质": 8},
    "面包": {"热量": 80,  "蛋白质": 4},
}
cost = {"燕麦": 0.5, "牛奶": 0.8, "面包": 0.2}
min_nutrition = {"热量": 2000, "蛋白质": 50}
```

### 代码

```python
import minipulp as mp

# 数据（如上）

# 变量
x = mp.LpVariable.dicts("x", foods, lowBound=0)

# 问题
prob = mp.LpProblem("diet", mp.LpMinimize)
prob += mp.lpSum(cost[f] * x[f] for f in foods)

for k in nutrients:
    prob += mp.lpSum(nutrition[f][k] * x[f] for f in foods) >= min_nutrition[k]

# 求解
prob.solve()
print(f"最低成本: {prob.objective.value():.2f} 元")
for f in foods:
    print(f"  {f}: {x[f].varValue:.2f}")
```

### LP 文件输出

```python
print(mp.write_lp(prob))
# \ Project name: diet
# Minimize
#   obj: 0.5 x_燕麦 + 0.8 x_牛奶 + 0.2 x_面包
# Subject To
#   c_0: 110 x_燕麦 + 120 x_牛奶 + 80 x_面包 >= 2000
#   c_1: 4 x_燕麦 + 8 x_牛奶 + 4 x_面包 >= 50
# Bounds
#   x_燕麦 >= 0
#   x_牛奶 >= 0
#   x_面包 >= 0
# End
```

---

## 建模示例：资源分配

### 问题描述

将预算分配到多个项目，最大化总收益。每个项目有最小投入和最大投入限制，收益与投入成正比但收益率不同。

### 数据

```python
projects = ["P1", "P2", "P3", "P4"]
return_rate = {"P1": 0.15, "P2": 0.12, "P3": 0.18, "P4": 0.10}
min_invest = {"P1": 100, "P2": 200, "P3": 150, "P4": 0}
max_invest = {"P1": 500, "P2": 800, "P3": 600, "P4": 400}
total_budget = 1000
```

### 代码

```python
import minipulp as mp

# 数据（如上）

# 变量：各项目投资额
x = {}
for p in projects:
    x[p] = mp.LpVariable(f"x_{p}", lowBound=min_invest[p], upBound=max_invest[p])

# 问题
prob = mp.LpProblem("invest", mp.LpMaximize)
prob += mp.lpSum(return_rate[p] * x[p] for p in projects)

# 预算约束
prob += mp.lpSum(x[p] for p in projects) <= total_budget

# 求解
prob.solve()
print(f"最大收益: {prob.objective.value():.2f}")
print(f"总投资: {sum(x[p].varValue for p in projects):.2f}")
for p in projects:
    print(f"  {p}: {x[p].varValue:.2f} (收益 {return_rate[p] * x[p].varValue:.2f})")
```

### LP 文件输出

```python
print(mp.write_lp(prob))
# \ Project name: invest
# Maximize
#   obj: 0.15 x_P1 + 0.12 x_P2 + 0.18 x_P3 + 0.1 x_P4
# Subject To
#   c_0: 1 x_P1 + 1 x_P2 + 1 x_P3 + 1 x_P4 <= 1000
# Bounds
#   100 <= x_P1 <= 500
#   200 <= x_P2 <= 800
#   150 <= x_P3 <= 600
#   0 <= x_P4 <= 400
# End
```

### 带互斥约束的扩展

如果项目 P1 和 P3 互斥（不能同时投资）：

```python
# 引入二元变量
y = mp.LpVariable.dicts("y", projects, cat=mp.LpBinary)

# 互斥约束：y_P1 + y_P3 <= 1
prob += y["P1"] + y["P3"] <= 1

# 关联约束：投资额受 y 控制
M = 1000  # 大常数
for p in projects:
    prob += x[p] <= M * y[p]  # y=0 时 x=0
    prob += x[p] >= min_invest[p] * y[p]  # y=1 时 x >= min

prob.solve(solver=mp.solvers.PULP_CBC_CMD())
```

---

## 测试

```bash
uv run pytest tests/test_problem.py tests/test_lp_io.py -v
```

35 个测试覆盖：`+=` 语法糖、约束自动命名、变量自动注册、LP 文件导出格式。

### 测试示例

```python
def test_iadd_objective():
    prob = LpProblem("demo", LpSense.MAXIMIZE)
    x = LpVariable("x", lowBound=0)
    prob += 3 * x
    assert prob.objective.terms == {x: 3.0}

def test_iadd_constraint():
    prob = LpProblem("demo", LpSense.MAXIMIZE)
    x = LpVariable("x", lowBound=0)
    prob += x <= 10
    assert "c_0" in prob.constraints
    assert prob.constraints["c_0"].terms == {x: 1.0}
    assert prob.constraints["c_0"].constant == -10.0

def test_auto_naming():
    prob = LpProblem("demo", LpSense.MAXIMIZE)
    x = LpVariable("x", lowBound=0)
    prob += x <= 10
    prob += x <= 20
    assert list(prob.constraints.keys()) == ["c_0", "c_1"]

def test_write_lp():
    prob = LpProblem("demo", LpSense.MAXIMIZE)
    x = LpVariable("x", lowBound=0)
    y = LpVariable("y", lowBound=0)
    prob += 3 * x + 2 * y
    prob += x + y <= 10
    lp_text = write_lp(prob)
    assert "Maximize" in lp_text
    assert "Subject To" in lp_text
    assert "Bounds" in lp_text
    assert "End" in lp_text
```

---

## 总结

Phase 2 的约束与问题系统是 minipulp 的建模核心，其设计要点：

1. **约束归一化**：`lhs <sense> 0` 统一形式，简化求解器接口
2. **`+=` 语法糖**：根据类型分派，目标与约束统一添加
3. **自动命名**：`c_0`, `c_1`, ... 无需手动命名
4. **自动注册**：变量自动收集，无需手动管理
5. **LP 文件导出**：CPLEX LP 格式，跨求解器通用
6. **系数格式化**：特殊处理 1 和 -1，输出接近数学写法

这些设计让用户能用最自然的 Python 语法建模，同时生成标准化的 LP 文件供求解器使用。
