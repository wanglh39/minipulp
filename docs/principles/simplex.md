# 单纯形法推导

> minipulp 的 `SimplexCore` 求解器背后的算法：两阶段单纯形法。

---

## 几何直觉

线性规划在多面体上优化线性目标。最优解一定在**顶点**上。

单纯形法的核心思想：**沿多面体的边，从一个顶点走到更优的相邻顶点**，直到找不到更优的邻居。

```
        max c^T x
        |
    ────●────  ← 最优顶点
   /    |\
  /     | \
 ●──────●──●
  \     | /
   ─────●────  ← 起始顶点
```

---

## 代数表示

### 标准形式

```
min  c^T x
s.t. Ax = b
     x >= 0
```

### 基本解

把变量分为**基变量**（$x_B$）和**非基变量**（$x_N$）。令 $x_N = 0$，解 $x_B = B^{-1} b$（$B$ 是基矩阵）。

若 $x_B \geq 0$，这是**可行基本解**，对应多面体的一个顶点。

---

## 单纯形表

用增广矩阵表示：

$$
\begin{array}{c|cc|c}
  & x_N & x_B & \text{RHS} \\
\hline
\text{约束} & N & B & b \\
\hline
\text{目标} & c_N & c_B & 0 \\
\end{array}
$$

经过转轴（高斯消元）后，基矩阵 $B$ 变为单位阵 $I$：

$$
\begin{array}{c|cc|c}
  & x_N & x_B & \text{RHS} \\
\hline
\text{约束} & \bar{N} & I & \bar{b} \\
\hline
\text{检验} & \bar{c}_N & 0 & -z \\
\end{array}
$$

其中：

- $\bar{b} = B^{-1} b \geq 0$（可行性）
- $\bar{c}_N = c_N - c_B B^{-1} N$（**检验数/缩减成本**）
- $z = c_B B^{-1} b$（当前目标值）

---

## 最优性条件

**若所有 $\bar{c}_N \geq 0$，当前基本解最优。**

直觉：$\bar{c}_j < 0$ 意味着把非基变量 $x_j$ 增大（从 0 变正），目标会下降。所以只要有 $\bar{c}_j < 0$，就能改进。

---

## 转轴操作

### 1. 选进基变量

找 $\bar{c}_j < 0$ 的列 $j$（Bland 规则：选下标最小的，避免循环）。

### 2. 选离基变量

在列 $j$ 中找 $\bar{a}_{ij} > 0$ 的行，计算比值 $\bar{b}_i / \bar{a}_{ij}$，选最小比值的行 $r$：

$$
r = \arg\min_i \frac{\bar{b}_i}{\bar{a}_{ij}}, \quad \bar{a}_{ij} > 0
$$

**最小比值原则**：保证转轴后 $\bar{b} \geq 0$（可行性不破坏）。

若所有 $\bar{a}_{ij} \leq 0$，问题**无界**（$x_j$ 可无限增大）。

### 3. 高斯消元

以 $\bar{a}_{rj}$ 为主元：

1. 主元行归一化：第 $r$ 行除以 $\bar{a}_{rj}$
2. 其他行消元：第 $i$ 行减去 $\bar{a}_{ij}$ 倍的主元行

这就是 `SimplexCore._pivot` 做的事：

```python
def _pivot(self, A, b, pr, pc, m, n_total):
    pivot_val = A[pr][pc]
    for j in range(n_total):
        A[pr][j] /= pivot_val    # 归一化主元行
    b[pr] /= pivot_val

    for i in range(m):
        if i == pr: continue
        factor = A[i][pc]
        for j in range(n_total):
            A[i][j] -= factor * A[pr][j]   # 消元其他行
        b[i] -= factor * b[pr]
```

---

## 两阶段法

### 问题：初始可行基从哪来？

如果原问题有 `>=` 或 `==` 约束，松弛变量不能直接构成可行基。

### 阶段一：求可行基

引入**人工变量** $a$，解辅助问题：

$$
\min \sum a_i \quad \text{s.t. 原约束} + a_i \text{ 人工变量}
$$

人工变量天然构成初始基（$a = b \geq 0$）。

- 若最优值 $> 0$：原问题**不可行**
- 若最优值 $= 0$：所有 $a_i = 0$，得到原问题的可行基

### 阶段二：求最优

从阶段一的可行基出发，用原目标函数继续单纯形迭代。

---

## 在 minipulp 中的实现

```python
class SimplexCore(LpSolver):
    def actualSolve(self, problem):
        std = self._extract(problem)          # 提取矩阵
        status, solution = self._solve(std)   # 两阶段单纯形
        self._backfill(std, status, solution) # 回填 varValue
        return status

    def _solve(self, std):
        A, b, basis, n_total, art = self._build_tableau(...)
        if art:                               # 阶段一
            self._simplex_loop(A, b, phase1_cost, basis, ...)
        status = self._simplex_loop(A, b, full_cost, basis, ...)  # 阶段二
        solution = [b[i] if basis[i]==j else 0 for j in range(n)]
        return status, solution
```

---

## Bland 规则：避免循环

单纯形法理论上可能**循环**（在退化解间无限转圈）。Bland 规则：

- 进基变量：选 $\bar{c}_j < 0$ 中**下标最小**的
- 离基变量：选最小比值中**下标最小**的

保证有限步终止。代价是可能比 Dantzig 规则（最负系数）慢，但教学版优先正确性。

```python
# Bland 规则：选第一个 reduced_cost < 0
for j in range(n_total):
    reduced = cost[j] - sum(c_basis[i] * A[i][j] for i in range(m))
    if reduced < -_EPS:
        pivot_col = j
        break
```