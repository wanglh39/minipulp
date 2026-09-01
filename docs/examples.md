# 示例

经典线性规划问题示例，展示 minipulp 建模能力。

每个示例包含：**问题描述（数学公式）→ 建模代码 → 求解结果 → 求解器选择说明**。

---

## 目录

### 基础问题

- [生产计划（连续 LP）](#生产计划连续-lp)
- [饮食问题（最小化）](#饮食问题最小化)
- [资源分配问题](#资源分配问题)

### 网络与流问题

- [运输问题](#运输问题)
- [指派问题（整数规划）](#指派问题整数规划)
- [最大流问题](#最大流问题)
- [最短路问题](#最短路问题)
- [最小费用流问题](#最小费用流问题)

### 组合优化问题

- [背包问题（二元变量）](#背包问题二元变量)
- [多维背包问题](#多维背包问题)
- [混合整数规划](#混合整数规划)
- [设施选址问题](#设施选址问题)
- [集合覆盖问题](#集合覆盖问题)
- [排班问题](#排班问题)

### 工业应用

- [切割下料问题](#切割下料问题)
- [生产库存问题](#生产库存问题)
- [多目标生产计划](#多目标生产计划)
- [投资组合问题](#投资组合问题)

### 求解器与技巧

- [求解器选择](#求解器选择)
- [批量建模](#批量建模)
- [调试技巧](#调试技巧)

---

## 生产计划（连续 LP）

!!! info "问题背景"

    工厂生产两种产品 A、B，利润分别为 3、2。受工时与原料约束，求最大利润的生产方案。

$$
\begin{aligned}
\max \quad & 3x + 2y \\
\text{s.t.} \quad & 2x + y \leq 100 \quad \text{(工时)} \\
& x + y \leq 80 \quad \text{(原料)} \\
& x \leq 40 \quad \text{(产能)} \\
& x, y \geq 0
\end{aligned}
$$

最优解：$x = 20, y = 60, \text{obj} = 180$

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("production", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

prob.solve()
print(f"status: {prob.status_msg}")  # Optimal
print(f"x = {x.varValue}")           # 20.0
print(f"y = {y.varValue}")           # 60.0
print(f"obj = {prob.objective.value()}")  # 180.0
```

!!! tip "求解器选择"

    连续 LP 用默认求解器即可。如需更快，用 `SimplexCpp()`：

    ```python
    from minipulp.solvers import SimplexCpp
    prob.solve(solver=SimplexCpp())
    ```

### 添加变量上下界

变量上下界可以直接在构造时指定，等价于约束但更高效：

```python
x = mp.LpVariable("x", lowBound=0, upBound=40)  # 0 <= x <= 40
y = mp.LpVariable("y", lowBound=0, upBound=80)  # 0 <= y <= 80

prob = mp.LpProblem("production_bounded", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
# x <= 40 已由 upBound 表达，无需再写

prob.solve()
```

### 查看生成的 LP 文件

```python
print(mp.write_lp(prob))
```

输出：

```text
\* production *\
Maximize
  3 x + 2 y
Subject To
  c0: 2 x + 1 y <= 100
  c1: 1 x + 1 y <= 80
Bounds
  0 <= x <= 40
  0 <= y <= 80
End
```

---

## 饮食问题（最小化）

!!! info "问题背景"

    选择食物组合，最小化成本同时满足营养需求。这是 LP 最古老的应用之一，由 George Stigler 在 1945 年首次研究。

$$
\begin{aligned}
\min \quad & 2x + 3y \\
\text{s.t.} \quad & 3x + y \geq 6 \quad \text{(营养 A)} \\
& x + 2y \geq 4 \quad \text{(营养 B)} \\
& x, y \geq 0
\end{aligned}
$$

最优解：$x = 1.6, y = 1.2, \text{obj} = 6.8$

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)  # 食物 A
y = mp.LpVariable("y", lowBound=0)  # 食物 B

prob = mp.LpProblem("diet", mp.LpMinimize)
prob += 2 * x + 3 * y
prob += 3 * x + y >= 6   # 营养 A 需求
prob += x + 2 * y >= 4   # 营养 B 需求

prob.solve()
print(f"x = {x.varValue}")  # 1.6
print(f"y = {y.varValue}")  # 1.2
```

### 扩展：多食物多营养

更现实的饮食问题有多个食物和多个营养约束：

```python
import minipulp as mp

foods = ["米", "面", "肉", "菜", "蛋"]
cost = {"米": 3, "面": 2, "肉": 12, "菜": 4, "蛋": 1}

nutrients = ["蛋白质", "碳水", "维生素", "脂肪"]
requirement = {"蛋白质": 50, "碳水": 200, "维生素": 30, "脂肪": 40}

# 营养含量表：nutrient_content[营养][食物] = 每单位食物中该营养含量
nutrient_content = {
    "蛋白质": {"米": 7, "面": 10, "肉": 25, "菜": 2, "蛋": 12},
    "碳水":   {"米": 75, "面": 70, "肉": 0, "菜": 5, "蛋": 1},
    "维生素": {"米": 1, "面": 2, "肉": 3, "菜": 20, "蛋": 5},
    "脂肪":   {"米": 1, "面": 1, "肉": 20, "菜": 1, "蛋": 10},
}

x = mp.LpVariable.dicts("x", foods, lowBound=0)

prob = mp.LpProblem("diet_full", mp.LpMinimize)
prob += mp.lpSum(cost[f] * x[f] for f in foods)

for n in nutrients:
    prob += mp.lpSum(nutrient_content[n][f] * x[f] for f in foods) >= requirement[n]

prob.solve()
print(f"最小成本: {prob.objective.value()}")
for f in foods:
    print(f"  {f}: {x[f].varValue:.2f}")
```

---

## 资源分配问题

!!! info "问题背景"

    公司有 3 种资源（人力、机器、原料），分配给 4 个项目，最大化总收益。

```python
import minipulp as mp

resources = ["人力", "机器", "原料"]
projects = ["P1", "P2", "P3", "P4"]

# 资源总量
available = {"人力": 100, "机器": 80, "原料": 60}

# 每个项目所需资源量：consume[资源][项目]
consume = {
    "人力": {"P1": 3, "P2": 2, "P3": 4, "P4": 5},
    "机器": {"P1": 2, "P2": 3, "P3": 1, "P4": 4},
    "原料": {"P1": 1, "P2": 2, "P3": 3, "P4": 2},
}

# 每个项目的单位收益
profit = {"P1": 10, "P2": 15, "P3": 12, "P4": 8}

x = mp.LpVariable.dicts("x", projects, lowBound=0)

prob = mp.LpProblem("resource", mp.LpMaximize)
prob += mp.lpSum(profit[p] * x[p] for p in projects)

for r in resources:
    prob += mp.lpSum(consume[r][p] * x[p] for p in projects) <= available[r]

prob.solve()
print(f"最大收益: {prob.objective.value()}")
for p in projects:
    print(f"  {p}: {x[p].varValue:.2f}")
```

---

## 运输问题

!!! info "问题背景"

    3 个工厂向 4 个客户运输，最小化总运输成本。这是 LP 最经典的应用之一，由 Hitchcock 在 1941 年提出。

$$
\begin{aligned}
\min \quad & \sum_{i,j} c_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_j x_{ij} \leq s_i \quad \forall i \quad \text{(供应)} \\
& \sum_i x_{ij} \geq d_j \quad \forall j \quad \text{(需求)} \\
& x_{ij} \geq 0
\end{aligned}
$$

```python
import minipulp as mp

supply = {"f1": 30, "f2": 40, "f3": 30}
demand = {"c1": 20, "c2": 25, "c3": 25, "c4": 30}
cost = {
    ("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4, ("f1", "c4"): 5,
    ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1, ("f2", "c4"): 4,
    ("f3", "c1"): 4, ("f3", "c2"): 3, ("f3", "c3"): 2, ("f3", "c4"): 1,
}

x = mp.LpVariable.matrix("x", supply.keys(), demand.keys(), lowBound=0)

prob = mp.LpProblem("transport", mp.LpMinimize)
prob += mp.lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)

for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) <= supply[i]

for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) >= demand[j]

prob.solve()
print(f"总成本: {prob.objective.value()}")
for i in supply:
    for j in demand:
        if x[i][j].varValue > 0.01:
            print(f"  {i} -> {j}: {x[i][j].varValue:.1f}")
```

### 平衡运输问题

当总供应等于总需求时，称为平衡运输问题。此时供应约束应为等式：

```python
total_supply = sum(supply.values())
total_demand = sum(demand.values())
assert total_supply == total_demand, "供需不平衡"

# ...
for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) == supply[i]  # 等式

for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) == demand[j]  # 等式
```

### 不平衡运输问题

当总供应 > 总需求时，可引入虚拟需求点吸收多余供应：

```python
if total_supply > total_demand:
    # 添加虚拟需求点，运输成本为 0
    surplus = total_supply - total_demand
    demand["virtual"] = surplus
    for i in supply:
        cost[(i, "virtual")] = 0
```

---

## 指派问题（整数规划）

!!! info "问题背景"

    将 4 个任务分配给 4 个工人，每个工人做一个任务，最小化总成本。这是 0-1 整数规划的典型应用。

$$
\begin{aligned}
\min \quad & \sum_{i,j} c_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_j x_{ij} = 1 \quad \forall i \quad \text{(每工人一任务)} \\
& \sum_i x_{ij} = 1 \quad \forall j \quad \text{(每任务一工人)} \\
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
    prob += mp.lpSum(x[i][j] for j in range(n)) == 1

for j in range(n):
    prob += mp.lpSum(x[i][j] for i in range(n)) == 1

prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
for i in range(n):
    for j in range(n):
        if x[i][j].varValue > 0.5:
            print(f"  工人 {i} -> 任务 {j}")
```

!!! warning "求解器要求"

    指派问题需要整数规划支持，必须用 `PULP_CBC_CMD`。`SimplexCore` / `SimplexCpp` 不支持整数变量。

### 松弛：连续指派

如果去掉整数约束（`cat=mp.LpContinuous`），指派问题的 LP 松弛仍有整数最优解（因为约束矩阵是全单模的）。这是组合优化中一个优美的性质：

```python
# 连续松弛——结果仍是 0/1 解
x = mp.LpVariable.matrix("x", range(n), range(n), lowBound=0, upBound=1)
# ... 其余不变
prob.solve()  # 用 SimplexCore 也能解
```

---

## 背包问题（二元变量）

!!! info "问题背景"

    0-1 背包问题：选物品放入背包，最大化价值，不超过容量。这是 NP-hard 问题中最简单的一个。

$$
\begin{aligned}
\max \quad & \sum_i v_i x_i \\
\text{s.t.} \quad & \sum_i w_i x_i \leq C \\
& x_i \in \{0, 1\}
\end{aligned}
$$

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

items = ["A", "B", "C", "D", "E"]
weight = {"A": 2, "B": 3, "C": 4, "D": 5, "E": 6}
value = {"A": 3, "B": 4, "C": 5, "D": 6, "E": 7}
capacity = 10

x = mp.LpVariable.dicts("x", items, cat=mp.LpBinary)

prob = mp.LpProblem("knapsack", mp.LpMaximize)
prob += mp.lpSum(value[i] * x[i] for i in items)
prob += mp.lpSum(weight[i] * x[i] for i in items) <= capacity

prob.solve(solver=PULP_CBC_CMD())
print(f"最大价值: {prob.objective.value()}")
for i in items:
    if x[i].varValue > 0.5:
        print(f"  选择 {i}")
```

---

## 多维背包问题

!!! info "问题背景"

    背包有多个维度的容量限制（重量、体积、预算），物品在每个维度都有消耗。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

items = ["A", "B", "C", "D", "E", "F"]
value = {"A": 10, "B": 15, "C": 20, "D": 25, "E": 30, "F": 35}

# 多维消耗：consume[维度][物品]
consume = {
    "重量": {"A": 2, "B": 3, "C": 4, "D": 5, "E": 6, "F": 7},
    "体积": {"A": 3, "B": 2, "C": 5, "D": 4, "E": 3, "F": 6},
    "预算": {"A": 5, "B": 4, "C": 3, "D": 6, "E": 5, "F": 4},
}
capacity = {"重量": 15, "体积": 12, "预算": 20}

x = mp.LpVariable.dicts("x", items, cat=mp.LpBinary)

prob = mp.LpProblem("multi_knapsack", mp.LpMaximize)
prob += mp.lpSum(value[i] * x[i] for i in items)

for dim in consume:
    prob += mp.lpSum(consume[dim][i] * x[i] for i in items) <= capacity[dim]

prob.solve(solver=PULP_CBC_CMD())
print(f"最大价值: {prob.objective.value()}")
for i in items:
    if x[i].varValue > 0.5:
        print(f"  选择 {i}")
```

---

## 混合整数规划

!!! info "问题背景"

    部分变量连续，部分变量整数。这是 MILP 的典型形式，常见于投资决策（建/不建）+ 连续运营量。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

x = mp.LpVariable("x", lowBound=0)                          # 连续
z = mp.LpVariable("z", lowBound=0, cat=mp.LpInteger)        # 整数

prob = mp.LpProblem("mip", mp.LpMaximize)
prob += 2 * x + 3 * z
prob += x + z <= 10
prob += 2 * x + z <= 15

prob.solve(solver=PULP_CBC_CMD())
print(f"x = {x.varValue} (连续)")
print(f"z = {z.varValue} (整数)")
print(f"obj = {prob.objective.value()}")
```

### 固定成本问题

MILP 常用于建模固定成本：是否开启某设施（二元变量）+ 开启后的连续运营量。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 是否建厂（二元）+ 建厂后的产量（连续）
y = mp.LpVariable("y", cat=mp.LpBinary)   # 建厂决策
x = mp.LpVariable("x", lowBound=0)        # 产量

fixed_cost = 100   # 建厂固定成本
unit_profit = 5    # 单位利润
max_capacity = 50  # 最大产能

prob = mp.LpProblem("fixed_cost", mp.LpMaximize)
prob += unit_profit * x - fixed_cost * y

# 大 M 约束：不建厂则产量为 0
M = max_capacity
prob += x <= M * y

prob.solve(solver=PULP_CBC_CMD())
print(f"建厂: {y.varValue > 0.5}")
print(f"产量: {x.varValue}")
print(f"利润: {prob.objective.value()}")
```

---

## 最大流问题

!!! info "问题背景"

    给定有向图与每条边的容量，求从源点 s 到汇点 t 的最大流量。

$$
\begin{aligned}
\max \quad & \sum_{(s, v)} f_{sv} \\
\text{s.t.} \quad & \sum_{u} f_{uv} - \sum_{w} f_{vw} = 0 \quad \forall v \neq s, t \quad \text{(流量守恒)} \\
& 0 \leq f_{uv} \leq c_{uv} \quad \text{(容量约束)}
\end{aligned}
$$

```python
import minipulp as mp

# 图：edges[(u, v)] = 容量
edges = {
    ("s", "a"): 10, ("s", "b"): 5,
    ("a", "b"): 4, ("a", "c"): 8, ("a", "d"): 2,
    ("b", "d"): 7,
    ("c", "t"): 5,
    ("d", "c"): 3, ("d", "t"): 10,
}
nodes = {"s", "a", "b", "c", "d", "t"}
source = "s"
sink = "t"

# 流量变量：0 <= f_uv <= capacity
f = {e: mp.LpVariable(f"f_{e[0]}_{e[1]}", lowBound=0, upBound=cap)
     for e, cap in edges.items()}

prob = mp.LpProblem("maxflow", mp.LpMaximize)
prob += mp.lpSum(f[(source, v)] for v in nodes if (source, v) in edges)

# 流量守恒（中间节点）
for v in nodes - {source, sink}:
    inflow = mp.lpSum(f[(u, v)] for u in nodes if (u, v) in edges)
    outflow = mp.lpSum(f[(v, w)] for w in nodes if (v, w) in edges)
    prob += inflow - outflow == 0

prob.solve()
print(f"最大流: {prob.objective.value()}")
for e, var in f.items():
    if var.varValue > 0.01:
        print(f"  {e[0]} -> {e[1]}: {var.varValue:.1f}")
```

---

## 最短路问题

!!! info "问题背景"

    给定有向图与每条边的长度，求从源点 s 到汇点 t 的最短路。

    建模技巧：用 0-1 流表示路径选择，每条边流量 ≤ 1，源点出流 = 1，汇点入流 = 1，中间节点流量守恒。

```python
import minipulp as mp

edges = {
    ("s", "a"): 2, ("s", "b"): 5,
    ("a", "b"): 1, ("a", "c"): 4, ("a", "d"): 7,
    ("b", "d"): 3,
    ("c", "t"): 2,
    ("d", "c"): 1, ("d", "t"): 4,
}
nodes = {"s", "a", "b", "c", "d", "t"}
source = "s"
sink = "t"

# x_uv = 1 表示选择边 (u, v)
x = {e: mp.LpVariable(f"x_{e[0]}_{e[1]}", cat=mp.LpBinary)
     for e in edges}

prob = mp.LpProblem("shortest_path", mp.LpMinimize)
prob += mp.lpSum(edges[e] * x[e] for e in edges)

# 源点出流 - 入流 = 1
prob += (mp.lpSum(x[(source, v)] for v in nodes if (source, v) in edges)
         - mp.lpSum(x[(u, source)] for u in nodes if (u, source) in edges) == 1)

# 汇点入流 - 出流 = 1
prob += (mp.lpSum(x[(u, sink)] for u in nodes if (u, sink) in edges)
         - mp.lpSum(x[(sink, v)] for v in nodes if (sink, v) in edges) == 1)

# 中间节点流量守恒
for v in nodes - {source, sink}:
    inflow = mp.lpSum(x[(u, v)] for u in nodes if (u, v) in edges)
    outflow = mp.lpSum(x[(v, w)] for w in nodes if (v, w) in edges)
    prob += inflow - outflow == 0

from minipulp.solvers import PULP_CBC_CMD
prob.solve(solver=PULP_CBC_CMD())
print(f"最短路径长度: {prob.objective.value()}")
print("路径:")
for e, var in x.items():
    if var.varValue > 0.5:
        print(f"  {e[0]} -> {e[1]} (长度 {edges[e]})")
```

!!! tip "为什么最短路用 0-1 流？"

    把路径看作从 s 到 t 的单位流：每条边要么在路径上（流量 1），要么不在（流量 0）。流量守恒保证路径连续。最小化总长度即最小化总流量成本。

---

## 最小费用流问题

!!! info "问题背景"

    每条边既有容量又有单位费用，给定各节点供需量，求满足供需的最小费用流。

```python
import minipulp as mp

edges = {
    ("s", "a"): {"cap": 10, "cost": 1},
    ("s", "b"): {"cap": 10, "cost": 2},
    ("a", "b"): {"cap": 5,  "cost": 1},
    ("a", "t"): {"cap": 8,  "cost": 3},
    ("b", "t"): {"cap": 8,  "cost": 1},
}
nodes = {"s", "a", "b", "t"}

# 供需：正表示供应，负表示需求
supply = {"s": 10, "a": 0, "b": 0, "t": -10}

f = {e: mp.LpVariable(f"f_{e[0]}_{e[1]}", lowBound=0, upBound=edges[e]["cap"])
     for e in edges}

prob = mp.LpProblem("min_cost_flow", mp.LpMinimize)
prob += mp.lpSum(edges[e]["cost"] * f[e] for e in edges)

for v in nodes:
    inflow = mp.lpSum(f[(u, v)] for u in nodes if (u, v) in edges)
    outflow = mp.lpSum(f[(v, w)] for w in nodes if (v, w) in edges)
    prob += outflow - inflow == supply[v]

prob.solve()
print(f"最小费用: {prob.objective.value()}")
for e, var in f.items():
    if var.varValue > 0.01:
        print(f"  {e[0]} -> {e[1]}: {var.varValue:.1f}")
```

---

## 设施选址问题

!!! info "问题背景"

    在候选地点中选若干建设施，服务一组客户。建设施有固定成本，分配客户有运输成本。求最小化总成本。

$$
\begin{aligned}
\min \quad & \sum_j f_j y_j + \sum_{i,j} c_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_j x_{ij} = 1 \quad \forall i \quad \text{(每客户被服务)} \\
& x_{ij} \leq y_j \quad \forall i, j \quad \text{(只能用已建设施)} \\
& y_j \in \{0, 1\}, x_{ij} \geq 0
\end{aligned}
$$

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

customers = ["c1", "c2", "c3", "c4", "c5"]
facilities = ["f1", "f2", "f3"]

# 建设施固定成本
fixed_cost = {"f1": 100, "f2": 150, "f3": 120}

# 客户 i 由设施 j 服务的运输成本
transport_cost = {
    ("c1", "f1"): 4, ("c1", "f2"): 6, ("c1", "f3"): 9,
    ("c2", "f1"): 5, ("c2", "f2"): 4, ("c2", "f3"): 7,
    ("c3", "f1"): 8, ("c3", "f2"): 3, ("c3", "f3"): 5,
    ("c4", "f1"): 7, ("c4", "f2"): 5, ("c4", "f3"): 4,
    ("c5", "f1"): 6, ("c5", "f2"): 8, ("c5", "f3"): 3,
}

# y_j = 1 表示在 j 建设施
y = mp.LpVariable.dicts("y", facilities, cat=mp.LpBinary)
# x_ij = 1 表示客户 i 由设施 j 服务
x = mp.LpVariable.matrix("x", customers, facilities, cat=mp.LpBinary)

prob = mp.LpProblem("facility", mp.LpMinimize)
prob += mp.lpSum(fixed_cost[j] * y[j] for j in facilities) \
     + mp.lpSum(transport_cost[(i, j)] * x[i][j] for i in customers for j in facilities)

# 每客户恰好由一个设施服务
for i in customers:
    prob += mp.lpSum(x[i][j] for j in facilities) == 1

# 只能用已建设施
for i in customers:
    for j in facilities:
        prob += x[i][j] <= y[j]

prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
print("建设设施:")
for j in facilities:
    if y[j].varValue > 0.5:
        print(f"  {j}")
print("分配:")
for i in customers:
    for j in facilities:
        if x[i][j].varValue > 0.5:
            print(f"  {i} -> {j}")
```

---

## 集合覆盖问题

!!! info "问题背景"

    给定一组元素和若干子集（每个子集有成本），选最小成本子集族覆盖所有元素。这是 NP-hard 的经典问题。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 元素
elements = ["e1", "e2", "e3", "e4", "e5", "e6"]

# 子集：subset -> cost
subsets = {
    "S1": {"cost": 3, "covers": {"e1", "e2", "e3"}},
    "S2": {"cost": 2, "covers": {"e2", "e4"}},
    "S3": {"cost": 4, "covers": {"e3", "e5", "e6"}},
    "S4": {"cost": 1, "covers": {"e4", "e6"}},
    "S5": {"cost": 5, "covers": {"e1", "e5"}},
}

# x_S = 1 表示选择子集 S
x = mp.LpVariable.dicts("x", subsets.keys(), cat=mp.LpBinary)

prob = mp.LpProblem("set_cover", mp.LpMinimize)
prob += mp.lpSum(subsets[S]["cost"] * x[S] for S in subsets)

# 每个元素至少被一个子集覆盖
for e in elements:
    covering = [x[S] for S in subsets if e in subsets[S]["covers"]]
    prob += mp.lpSum(covering) >= 1

prob.solve(solver=PULP_CBC_CMD())
print(f"最小成本: {prob.objective.value()}")
print("选择子集:")
for S in subsets:
    if x[S].varValue > 0.5:
        print(f"  {S} (成本 {subsets[S]['cost']})")
```

---

## 排班问题

!!! info "问题背景"

    7 天营业，每天需要一定数量员工，每个员工连续工作 5 天休息 2 天。求最少员工数。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
demand = {"周一": 3, "周二": 4, "周三": 5, "周四": 5, "周五": 4, "周六": 3, "周日": 2}

# x_i = 从第 i 天开始工作的员工数
# 周一开工的员工工作 周一二三四五
# 周二开工的员工工作 周二三四五六
# ...
start_days = days  # 7 种开工模式

x = mp.LpVariable.dicts("x", start_days, lowBound=0, cat=mp.LpInteger)

# 每天在岗员工 = 从当天往前数 5 天内开工的员工
def working_on(day):
    idx = days.index(day)
    # 当天在岗的员工是过去 5 天内（含当天）开工的
    active = []
    for offset in range(5):
        start_day = days[(idx - offset) % 7]
        active.append(x[start_day])
    return mp.lpSum(active)

prob = mp.LpProblem("scheduling", mp.LpMinimize)
prob += mp.lpSum(x[d] for d in start_days)

for d in days:
    prob += working_on(d) >= demand[d]

prob.solve(solver=PULP_CBC_CMD())
print(f"最少员工: {prob.objective.value()}")
for d in start_days:
    if x[d].varValue > 0:
        print(f"  {d} 开工: {x[d].varValue:.0f} 人")
```

### 弹性排班

允许加班（超出需求的在岗员工），但有加班成本：

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
demand = {"周一": 3, "周二": 4, "周三": 5, "周四": 5, "周五": 4, "周六": 3, "周日": 2}

x = mp.LpVariable.dicts("x", days, lowBound=0, cat=mp.LpInteger)
# 加班变量
o = mp.LpVariable.dicts("o", days, lowBound=0)  # 多余在岗员工

prob = mp.LpProblem("flex_scheduling", mp.LpMinimize)
prob += mp.lpSum(x[d] for d in days) + mp.lpSum(0.5 * o[d] for d in days)

for idx, d in enumerate(days):
    active = [x[days[(idx - off) % 7]] for off in range(5)]
    prob += mp.lpSum(active) - o[d] == demand[d]

prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
```

---

## 切割下料问题

!!! info "问题背景"

    原料长度 100，需要切出若干指定长度的件，最小化原料使用量。这是列生成法的经典应用，这里用枚举切割模式的方法建模。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 原料长度
L = 100

# 需求：length -> 数量
orders = {30: 5, 50: 3, 70: 2}

# 枚举所有可行切割模式
# 模式 = (30 的数量, 50 的数量, 70 的数量)，满足 30a + 50b + 70c <= 100
patterns = []
for a in range(L // 30 + 1):
    for b in range(L // 50 + 1):
        for c in range(L // 70 + 1):
            if 30 * a + 50 * b + 70 * c <= L and (a + b + c) > 0:
                patterns.append((a, b, c))

print(f"可行切割模式数: {len(patterns)}")

# 每种模式使用次数
x = mp.LpVariable.dicts("x", range(len(patterns)), lowBound=0, cat=mp.LpInteger)

prob = mp.LpProblem("cutting_stock", mp.LpMinimize)
prob += mp.lpSum(x[i] for i in range(len(patterns)))

# 满足每种订单需求
lengths = list(orders.keys())
for j, length in enumerate(lengths):
    prob += mp.lpSum(patterns[i][j] * x[i] for i in range(len(patterns))) >= orders[length]

prob.solve(solver=PULP_CBC_CMD())
print(f"最少原料数: {prob.objective.value()}")
for i in range(len(patterns)):
    if x[i].varValue > 0:
        print(f"  模式 {patterns[i]} 使用 {x[i].varValue:.0f} 次")
```

---

## 生产库存问题

!!! info "问题背景"

    多时段生产计划：每时段有需求，可生产可存储，最小化生产 + 存储成本。

```python
import minipulp as mp

T = 6  # 时段数
demand = [50, 60, 70, 80, 90, 100]  # 各时段需求
prod_cost = 10   # 单位生产成本
hold_cost = 2    # 单位库存成本
capacity = 120   # 单时段最大产能

# 生产量
p = mp.LpVariable.dicts("p", range(T), lowBound=0, upBound=capacity)
# 库存量
s = mp.LpVariable.dicts("s", range(T), lowBound=0)

prob = mp.LpProblem("inventory", mp.LpMinimize)
prob += mp.lpSum(prod_cost * p[t] + hold_cost * s[t] for t in range(T))

# 库存平衡：s[t] = s[t-1] + p[t] - demand[t]
for t in range(T):
    if t == 0:
        prob += s[t] == p[t] - demand[t]
    else:
        prob += s[t] == s[t - 1] + p[t] - demand[t]

prob.solve()
print(f"总成本: {prob.objective.value()}")
for t in range(T):
    print(f"  时段 {t}: 生产 {p[t].varValue:.1f}, 库存 {s[t].varValue:.1f}")
```

### 带启动成本的生产库存

每次开工有固定启动成本，需用二元变量建模：

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

T = 6
demand = [50, 60, 70, 80, 90, 100]
prod_cost = 10
hold_cost = 2
capacity = 120
startup_cost = 200  # 每次开工的固定成本

p = mp.LpVariable.dicts("p", range(T), lowBound=0, upBound=capacity)
s = mp.LpVariable.dicts("s", range(T), lowBound=0)
# 是否开工
y = mp.LpVariable.dicts("y", range(T), cat=mp.LpBinary)

prob = mp.LpProblem("inventory_startup", mp.LpMinimize)
prob += mp.lpSum(prod_cost * p[t] + hold_cost * s[t] + startup_cost * y[t]
                 for t in range(T))

for t in range(T):
    if t == 0:
        prob += s[t] == p[t] - demand[t]
    else:
        prob += s[t] == s[t - 1] + p[t] - demand[t]
    # 大 M 约束：不开工则不生产
    prob += p[t] <= capacity * y[t]

prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
for t in range(T):
    print(f"  时段 {t}: 开工 {y[t].varValue > 0.5}, 生产 {p[t].varValue:.1f}")
```

---

## 多目标生产计划

!!! info "问题背景"

    同时最大化利润与最小化污染。用加权法转化为单目标。

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)  # 产品 A 产量
y = mp.LpVariable("y", lowBound=0)  # 产品 B 产量

profit = 3 * x + 2 * y       # 利润
pollution = 2 * x + 5 * y    # 污染

# 加权：最大化 0.7 * 利润 - 0.3 * 污染
weight_profit = 0.7
weight_pollution = 0.3

prob = mp.LpProblem("multi_obj", mp.LpMaximize)
prob += weight_profit * profit - weight_pollution * pollution
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

prob.solve()
print(f"利润: {profit.value()}")
print(f"污染: {pollution.value()}")
print(f"x = {x.varValue}, y = {y.varValue}")
```

### Pareto 前沿扫描

通过扫描权重得到 Pareto 前沿：

```python
import minipulp as mp

results = []
for w in [i / 10 for i in range(11)]:
    x = mp.LpVariable("x", lowBound=0)
    y = mp.LpVariable("y", lowBound=0)

    prob = mp.LpProblem(f"multi_{w}", mp.LpMaximize)
    prob += w * (3 * x + 2 * y) - (1 - w) * (2 * x + 5 * y)
    prob += 2 * x + y <= 100
    prob += x + y <= 80
    prob += x <= 40

    prob.solve()
    if prob.status == mp.LpStatusOptimal:
        results.append((w, 3 * x.varValue + 2 * y.varValue,
                        2 * x.varValue + 5 * y.varValue))

for w, profit, pollution in results:
    print(f"权重 {w:.1f}: 利润 {profit:.1f}, 污染 {pollution:.1f}")
```

---

## 投资组合问题

!!! info "问题背景"

    简化的投资组合：选若干项目投资，最大化收益，限制风险。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

projects = ["A", "B", "C", "D", "E"]
return_rate = {"A": 0.08, "B": 0.12, "C": 0.15, "D": 0.07, "E": 0.10}
risk = {"A": 0.02, "B": 0.05, "C": 0.08, "D": 0.01, "E": 0.04}
min_invest = {"A": 100, "B": 200, "C": 300, "D": 50, "E": 150}

budget = 1000
max_risk = 0.05  # 平均风险上限

# 是否投资
y = mp.LpVariable.dicts("y", projects, cat=mp.LpBinary)
# 投资额
x = mp.LpVariable.dicts("x", projects, lowBound=0)

prob = mp.LpProblem("portfolio", mp.LpMaximize)
prob += mp.lpSum(return_rate[p] * x[p] for p in projects)

# 预算约束
prob += mp.lpSum(x[p] for p in projects) <= budget

# 风险约束
prob += mp.lpSum(risk[p] * x[p] for p in projects) <= max_risk * budget

# 最小投资额约束（大 M）
for p in projects:
    prob += x[p] >= min_invest[p] * y[p]
    prob += x[p] <= budget * y[p]

prob.solve(solver=PULP_CBC_CMD())
print(f"最大收益: {prob.objective.value()}")
for p in projects:
    if y[p].varValue > 0.5:
        print(f"  投资 {p}: {x[p].varValue:.1f}")
```

---

## 求解器选择

```python
from minipulp.solvers import SimplexCore, SimplexCpp, PULP_CBC_CMD

# 纯 Python 单纯形法（教学透明）
prob.solve(solver=SimplexCore())

# C++ 单纯形法（性能加速）
prob.solve(solver=SimplexCpp())

# CBC 求解器（支持整数规划）
prob.solve(solver=PULP_CBC_CMD())

# 默认求解器（自动选最优可用）
prob.solve()
```

| 求解器 | 整数规划 | 依赖 | 适用场景 |
|-------|---------|------|---------|
| `SimplexCore` | 不支持 | 零依赖 | 教学、小规模 |
| `SimplexCpp` | 不支持 | 需编译 | 中规模连续 LP |
| `PULP_CBC_CMD` | 支持 | 需 CBC | 整数规划、大规模 |

### 求解器参数

```python
# CBC 显示输出
prob.solve(solver=PULP_CBC_CMD(msg=True))

# CBC 时间限制（秒）
prob.solve(solver=PULP_CBC_CMD(timeLimit=60))

# CBC 指定路径
prob.solve(solver=PULP_CBC_CMD(path="/usr/local/bin/cbc"))
```

### 检查求解器可用性

```python
from minipulp.solvers import SimplexCore, SimplexCpp, PULP_CBC_CMD

print(f"SimplexCore: {SimplexCore().available()}")  # 总是 True
print(f"SimplexCpp:  {SimplexCpp().available()}")   # 取决于是否编译
print(f"PULP_CBC_CMD: {PULP_CBC_CMD().available()}")  # 取决于 CBC 是否安装
```

---

## 批量建模

!!! info "技巧"

    用 `LpVariable.dicts` 和 `LpVariable.matrix` 批量创建变量，用 `lpSum` 求和，避免循环中创建中间对象。

### 一维变量字典

```python
import minipulp as mp

n = 100
x = mp.LpVariable.dicts("x", range(n), lowBound=0)

prob = mp.LpProblem("batch", mp.LpMinimize)
prob += mp.lpSum(x[i] for i in range(n))
for i in range(n - 1):
    prob += x[i] + x[i + 1] >= 1

prob.solve()
```

### 二维变量矩阵

```python
rows = range(50)
cols = range(30)
x = mp.LpVariable.matrix("x", rows, cols, lowBound=0)

prob = mp.LpProblem("matrix", mp.LpMinimize)
prob += mp.lpSum(x[i][j] for i in rows for j in cols)
for i in rows:
    prob += mp.lpSum(x[i][j] for j in cols) >= 1
for j in cols:
    prob += mp.lpSum(x[i][j] for i in rows) >= 1

prob.solve()
```

### 用生成器表达式

`lpSum` 接受生成器，避免先构造列表：

```python
# 推荐：生成器
prob += mp.lpSum(cost[i] * x[i] for i in range(n))

# 也可以：列表
prob += mp.lpSum([cost[i] * x[i] for i in range(n)])
```

---

## 调试技巧

### 打印问题

```python
# 打印 LP 文件格式
print(mp.write_lp(prob))
```

### 检查状态

```python
prob.solve()
print(f"状态码: {prob.status}")
print(f"状态消息: {prob.status_msg}")

if prob.status == mp.LpStatusOptimal:
    print("找到最优解")
elif prob.status == mp.LpStatusInfeasible:
    print("问题不可行")
elif prob.status == mp.LpStatusUnbounded:
    print("问题无界")
else:
    print(f"其他状态: {prob.status_msg}")
```

### 检查约束满足

```python
for name, con in prob.constraints.items():
    val = con.lhs.value()
    if con.sense == mp.LpConstraintSense.LE:
        ok = val <= 1e-6
    elif con.sense == mp.LpConstraintSense.GE:
        ok = val >= -1e-6
    else:  # EQ
        ok = abs(val) <= 1e-6
    print(f"  {name}: {val:.4f} {'OK' if ok else 'VIOLATED'}")
```

### 用纯 Python 求解器调试

`SimplexCore` 是纯 Python 实现，可以断点调试：

```python
from minipulp.solvers import SimplexCore

prob.solve(solver=SimplexCore())
# 可以在 simplex_py.py 中设断点
```

### 保存 LP 文件供外部求解器使用

```python
with open("problem.lp", "w") as f:
    f.write(mp.write_lp(prob))

# 用 CBC 命令行求解
# $ cbc problem.lp solve solution.sol
```

---

## 常见错误与解决

??? warning "变量名冲突"

    ```python
    x1 = mp.LpVariable("x")  # 名字 "x"
    x2 = mp.LpVariable("x")  # 又一个 "x"，会冲突！
    ```

    **解决**：每个变量用唯一名字。

??? warning "非线性表达式"

    ```python
    x * y  # TypeError: 不能将两个含变量的表达式相乘
    ```

    **解决**：线性规划不支持变量相乘。如需非线性，用 Pyomo。

??? warning "未设置目标函数"

    ```python
    prob = mp.LpProblem("demo")
    prob += 2 * x + y <= 100  # 只有约束
    prob.solve()  # 报错：未设置目标
    ```

    **解决**：先 `prob += 3 * x + 2 * y` 设置目标。

??? warning "用错求解器"

    ```python
    x = mp.LpVariable("x", cat=mp.LpBinary)
    prob.solve(solver=SimplexCore())  # SimplexCore 不支持整数变量
    ```

    **解决**：整数规划用 `PULP_CBC_CMD`。

---

## 更多示例

### 两阶段决策

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 第一阶段：建设产能
cap_build = mp.LpVariable("cap_build", lowBound=0, cat=mp.LpInteger)
# 第二阶段：实际生产
prod = mp.LpVariable("prod", lowBound=0)

prob = mp.LpProblem("two_stage", mp.LpMaximize)
prob += 5 * prod - 10 * cap_build  # 收入 - 建设成本
prob += prod <= cap_build * 10     # 产能约束
prob += prod <= 100                # 市场需求

prob.solve(solver=PULP_CBC_CMD())
print(f"建设产能: {cap_build.varValue}")
print(f"实际生产: {prod.varValue}")
print(f"利润: {prob.objective.value()}")
```

### 多商品流

```python
import minipulp as mp

# 两种商品流过同一网络
commodities = ["K1", "K2"]
edges = [("s", "t"), ("s", "a"), ("a", "t")]
capacity = {("s", "t"): 10, ("s", "a"): 8, ("a", "t"): 6}
demand = {"K1": 5, "K2": 4}

f = {(k, e): mp.LpVariable(f"f_{k}_{e[0]}_{e[1]}", lowBound=0)
     for k in commodities for e in edges}

prob = mp.LpProblem("multi_commodity", mp.LpMinimize)
prob += 0  # 可行性问题，目标为 0

# 容量共享
for e in edges:
    prob += mp.lpSum(f[(k, e)] for k in commodities) <= capacity[e]

# 每种商品的流守恒
for k in commodities:
    prob += f[(k, ("s", "t"))] + f[(k, ("s", "a"))] == demand[k]
    prob += f[(k, ("s", "a"))] == f[(k, ("a", "t"))]

prob.solve()
print(f"状态: {prob.status_msg}")
for k in commodities:
    for e in edges:
        print(f"  {k} on {e}: {f[(k, e)].varValue:.1f}")
```

### 旅行商问题（TSP）简化版

!!! warning "完整 TSP 需要消除子回路"

    这里展示基础建模，完整 TSP 需要额外的子回路消除约束（MTZ 或 lazy constraint）。

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 4 城市对称 TSP
cities = [0, 1, 2, 3]
dist = [
    [0, 10, 15, 20],
    [10, 0, 35, 25],
    [15, 35, 0, 30],
    [20, 25, 30, 0],
]

# x_ij = 1 表示从 i 到 j
x = mp.LpVariable.matrix("x", cities, cities, cat=mp.LpBinary)

prob = mp.LpProblem("tsp", mp.LpMinimize)
prob += mp.lpSum(dist[i][j] * x[i][j] for i in cities for j in cities if i != j)

# 每城市恰好一次出
for i in cities:
    prob += mp.lpSum(x[i][j] for j in cities if j != i) == 1
# 每城市恰好一次入
for j in cities:
    prob += mp.lpSum(x[i][j] for i in cities if i != j) == 1

prob.solve(solver=PULP_CBC_CMD())
print(f"距离: {prob.objective.value()}")
for i in cities:
    for j in cities:
        if i != j and x[i][j].varValue > 0.5:
            print(f"  {i} -> {j}")
```

!!! note "注意"

    上述建模可能产生子回路。完整 TSP 需要添加 MTZ 约束或 lazy constraint 消除子回路。这超出 minipulp 当前范围，建议用专门求解器如 [Concorde](https://github.com/jvkersch/pyconcorde)。

---

## 示例索引

| 示例 | 类型 | 变量类型 | 求解器 | 经典来源 |
|------|------|---------|--------|---------|
| 生产计划 | 连续 LP | 连续 | 默认 | — |
| 饮食问题 | 连续 LP | 连续 | 默认 | Stigler 1945 |
| 资源分配 | 连续 LP | 连续 | 默认 | — |
| 运输问题 | 连续 LP | 连续 | 默认 | Hitchcock 1941 |
| 指派问题 | 整数规划 | 二元 | CBC | König |
| 背包问题 | 整数规划 | 二元 | CBC | — |
| 多维背包 | 整数规划 | 二元 | CBC | — |
| 混合整数规划 | MILP | 混合 | CBC | — |
| 最大流 | 连续 LP | 连续 | 默认 | Ford-Fulkerson |
| 最短路 | 整数规划 | 二元 | CBC | Dijkstra |
| 最小费用流 | 连续 LP | 连续 | 默认 | — |
| 设施选址 | MILP | 混合 | CBC | — |
| 集合覆盖 | 整数规划 | 二元 | CBC | Karp |
| 排班 | 整数规划 | 整数 | CBC | — |
| 切割下料 | 整数规划 | 整数 | CBC | Gilmore-Gomory |
| 生产库存 | 连续 LP | 连续 | 默认 | — |
| 多目标 | 连续 LP | 连续 | 默认 | — |
| 投资组合 | MILP | 混合 | CBC | Markowitz |

---

## 下一步

- [:octicons-book-24: 学习教程](tutorial/phase1-expressions.md) — 从零理解 minipulp 的实现
- [:octicons-code-24: API 参考](api/minipulp.md) — 查阅完整 API
- [:octicons-lightbulb-24: 设计哲学](principles/philosophy.md) — 理解 PuLP 的设计精髓
