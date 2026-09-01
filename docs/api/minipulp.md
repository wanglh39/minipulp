# API 参考

minipulp 的公开 API，与 PuLP 兼容。

---

## 顶层导入

```python
import minipulp as mp
```

---

## 变量

### `LpVariable`

决策变量，继承 `LpAffineExpression`。

```python
LpVariable(name, lowBound=None, upBound=None, cat=LpContinuous)
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `name` | `str` | — | 变量名（唯一标识符） |
| `lowBound` | `float \| None` | `None` | 下界，None 表示无下界 |
| `upBound` | `float \| None` | `None` | 上界，None 表示无上界 |
| `cat` | `LpCat` | `LpContinuous` | 变量类别 |

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 变量名 |
| `lowBound` | `float \| None` | 下界 |
| `upBound` | `float \| None` | 上界 |
| `cat` | `LpCat` | 变量类别 |
| `varValue` | `float \| None` | 求解后回填的解值 |

**类方法**：

#### `LpVariable.dicts(name, indices, lowBound=None, upBound=None, cat=LpContinuous)`

批量创建一维变量字典。

```python
x = mp.LpVariable.dicts("x", range(10), lowBound=0)
# x[0].name == "x_0", x[1].name == "x_1", ...
```

**返回**：`dict[index, LpVariable]`

#### `LpVariable.matrix(name, rows, cols, lowBound=None, upBound=None, cat=LpContinuous)`

批量创建二维变量矩阵。

```python
x = mp.LpVariable.matrix("x", range(3), range(4), lowBound=0)
# x[0][0].name == "x_0_0", x[2][3].name == "x_2_3"
```

**返回**：`dict[row, dict[col, LpVariable]]`

---

## 表达式

### `LpAffineExpression`

仿射表达式：`sum(coef_i * var_i) + const`。

```python
LpAffineExpression(terms=None, const=0.0)
```

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `terms` | `dict[LpVariable, float]` | 变量系数字典 |
| `const` | `float` | 常数项 |

**方法**：

| 方法 | 返回 | 说明 |
|------|------|------|
| `value()` | `float \| None` | 计算表达式值（需变量已求解） |
| `is_constant()` | `bool` | 是否为纯常数 |

**运算符**：

| 运算 | 示例 | 结果 |
|------|------|------|
| `expr + expr` | `x + y` | `LpAffineExpression` |
| `expr + num` | `x + 5` | `LpAffineExpression` |
| `num * expr` | `3 * x` | `LpAffineExpression` |
| `expr - expr` | `x - y` | `LpAffineExpression` |
| `expr / num` | `x / 2` | `LpAffineExpression` |
| `-expr` | `-x` | `LpAffineExpression` |
| `expr <= num` | `x <= 5` | `LpConstraint` |
| `expr >= num` | `x >= 5` | `LpConstraint` |
| `expr == num` | `x == 5` | `LpConstraint` |

### `lpSum(vector)`

高效求和函数，避免 `sum()` 的中间对象创建。

```python
mp.lpSum([3 * x, 2 * y, 5])  # 3*x + 2*y + 5
mp.lpSum(cost[i] * x[i] for i in range(n))  # 生成器也支持
```

**返回**：`LpAffineExpression`

---

## 约束

### `LpConstraint`

线性约束：`lhs (<=|==|>=) 0`。

通常由运算符自动构造，不直接实例化。

```python
con = 2 * x + y <= 100  # LpConstraint
```

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `lhs` | `LpAffineExpression` | 归一化后的左侧表达式 |
| `sense` | `LpConstraintSense` | 比较方向 |
| `name` | `str \| None` | 约束名 |
| `terms` | `dict` | 左侧表达式的变量系数字典 |
| `constant` | `float` | 左侧表达式的常数项 |

---

## 问题

### `LpProblem`

线性规划问题容器。

```python
LpProblem(name="problem", sense=LpMinimize)
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `name` | `str` | `"problem"` | 问题名 |
| `sense` | `LpSense` | `LpMinimize` | 目标方向 |

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 问题名 |
| `sense` | `LpSense` | 目标方向 |
| `objective` | `LpAffineExpression \| None` | 目标函数 |
| `constraints` | `dict[str, LpConstraint]` | 约束字典 |
| `status` | `LpStatus` | 求解状态 |
| `status_msg` | `str` | 求解状态消息 |

