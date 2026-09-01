# Phase 2 — 约束与问题

> `LpProblem` 容器与 LP 文件格式导出。
>
> 本篇对应 `src/minipulp/problem.py`、`src/minipulp/constraints.py` 和 `src/minipulp/lp_io.py`。

---

## 目录

- [LpConstraint — 约束对象](#lpconstraint--约束对象)
- [LpProblem — 问题容器](#lpproblem--问题容器)
- [+= 语法糖](#-语法糖)
- [LP 文件格式导出](#lp-文件格式导出)
- [完整示例](#完整示例)
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
\ Problem name: demo
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
| `\ Problem name:` | 注释行，问题名 |
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
    lines.append(f"\\ Problem name: {problem.name}")

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
# \ Problem name: production
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

## 测试

```bash
uv run pytest tests/test_problem.py tests/test_lp_io.py -v
```

35 个测试覆盖：`+=` 语法糖、约束自动命名、变量自动注册、LP 文件导出格式。
