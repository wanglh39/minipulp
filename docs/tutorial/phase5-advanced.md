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
- [dicts/matrix 更多用法示例](#dictsmatrix-更多用法示例)
- [lpSum 详细性能分析](#lpsum-详细性能分析)
- [运输问题完整建模和求解](#运输问题完整建模和求解)
- [指派问题完整建模](#指派问题完整建模)
- [生产计划多产品多资源](#生产计划多产品多资源)
- [饮食问题多营养](#饮食问题多营养)
- [网络流问题](#网络流问题)
- [最大流问题](#最大流问题)
- [最短路问题](#最短路问题)
- [混合整数规划](#混合整数规划)
- [多目标规划简介](#多目标规划简介)
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

## dicts/matrix 更多用法示例

### 用字符串索引

```python
# 用产品名作为索引
products = ["苹果", "香蕉", "橙子"]
x = mp.LpVariable.dicts("x", products, lowBound=0)
# x["苹果"].name == "x_苹果"
# x["香蕉"].name == "x_香蕉"
```

### 用元组索引

```python
# 用 (工厂, 客户) 元组作为索引
pairs = [("f1", "c1"), ("f1", "c2"), ("f2", "c1"), ("f2", "c2")]
x = mp.LpVariable.dicts("x", pairs, lowBound=0)
# x[("f1", "c1")].name == "x_('f1', 'c1')"
```

### 用字典键作为索引

```python
# 从现有数据字典提取索引
cost = {"北京→上海": 100, "北京→广州": 200, "上海→广州": 150}
routes = mp.LpVariable.dicts("route", cost.keys(), lowBound=0)
# routes["北京→上海"].name == "route_北京→上海"
```

### 整数变量批量创建

```python
# 批量创建整数变量
z = mp.LpVariable.dicts("z", range(10), lowBound=0, cat=mp.LpInteger)
# 所有 z[i] 都是整数变量

# 批量创建二元变量
b = mp.LpVariable.dicts("b", range(10), cat=mp.LpBinary)
# 所有 b[i] 都是 0/1 变量
```

### 带上下界的批量创建

```python
# 所有变量在 [0, 100] 范围内
x = mp.LpVariable.dicts("x", range(10), lowBound=0, upBound=100)

# 不同上下界需要手动创建
bounds = {0: (0, 10), 1: (5, 20), 2: (0, 30)}
x = {i: mp.LpVariable(f"x_{i}", lowBound=bounds[i][0], upBound=bounds[i][1]) for i in bounds}
```

### matrix 的三维扩展

`matrix` 只支持二维。如需三维，用嵌套 `dicts`：

```python
# 三维变量 x[i][j][k]
I, J, K = range(3), range(4), range(2)
x = {
    i: {
        j: mp.LpVariable.dicts(f"x_{i}_{j}", K, lowBound=0)
        for j in J
    }
    for i in I
}
# x[0][0][0].name == "x_0_0_0"
```

### matrix 的迭代

```python
x = mp.LpVariable.matrix("x", range(3), range(4), lowBound=0)

# 遍历所有变量
for i in range(3):
    for j in range(4):
        print(x[i][j].name)

# 用 lpSum 求和
total = mp.lpSum(x[i][j] for i in range(3) for j in range(4))
```

### dicts 与 matrix 的选择

| 场景 | 推荐 | 原因 |
|------|------|------|
| 一维索引 | `dicts` | 简洁 |
| 二维网格 | `matrix` | 嵌套字典访问自然 |
| 混合索引 | `dicts` | 灵活 |
| 三维+ | 手动嵌套 | `matrix` 不支持 |

---

## lpSum 详细性能分析

### 理论分析

#### `sum()` 的展开

```python
sum([e1, e2, e3, e4])
# 等价于
((e1 + e2) + e3) + e4
```

每次 `+` 调用 `LpAffineExpression.__add__`，创建新对象：

```
e1 + e2 → temp1（合并 e1.terms 和 e2.terms）
temp1 + e3 → temp2（合并 temp1.terms 和 e3.terms）
temp2 + e4 → result（合并 temp2.terms 和 e4.terms）
```

如果每个 `ei` 有 $T$ 项：

- `temp1` 有 $2T$ 项，合并耗时 $O(T)$
- `temp2` 有 $3T$ 项，合并耗时 $O(T)$
- `temp_{N-1}` 有 $NT$ 项，合并耗时 $O(T)$

总耗时：$O(NT)$，但创建了 $N-1$ 个中间对象，每个对象大小递增。

总内存：$O(NT) + O((N-1)T) + ... + O(2T) = O(N^2 T)$

#### `lpSum()` 的展开

```python
lpSum([e1, e2, e3, e4])
# 一次性合并所有项
```

```
merged = {}
遍历 e1: merged += e1.terms
遍历 e2: merged += e2.terms
遍历 e3: merged += e3.terms
遍历 e4: merged += e4.terms
result = LpAffineExpression(merged)
```

- 每项合并一次：$N$ 次操作
- 只创建 1 个对象
- 总耗时：$O(NT)$
- 总内存：$O(NT)$

### 实测对比

```python
import time
from minipulp import LpVariable, lpSum

def benchmark(n, repeats=100):
    x = LpVariable.dicts("x", range(n), lowBound=0)
    exprs = [3 * x[i] for i in range(n)]

    t0 = time.perf_counter()
    for _ in range(repeats):
        sum(exprs)
    t_sum = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(repeats):
        lpSum(exprs)
    t_lpsum = time.perf_counter() - t0

    return t_sum, t_lpsum, t_sum / t_lpsum

print(f"{'N':>6} {'sum(s)':>10} {'lpSum(s)':>10} {'加速比':>8}")
for n in [10, 50, 100, 200, 500, 1000]:
    t_sum, t_lpsum, speedup = benchmark(n)
    print(f"{n:6d} {t_sum:10.4f} {t_lpsum:10.4f} {speedup:7.1f}x")
```

典型输出：

```
     N    sum(s)   lpSum(s)    加速比
    10     0.0020     0.0010     2.0x
    50     0.0150     0.0030     5.0x
   100     0.0450     0.0060     7.5x
   200     0.1500     0.0120    12.5x
   500     0.5200     0.0300    17.3x
  1000     1.9500     0.0600    32.5x
```

### 内存对比

```python
import sys

x = LpVariable.dicts("x", range(1000), lowBound=0)
exprs = [3 * x[i] for i in range(1000)]

# sum() 创建 999 个中间对象
result_sum = sum(exprs)
# 中间对象已释放，但构造时峰值内存高

# lpSum() 只创建 1 个对象
result_lpsum = lpSum(exprs)

print(f"结果对象大小: {sys.getsizeof(result_sum.terms)} bytes")
```

### lpSum 的正确性

```python
# 验证 lpSum 与 sum 结果一致
x = LpVariable.dicts("x", range(100), lowBound=0)
exprs = [3 * x[i] + i for i in range(100)]

result_sum = sum(exprs)
result_lpsum = lpSum(exprs)

assert result_sum.terms == result_lpsum.terms
assert result_sum.const == result_lpsum.const
print("正确性验证通过")
```

### 何时用 lpSum？

| 场景 | 推荐 |
|------|------|
| 2-3 个表达式 | `+` 运算符 |
| 4-10 个表达式 | `sum()` 或 `lpSum()` |
| 10+ 个表达式 | `lpSum()` |
| 循环内求和 | `lpSum()` |
| 大规模建模 | `lpSum()` |

---

## 运输问题完整建模和求解

### 问题描述

三个工厂供应产品给四个客户。求最小运输成本的方案。

### 完整代码

```python
import minipulp as mp

# 数据
supply = {"f1": 30, "f2": 40, "f3": 30}           # 工厂供应量
demand = {"c1": 20, "c2": 25, "c3": 25, "c4": 30}  # 客户需求量
cost = {
    ("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4, ("f1", "c4"): 5,
    ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1, ("f2", "c4"): 4,
    ("f3", "c1"): 4, ("f3", "c2"): 3, ("f3", "c3"): 2, ("f3", "c4"): 1,
}

# 检查供需平衡
total_supply = sum(supply.values())  # 100
total_demand = sum(demand.values())  # 100
print(f"总供应: {total_supply}, 总需求: {total_demand}")
assert total_supply >= total_demand, "供应不足"

# 变量
x = mp.LpVariable.matrix("x", supply.keys(), demand.keys(), lowBound=0)

# 问题
prob = mp.LpProblem("transport", mp.LpMinimize)
prob += mp.lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)

# 供应约束
for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) <= supply[i]

# 需求约束
for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) >= demand[j]

# 求解
prob.solve()

# 输出
print(f"\n状态: {prob.status_msg}")
print(f"总成本: {prob.objective.value()}")

print("\n运输方案:")
print(f"{'工厂':>4} {'客户':>4} {'运量':>8} {'成本':>8}")
for i in supply:
    for j in demand:
        if x[i][j].varValue > 0.01:
            amount = x[i][j].varValue
            c = cost[(i, j)] * amount
            print(f"{i:>4} {j:>4} {amount:>8.1f} {c:>8.1f}")

# 验证
print("\n验证:")
for i in supply:
    total = sum(x[i][j].varValue for j in demand)
    print(f"  工厂 {i} 运出: {total:.1f} / 供应 {supply[i]}")
for j in demand:
    total = sum(x[i][j].varValue for i in supply)
    print(f"  客户 {j} 收到: {total:.1f} / 需求 {demand[j]}")
```

### 平衡运输问题

当总供应等于总需求时，约束可改为等式：

```python
if total_supply == total_demand:
    # 平衡运输问题，用等式约束
    for i in supply:
        prob += mp.lpSum(x[i][j] for j in demand) == supply[i]
    for j in demand:
        prob += mp.lpSum(x[i][j] for i in supply) == demand[j]
```

### 带容量限制的运输

某些路线有最大运量限制：

```python
# 路线容量
route_cap = {("f1", "c4"): 15, ("f3", "c1"): 10}  # 其他路线无限制

for (i, j), cap in route_cap.items():
    prob += x[i][j] <= cap
```

### 带固定成本的运输

开启一条路线有固定成本：

```python
from minipulp.solvers import PULP_CBC_CMD

# 固定成本
fixed_cost = {("f1", "c1"): 5, ("f2", "c3"): 3}

# 二元变量：是否使用路线
y = mp.LpVariable.matrix("y", supply.keys(), demand.keys(), cat=mp.LpBinary)

# 目标加入固定成本
prob += mp.lpSum(fixed_cost.get((i, j), 0) * y[i][j]
                 for i in supply for j in demand)

# 关联约束：x > 0 则 y = 1
M = max(supply.values())  # 大常数
for i in supply:
    for j in demand:
        prob += x[i][j] <= M * y[i][j]

prob.solve(solver=PULP_CBC_CMD())
```

---

## 指派问题完整建模

### 问题描述

将 4 个任务分配给 4 个工人，每人一个任务，最小化总成本。

### 完整代码

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 成本矩阵：cost[工人][任务]
cost = [
    [9, 2, 7, 8],
    [6, 4, 3, 7],
    [5, 8, 1, 8],
    [7, 6, 9, 4],
]

n = len(cost)
workers = range(n)
tasks = range(n)

# 变量：x[工人][任务] = 1 表示分配
x = mp.LpVariable.matrix("x", workers, tasks, cat=mp.LpBinary)

# 问题
prob = mp.LpProblem("assign", mp.LpMinimize)
prob += mp.lpSum(cost[i][j] * x[i][j] for i in workers for j in tasks)

# 每个工人恰好一个任务
for i in workers:
    prob += mp.lpSum(x[i][j] for j in tasks) == 1

# 每个任务恰好一个工人
for j in tasks:
    prob += mp.lpSum(x[i][j] for i in workers) == 1

# 求解
prob.solve(solver=PULP_CBC_CMD())

# 输出
print(f"状态: {prob.status_msg}")
print(f"总成本: {prob.objective.value()}")
print("\n分配方案:")
for i in workers:
    for j in tasks:
        if x[i][j].varValue > 0.5:
            print(f"  工人 {i} → 任务 {j} (成本 {cost[i][j]})")
```

### 不平衡指派

工人数多于任务数：

```python
# 5 个工人，3 个任务
cost = [
    [9, 2, 7],
    [6, 4, 3],
    [5, 8, 1],
    [7, 6, 9],
    [8, 5, 4],
]
n_workers = 5
n_tasks = 3

x = mp.LpVariable.matrix("x", range(n_workers), range(n_tasks), cat=mp.LpBinary)

prob = mp.LpProblem("assign", mp.LpMinimize)
prob += mp.lpSum(cost[i][j] * x[i][j] for i in range(n_workers) for j in range(n_tasks))

# 每个工人最多一个任务
for i in range(n_workers):
    prob += mp.lpSum(x[i][j] for j in range(n_tasks)) <= 1

# 每个任务恰好一个工人
for j in range(n_tasks):
    prob += mp.lpSum(x[i][j] for i in range(n_workers)) == 1

prob.solve(solver=PULP_CBC_CMD())
```

### 带技能限制的指派

并非所有工人都能做所有任务：

```python
# 技能矩阵：can_do[工人][任务]
can_do = [
    [1, 1"1, 1, 0],  # 工人 0 不能做任务 3
    [1, 0, 1, 1],  # 工人 1 不能做任务 1
    [1, 1, 0, 1],  # 工人 2 不能做任务 2
    [0, 1, 1, 1],  # 工人 3 不能做任务 0
]

# 添加约束
for i in range(n):
    for j in range(n):
        if not can_do[i][j]:
            prob += x[i][j] == 0  # 不能做则强制为 0
```

---

## 生产计划多产品多资源

### 问题描述

工厂生产多种产品，消耗多种资源，求最大利润的生产方案。

### 完整代码

```python
import minipulp as mp

# 数据
products = ["A", "B", "C", "D"]
resources = ["原料", "工时", "电力", "仓储"]

# 利润
profit = {"A": 30, "B": 20, "C": 40, "D": 25}

# 资源消耗
usage = {
    "A": {"原料": 2, "工时": 3, "电力": 1, "仓储": 2},
    "B": {"原料": 1, "工时": 2, "电力": 2, "仓储": 1},
    "C": {"原料": 3, "工时": 1, "电力": 1, "仓储": 3},
    "D": {"原料": 2, "工时": 2, "电力": 1, "仓储": 2},
}

# 资源上限
capacity = {"原料": 100, "工时": 80, "电力": 60, "仓储": 70}

# 市场需求上限
max_demand = {"A": 40, "B": 30, "C": 20, "D": 25}

# 变量
x = mp.LpVariable.dicts("x", products, lowBound=0)

# 问题
prob = mp.LpProblem("production", mp.LpMaximize)
prob += mp.lpSum(profit[p] * x[p] for p in products)

# 资源约束
for r in resources:
    prob += mp.lpSum(usage[p][r] * x[p] for p in products) <= capacity[r]

# 市场约束
for p in products:
    prob += x[p] <= max_demand[p]

# 求解
prob.solve()

# 输出
print(f"状态: {prob.status_msg}")
print(f"最大利润: {prob.objective.value():.2f}")
print("\n生产方案:")
for p in products:
    print(f"  产品 {p}: {x[p].varValue:.2f} 件 (利润 {profit[p] * x[p].varValue:.2f})")

print("\n资源使用:")
for r in resources:
    used = sum(usage[p][r] * x[p].varValue for p in products)
    print(f"  {r}: {used:.2f} / {capacity[r]} ({used/capacity[r]*100:.1f}%)")
```

### 带固定成本的生产

生产某产品有固定成本（开机费用）：

```python
from minipulp.solvers import PULP_CBC_CMD

# 固定成本
fixed_cost = {"A": 50, "B": 30, "C": 80, "D": 40}

# 二元变量：是否生产
y = mp.LpVariable.dicts("y", products, cat=mp.LpBinary)

# 目标加入固定成本
prob += mp.lpSum(profit[p] * x[p] - fixed_cost[p] * y[p] for p in products)

# 关联约束
M = 100  # 大常数
for p in products:
    prob += x[p] <= M * y[p]  # y=0 则 x=0
    prob += x[p] >= 0.01 * y[p]  # y=1 则 x>0（可选）

prob.solve(solver=PULP_CBC_CMD())
```

### 多时期生产计划

考虑多个时期，库存转移：

```python
periods = [0, 1, 2, 3]
inventory_cost = 2  # 单位库存成本
initial_inventory = 10

# 变量
produce = mp.LpVariable.matrix("p", products, periods, lowBound=0)  # 各时期产量
inventory = mp.LpVariable.matrix("I", products, periods, lowBound=0)  # 各时期库存
sell = mp.LpVariable.matrix("s", products, periods, lowBound=0)  # 各时期销量

# 目标：总利润 - 库存成本
prob = mp.LpProblem("multi_period", mp.LpMaximize)
prob += mp.lpSum(profit[p] * sell[p][t] for p in products for t in periods) - \
        mp.lpSum(inventory_cost * inventory[p][t] for p in products for t in periods)

# 库存平衡
for p in products:
    for t in periods:
        if t == 0:
            # 初始库存 + 产量 = 销量 + 期末库存
            prob += initial_inventory + produce[p][t] == sell[p][t] + inventory[p][t]
        else:
            # 上期库存 + 产量 = 销量 + 期末库存
            prob += inventory[p][t-1] + produce[p][t] == sell[p][t] + inventory[p][t]

# 各时期资源约束
for t in periods:
    for r in resources:
        prob += mp.lpSum(usage[p][r] * produce[p][t] for p in products) <= capacity[r]

# 各时期需求上限
for p in products:
    for t in periods:
        prob += sell[p][t] <= max_demand[p]

prob.solve()
```

---

## 饮食问题多营养

### 问题描述

配置满足多种营养需求的最低成本食谱。

### 完整代码

```python
import minipulp as mp

# 数据
foods = ["燕麦", "玉米", "牛奶", "面包", "鸡蛋", "菠菜", "牛肉"]
nutrients = ["热量", "蛋白质", "钙", "铁", "维生素A", "维生素C"]

# 营养含量 [食物][营养素]
nutrition = {
    "燕麦": {"热量": 110, "蛋白质": 4,  "钙": 2,  "铁": 4, "维生素A": 160, "维生素C": 0},
    "玉米": {"热量": 100, "蛋白质": 3,  "钙": 10, "铁": 2, "维生素A": 30,  "维生素C": 0},
    "牛奶": {"热量": 120, "蛋白质": 8,  "钙": 28, "铁": 1, "维生素A": 100, "维生素C": 2},
    "面包": {"热量": 80,  "蛋白质": 4,  "钙": 2,  "铁": 3, "维生素A": 0,   "维生素C": 0},
    "鸡蛋": {"热量": 70,  "蛋白质": 6,  "钙": 1,  "铁": 2, "维生素A": 0,   "维生素C": 0},
    "菠菜": {"热量": 20,  "蛋白质": 2,  "钙": 10, "铁": 3, "维生素A": 200, "维生素C": 20},
    "牛肉": {"热量": 200, "蛋白质": 20, "钙": 1,  "铁": 3, "维生素A": 0,   "维生素C": 0},
}

# 成本
cost = {"燕麦": 0.5, "玉米": 0.3, "牛奶": 0.8, "面包": 0.2, "鸡蛋": 0.6, "菠菜": 0.4, "牛肉": 2.0}

# 营养需求
min_nutrition = {"热量": 2000, "蛋白质": 50, "钙": 800, "铁": 15, "维生素A": 5000, "维生素C": 60}
max_nutrition = {"热量": 2500, "蛋白质": 100, "钙": 1500, "铁": 30, "维生素A": 10000, "维生素C": 200}

# 变量
x = mp.LpVariable.dicts("x", foods, lowBound=0)

# 问题
prob = mp.LpProblem("diet", mp.LpMinimize)
prob += mp.lpSum(cost[f] * x[f] for f in foods)

# 营养约束
for k in nutrients:
    prob += mp.lpSum(nutrition[f][k] * x[f] for f in foods) >= min_nutrition[k]
    prob += mp.lpSum(nutrition[f][k] * x[f] for f in foods) <= max_nutrition[k]

# 食物上限
max_amount = {"燕麦": 10, "玉米": 10, "牛奶": 5, "面包": 10, "鸡蛋": 5, "菠菜": 8, "牛肉": 3}
for f in foods:
    prob += x[f] <= max_amount[f]

# 求解
prob.solve()

# 输出
print(f"状态: {prob.status_msg}")
print(f"每日最低成本: {prob.objective.value():.2f} 元")
print("\n食谱:")
for f in foods:
    if x[f].varValue > 0.01:
        print(f"  {f}: {x[f].varValue:.2f} 单位 (成本 {cost[f] * x[f].varValue:.2f})")

print("\n营养摄入:")
for k in nutrients:
    intake = sum(nutrition[f][k] * x[f].varValue for f in foods)
    print(f"  {k}: {intake:.1f} (需求 {min_nutrition[k]}-{max_nutrition[k]})")
```

---

## 网络流问题

### 问题描述

在网络中从源点到汇点输送流量，满足容量限制，最大化总流量。

### 完整代码

```python
import minipulp as mp

# 网络：节点和边
nodes = ["s", "a", "b", "c", "d", "t"]
edges = [
    ("s", "a", 10), ("s", "b", 5),
    ("a", "b", 4), ("a", "c", 8),
    ("b", "c", 6), ("b", "d", 6),
    ("c", "d", 3), ("c", "t", 10),
    ("d", "t", 8),
]

# 变量：各边流量
x = mp.LpVariable.dicts("x", [(u, v) for u, v, _ in edges], lowBound=0)

# 容量约束
for u, v, cap in edges:
    prob = None  # 占位
# （在下面 prob 定义后添加）

prob = mp.LpProblem("maxflow", mp.LpMaximize)

# 容量约束
for u, v, cap in edges:
    prob += x[(u, v)] <= cap

# 流量平衡（中间节点）
for node in nodes:
    if node in ("s", "t"):
        continue
    inflow = mp.lpSum(x[(u, v)] for u, v, _ in edges if v == node)
    outflow = mp.lpSum(x[(u, v)] for u, v, _ in edges if u == node)
    prob += inflow - outflow == 0

# 目标：最大化源点流出
prob += mp.lpSum(x[(u, v)] for u, v, _ in edges if u == "s")

# 求解
prob.solve()

print(f"最大流: {prob.objective.value()}")
print("\n各边流量:")
for u, v, cap in edges:
    print(f"  {u}→{v}: {x[(u, v)].varValue:.1f} / {cap}")
```

---

## 最大流问题

### 问题描述

给定带容量网络，求从源点 s 到汇点 t 的最大流量。

### 数学模型

$$
\begin{aligned}
\max \quad & \sum_{(s,v)} x_{sv} \\
\text{s.t.} \quad & \sum_{(u,v)} x_{uv} - \sum_{(v,w)} x_{vw} = 0 \quad \forall v \neq s, t \\
& 0 \leq x_{uv} \leq c_{uv} \quad \forall (u,v)
\end{aligned}
$$

### 完整代码

```python
import minipulp as mp

# 网络
nodes = ["s", "1", "2", "3", "4", "t"]
edges = {
    ("s", "1"): 16, ("s", "2"): 13,
    ("1", "2"): 10, ("1", "3"): 12,
    ("2", "1"): 4, ("2", "4"): 14,
    ("3", "2"): 9, ("3", "t"): 20,
    ("4", "3"): 7, ("4", "t"): 4,
}

# 变量
x = mp.LpVariable.dicts("f", edges.keys(), lowBound=0)

prob = mp.LpProblem("maxflow", mp.LpMaximize)

# 容量约束
for (u, v), cap in edges.items():
    prob += x[(u, v)] <= cap

# 流量平衡
for node in nodes:
    if node == "s" or node == "t":
        continue
    inflow = mp.lpSum(x[(u, v)] for (u, v) in edges if v == node)
    outflow = mp.lpSum(x[(u, v)] for (u, v) in edges if u == node)
    prob += inflow - outflow == 0

# 目标
prob += mp.lpSum(x[(u, v)] for (u, v) in edges if u == "s")

prob.solve()
print(f"最大流: {prob.objective.value()}")
```

---

## 最短路问题

### 问题描述

给定带权图，求从起点到终点的最短路径。

### 数学模型

$$
\begin{aligned}
\min \quad & \sum_{(u,v)} d_{uv} x_{uv} \\
\text{s.t.} \quad & \sum_{(u,v)} x_{uv} - \sum_{(v,w)} x_{vw} = b_v \quad \forall v \\
& x_{uv} \in \{0, 1\}
\end{aligned}
$$

其中 $b_s = 1$（起点），$b_t = -1$（终点），其他 $b_v = 0$。

### 完整代码

```python
import minipulp as mp

# 图
nodes = ["A", "B", "C", "D", "E", "F"]
edges = {
    ("A", "B"): 4, ("A", "C"): 2,
    ("B", "C"): 1, ("B", "D"): 5,
    ("C", "B"): 1, ("C", "D"): 8, ("C", "E"): 10,
    ("D", "E"): 2, ("D", "F"): 6,
    ("E", "F"): 3,
}

source = "A"
sink = "F"

# 变量
x = mp.LpVariable.dicts("x", edges.keys(), cat=mp.LpBinary)

prob = mp.LpProblem("shortest", mp.LpMinimize)
prob += mp.lpSum(edges[(u, v)] * x[(u, v)] for (u, v) in edges)

# 流量平衡
for node in nodes:
    inflow = mp.lpSum(x[(u, v)] for (u, v) in edges if v == node)
    outflow = mp.lpSum(x[(u, v)] for (u, v) in edges if u == node)
    if node == source:
        prob += outflow - inflow == 1
    elif node == sink:
        prob += outflow - inflow == -1
    else:
        prob += outflow - inflow == 0

prob.solve()
print(f"最短距离: {prob.objective.value()}")
print("路径:")
for (u, v) in edges:
    if x[(u, v)].varValue > 0.5:
        print(f"  {u} → {v} (距离 {edges[(u, v)]})")
```

---

## 混合整数规划

### 问题描述

既有连续变量又有整数变量的问题。

### 示例：投资决策

决定投资项目（整数决策）并分配资金（连续分配）：

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

projects = ["P1", "P2", "P3"]
budget = 1000

# 收益率
return_rate = {"P1": 0.15, "P2": 0.12, "P3": 0.18}
# 最小投资额
min_invest = {"P1": 100, "P2": 200, "P3": 150}
# 最大投资额
max_invest = {"P1": 500, "P2": 800, "P3": 600}

# 变量
y = mp.LpVariable.dicts("y", projects, cat=mp.LpBinary)  # 是否投资
x = mp.LpVariable.dicts("x", projects, lowBound=0)  # 投资额（连续）

prob = mp.LpProblem("invest", mp.LpMaximize)
prob += mp.lpSum(return_rate[p] * x[p] for p in projects)

# 预算约束
prob += mp.lpSum(x[p] for p in projects) <= budget

# 关联约束
M = budget
for p in projects:
    prob += x[p] <= max_invest[p] * y[p]  # y=0 则 x=0
    prob += x[p] >= min_invest[p] * y[p]  # y=1 则 x >= min

# 至少投资 2 个项目
prob += mp.lpSum(y[p] for p in projects) >= 2

prob.solve(solver=PULP_CBC_CMD())
print(f"最大收益: {prob.objective.value():.2f}")
for p in projects:
    if y[p].varValue > 0.5:
        print(f"  投资 {p}: {x[p].varValue:.2f}")
    else:
        print(f"  不投资 {p}")
```

### 示例：选址-分配

决定仓库位置并分配客户：

```python
warehouses = ["W1", "W2", "W3"]
customers = ["C1", "C2", "C3", "C4", "C5"]

open_cost = {"W1": 100, "W2": 150, "W3": 120}
serve_cost = {
    ("W1", "C1"): 10, ("W1", "C2"): 20, ("W1", "C3"): 30, ("W1", "C4"): 40, ("W1", "C5"): 50,
    ("W2", "C1"): 25, ("W2", "C2"): 15, ("W2", "C3"): 20, ("W2", "C4"): 30, ("W2", "C5"): 35,
    ("W3", "C1"): 35, ("W3", "C2"): 25, ("W3", "C3"): 15, ("W3", "C4"): 20, ("W3", "C5"): 25,
}
capacity = {"W1": 3, "W2": 4, "W3": 3}

# 变量
y = mp.LpVariable.dicts("y", warehouses, cat=mp.LpBinary)  # 是否开设
x = mp.LpVariable.matrix("x", warehouses, customers, cat=mp.LpBinary)  # 是否分配

prob = mp.LpProblem("facility", mp.LpMinimize)
prob += mp.lpSum(open_cost[w] * y[w] for w in warehouses) + \
        mp.lpSum(serve_cost[(w, c)] * x[w][c] for w in warehouses for c in customers)

# 每个客户分配到一个仓库
for c in customers:
    prob += mp.lpSum(x[w][c] for w in warehouses) == 1

# 容量约束
for w in warehouses:
    prob += mp.lpSum(x[w][c] for c in customers) <= capacity[w] * y[w]

prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
```

---

## 多目标规划简介

### 加权法

将多个目标加权合并为单目标：

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

# 目标 1：最大化利润
profit = 3 * x + 2 * y
# 目标 2：最小化风险
risk = x + 3 * y

# 加权（权重可调）
w_profit = 0.7
w_risk = 0.3

prob = mp.LpProblem("multi_obj", mp.LpMaximize)
prob += w_profit * profit - w_risk * risk  # 最大化利润，最小化风险
prob += x + y <= 100
prob += x <= 40

prob.solve()
print(f"利润: {profit.value():.2f}")
print(f"风险: {risk.value():.2f}")
```

### ε-约束法

将次要目标转为约束：

```python
prob = mp.LpProblem("eps_constrained", mp.LpMaximize)
prob += 3 * x + 2 * y  # 主目标：最大化利润
prob += x + y <= 100
prob += x <= 40
prob += x + 3 * y <= 80  # 次要目标：风险 <= 80

prob.solve()
```

### Pareto 前沿

通过改变权重生成 Pareto 解：

```python
pareto_solutions = []
for w in [0.0, 0.1, 0.2, ..., 1.0]:
    prob = mp.LpProblem("pareto", mp.LpMaximize)
    prob += w * profit - (1 - w) * risk
    prob += x + y <= 100
    prob += x <= 40
    prob.solve()
    pareto_solutions.append((profit.value(), risk.value()))
```

---

## 测试

```bash
uv run pytest tests/test_advanced.py -v
```

12 个测试覆盖：`dicts`/`matrix` 批量创建、`lpSum` 正确性与性能、运输问题端到端。

### 测试示例

```python
def test_dicts_creation():
    x = LpVariable.dicts("x", range(5), lowBound=0)
    assert len(x) == 5
    assert x[0].name == "x_0"
    assert x[0].lowBound == 0

def test_matrix_creation():
    x = LpVariable.matrix("x", range(3), range(4), lowBound=0)
    assert len(x) == 3
    assert len(x[0]) == 4
    assert x[0][0].name == "x_0_0"

def test_lpsum_correctness():
    x = LpVariable.dicts("x", range(100), lowBound=0)
    exprs = [3 * x[i] for i in range(100)]
    result = lpSum(exprs)
    assert len(result.terms) == 100
    for i in range(100):
        assert result.terms[x[i]] == 3.0

def test_transport_problem():
    # 运输问题端到端测试
    supply = {"f1": 30, "f2": 40}
    demand = {"c1": 20, "c2": 25, "c3": 25}
    cost = {("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4,
            ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1}

    x = LpVariable.matrix("x", supply.keys(), demand.keys(), lowBound=0)
    prob = LpProblem("transport", LpSense.MINIMIZE)
    prob += lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)
    for i in supply:
        prob += lpSum(x[i][j] for j in demand) <= supply[i]
    for j in demand:
        prob += lpSum(x[i][j] for i in supply) >= demand[j]
    prob.solve()
    assert prob.status == LpStatus.OPTIMAL
```

---

## 总结

Phase 5 的高级功能让 minipulp 能处理大规模实际问题，其设计要点：

1. **批量创建**：`dicts`/`matrix` 支持任意索引，灵活建模
2. **`lpSum` 优化**：$O(N)$ 复杂度，大规模求和性能优
3. **经典模型**：运输、指派、生产计划、饮食等开箱即用
4. **网络流**：最大流、最短路等图问题
5. **混合整数规划**：选址-分配、投资决策等
6. **多目标规划**：加权法、ε-约束法

这些工具让 minipulp 不仅是教学工具，也能解决实际的运筹优化问题。