**方法**：

#### `addConstraint(constraint, name=None)`

添加约束。

```python
prob.addConstraint(2 * x + y <= 100, name="supply")
```

#### `setObjective(expr)`

设置目标函数。

```python
prob.setObjective(3 * x + 2 * y)
```

#### `variables()`

返回问题中所有变量列表。

#### `solve(solver=None)`

求解问题。

```python
prob.solve()                          # 默认求解器
prob.solve(solver=SimplexCore())      # 纯 Python
prob.solve(solver=SimplexCpp())       # C++
prob.solve(solver=PULP_CBC_CMD())     # CBC
```

**返回**：`LpStatus`

#### `valid()`

检查问题是否已设置目标函数。

#### `__iadd__(other)`

`+=` 语法糖：表达式→目标，约束→添加约束。

```python
prob += 3 * x + 2 * y          # 设置目标
prob += 2 * x + y <= 100       # 添加约束
```

---

## 求解器

### `SimplexCore`

纯 Python 两阶段单纯形法求解器。

```python
from minipulp.solvers import SimplexCore
prob.solve(solver=SimplexCore())
```

### `SimplexCpp`

C++ 两阶段单纯形法求解器（需编译 `_native` 扩展）。

```python
from minipulp.solvers import SimplexCpp
prob.solve(solver=SimplexCpp())
```

### `PULP_CBC_CMD`

CBC 命令行求解器（需安装 CBC）。

```python
from minipulp.solvers import PULP_CBC_CMD
prob.solve(solver=PULP_CBC_CMD(msg=True, timeLimit=60))
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `path` | `str \| None` | `None` | CBC 路径，None 自动查找 |
| `msg` | `bool` | `False` | 是否显示 CBC 输出 |
| `timeLimit` | `int \| None` | `None` | 时间上限（秒） |

---

## 常量

### 目标方向

```python
mp.LpMinimize  # 最小化 (1)
mp.LpMaximize  # 最大化 (-1)
```

### 变量类别

```python
mp.LpContinuous  # 连续变量 (0)
mp.LpInteger     # 整数变量 (1)
mp.LpBinary      # 二元变量 (2)
```

### 求解状态

```python
mp.LpStatusOptimal     # 最优 (1)
mp.LpStatusInfeasible  # 不可行 (-1)
mp.LpStatusUnbounded   # 无界 (-2)
mp.LpStatusUndefined   # 未定义 (-3)
mp.LpStatusNotSolved   # 未求解 (0)
```

### 约束方向

```python
mp.LpConstraintSense.LE  # <= (0)
mp.LpConstraintSense.EQ  # == (1)
mp.LpConstraintSense.GE  # >= (2)
```

---

## I/O

### `write_lp(problem)`

将问题序列化为 CPLEX LP 格式文本。

```python
text = mp.write_lp(prob)
print(text)
```

**返回**：`str`

---

## 完整 API 列表

```python
# 变量
mp.LpVariable
mp.LpVariable.dicts
mp.LpVariable.matrix

# 表达式
mp.LpAffineExpression
mp.LpElement
mp.lpSum

# 约束
mp.LpConstraint

# 问题
mp.LpProblem

# I/O
mp.write_lp

# 常量
mp.LpMinimize
mp.LpMaximize
mp.LpContinuous
mp.LpInteger
mp.LpBinary
mp.LpStatusOptimal
mp.LpStatusInfeasible
mp.LpStatusUnbounded
mp.LpStatusNotSolved
mp.LpStatusUndefined
mp.LpStatusToMsg

# 求解器
mp.solvers.SimplexCore
mp.solvers.SimplexCpp
mp.solvers.PULP_CBC_CMD
```
