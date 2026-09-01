# Phase 5 — 高级功能

> 批量变量创建、`lpSum` 优化、运输问题等大规模建模工具。
>
> 本篇对应 `src/minipulp/elements.py` 中的 `dicts`/`matrix`/`lpSum`。

---

## 目录

- [批量变量创建](#批量变量创建)
- [lpSum 高效求和](#lpsum-高效求和)
- [运输问题](#运输问题)
- [指派问题](#指派问题)
- [生产计划](#生产计划)
- [测试](#测试)

---

## 批量变量创建

### `LpVariable.dicts` — 一维变量字典

```python
@classmethod
def dicts(cls, name, indices, lowBound=None, upBound=None, cat=LpContinuous) -> dict:
    return {i: cls(f"{name}_{i}", lowBound, upBound, cat) for i in indices}
```

**用途**：按索引集合批量创建变量，返回 `{index: LpVariable}` 字典。

```python
import minipulp as mp

# 创建 10 个非负变量
x = mp.LpVariable.dicts("x", range(10), lowBound=0)
# x[0].name == "x_0", x[1].name == "x_1", ..., x[9].name == "x_9"
```

索引可以是任意可哈希对象，适配灵活的建模场景：

```python
# 用城市对作为索引
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
# 3x4 运输矩阵
x = mp.LpVariable.matrix("x", range(3), range(4), lowBound=0)
# x[0][0].name == "x_0_0"
# x[2][3].name == "x_2_3"
```

### 命名规则

| 方法 | 变量名格式 | 示例 |
|------|---------|------|
| `dicts` | `{name}_{index}` | `x_0`, `x_1`, `x_2` |
| `matrix` | `{name}_{row}_{col}` | `x_0_0`, `x_1_2`, `x_2_3` |

命名规则确保变量名唯一，可安全用作字典 key 和 LP 文件输出标识符。

---

## lpSum 高效求和

### 问题：`sum()` 的性能瓶颈

Python 内置 `sum()` 对表达式列表求和时，`LpAffineExpression` 的 `__add__` 每次都创建新对象，
对 N 个表达式求和需要 N-1 次构造，每次拷贝并合并字典。

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

| 方法 | 时间复杂度 | 空间复杂度 | 中间对象数 |
|------|-----------|-----------|---------|
| `sum(vector)` | $O(N \cdot \bar{T})$ | $O(N \cdot \bar{T})$ | $N-1$ |
| `lpSum(vector)` | $O(\sum T_i)$ | $O(\sum T_i)$ | $1$ |

其中 $T_i$ 是第 $i$ 个表达式的项数，$\bar{T}$ 是平均项数。

### 实测

对 500 个变量的求和，`lpSum` 比 `sum` 快约 5-10x：

```python
import time
from minipulp import LpVariable, lpSum

x = LpVariable.dicts("x", range(500), lowBound=0)
exprs = [3 * x[i] for i in range(500)]

t0 = time.perf_counter()
for _ in range(100):
    sum(exprs)
t_sum = time.perf_counter() - t0

t0 = time.perf_counter()
for _ in range(100):
    lpSum(exprs)
t_lpsum = time.perf_counter() - t0

print(f"sum:   {t_sum:.3f}s")
print(f"lpSum: {t_lpsum:.3f}s")
print(f"Speedup: {t_sum / t_lpsum:.1f}x")
```

---

## 运输问题

运输问题是经典 LP 应用，展示 `dicts` + `lpSum` 的典型用法。

### 问题描述

有 $m$ 个工厂和 $n$ 个客户。工厂 $i$ 的供应量为 $s_i$，客户 $j$ 的需求量为 $d_j$，
从工厂 $i$ 到客户 $j$ 的单位运输成本为 $c_{ij}$。求最小总成本的运输方案。

$$
\begin{aligned}
\min \quad & \sum_{i,j} c_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_j x_{ij} \leq s_i \quad \forall i \quad \text{(供应约束)} \\
& \sum_i x_{ij} \geq d_j \quad \forall j \quad \text{(需求约束)} \\
& x_{ij} \geq 0
\end{aligned}
$$

### 建模

```python
import minipulp as mp

# 数据
supply = {"f1": 30, "f2": 40, "f3": 30}
demand = {"c1": 20, "c2": 25, "c3": 25, "c4": 30}
cost = {
    ("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4, ("f1", "c4"): 5,
    ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1, ("f2", "c4"): 4,
    ("f3", "c1"): 4, ("f3", "c2"): 3, ("f3", "c3"): 2, ("f3", "c4"): 1,
}

# 变量：x[i][j] = 从工厂 i 运到客户 j 的量
x = mp.LpVariable.matrix("x", supply.keys(), demand.keys(), lowBound=0)

# 问题
prob = mp.LpProblem("transport", mp.LpMinimize)
prob += mp.lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)

# 供应约束：每个工厂运出量 ≤ 供应量
for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) <= supply[i]

# 需求约束：每个客户收到量 ≥ 需求量
for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) >= demand[j]

# 求解
prob.solve()
print(f"总成本: {prob.objective.value()}")
for i in supply:
    for j in demand:
        if x[i][j].varValue > 0:
            print(f"  {i} → {j}: {x[i][j].varValue}")
```

---

## 指派问题

将 $n$ 个任务分配给 $n$ 个工人，每个工人恰好一个任务，最小化总成本。

$$
\begin{aligned}
\min \quad & \sum_{i,j} c_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_j x_{ij} = 1 \quad \forall i \quad \text{(每个工人一个任务)} \\
& \sum_i x_{ij} = 1 \quad \forall j \quad \text{(每个任务一个工人)} \\
& x_{ij} \in \{0, 1\}
\end{aligned}
$$

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

cost = [
    [9, 2, 7, 8],
    [6, 4, 3, 7],
    [5, 8, 1, 8],
    [7, 6, 9, 4],
]

n = len(cost)
x = mp.LpVariable.matrix("x", range(n), range(n), cat=mp.LpBinary)

prob = mp.LpProblem("assign", mp.LpMinimize)
prob += mp.lpSum(cost[i][j] * x[i][j] for i in range(n) for j in range(n))

for i in range(n):
    prob += mp.lpSum(x[i][j] for j in range(n)) == 1  # 每个工人一个任务

for j in range(n):
    prob += mp.lpSum(x[i][j] for i in range(n)) == 1  # 每个任务一个工人

prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
for i in range(n):
    for j in range(n):
        if x[i][j].varValue > 0.5:
            print(f"  工人 {i} → 任务 {j}")
```

---

## 生产计划

多产品、多资源约束的生产计划问题。

```python
import minipulp as mp

# 产品列表
products = ["A", "B", "C"]
# 资源列表
resources = ["原料", "工时", "电力"]

# 利润
profit = {"A": 30, "B": 20, "C": 40}
# 资源消耗 [product][resource]
usage = {
    "A": {"原料": 2, "工时": 3, "电力": 1},
    "B": {"原料": 1, "工时": 2, "电力": 2},
    "C": {"原料": 3, "工时": 1, "电力": 1},
}
# 资源上限
capacity = {"原料": 100, "工时": 80, "电力": 60}

# 变量：各产品产量
x = mp.LpVariable.dicts("x", products, lowBound=0)

# 问题
prob = mp.LpProblem("production", mp.LpMaximize)
prob += mp.lpSum(profit[p] * x[p] for p in products)

for r in resources:
    prob += mp.lpSum(usage[p][r] * x[p] for p in products) <= capacity[r]

prob.solve()
print(f"最大利润: {prob.objective.value()}")
for p in products:
    print(f"  {p}: {x[p].varValue}")
```

---

## 测试

```bash
uv run pytest tests/test_advanced.py -v
```

12 个测试覆盖：`dicts`/`matrix` 批量创建、`lpSum` 正确性与性能、运输问题端到端。
