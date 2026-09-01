# 示例

经典线性规划问题示例，展示 minipulp 建模能力。

---

## 目录

- [生产计划（连续 LP）](#生产计划连续-lp)
- [饮食问题（最小化）](#饮食问题最小化)
- [运输问题](#运输问题)
- [指派问题（整数规划）](#指派问题整数规划)
- [背包问题（二元变量）](#背包问题二元变量)
- [混合整数规划](#混合整数规划)

---

## 生产计划（连续 LP）

$$
\begin{aligned}
\max \quad & 3x + 2y \\
\text{s.t.} \quad & 2x + y \leq 100 \\
& x + y \leq 80 \\
& x \leq 40 \\
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

---

## 饮食问题（最小化）

选择食物组合，最小化成本同时满足营养需求。

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

---

## 运输问题

3 个工厂向 4 个客户运输，最小化总运输成本。

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
```

---

## 指派问题（整数规划）

将 4 个任务分配给 4 个工人，最小化总成本。

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
```

---

## 背包问题（二元变量）

0-1 背包问题：选物品放入背包，最大化价值，不超过容量。

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

## 混合整数规划

部分变量连续，部分变量整数。

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
