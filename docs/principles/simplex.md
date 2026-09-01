# 单纯形法推导

> minipulp 的 `SimplexCore` 求解器背后的算法：两阶段单纯形法。
>
> 本文从几何直觉出发，逐步推导单纯形法的每一个概念：多面体、顶点、
> 基本可行解、检验数、转轴操作、最优性条件。然后讲解两阶段法处理
> 一般线性规划的完整流程，并对照 minipulp 的 Python 实现。

---

## 目录

1. [几何直觉](#几何直觉)
2. [线性规划的标准形式](#线性规划的标准形式)
3. [一般形式到标准形式的转化](#一般形式到标准形式的转化)
4. [多面体的几何结构](#多面体的几何结构)
5. [基本可行解的代数定义](#基本可行解的代数定义)
6. [顶点与基本可行解的等价性](#顶点与基本可行解的等价性)
7. [单纯形表的矩阵表示](#单纯形表的矩阵表示)
8. [检验数的推导](#检验数的推导)
9. [最优性条件的证明](#最优性条件的证明)
10. [转轴操作的详细步骤](#转轴操作的详细步骤)
11. [最小比值测试的原理](#最小比值测试的原理)
12. [Bland 规则与避免循环](#bland-规则与避免循环)
13. [两阶段法的完整推导](#两阶段法的完整推导)
14. [退化处理](#退化处理)
15. [不可行和无界的检测](#不可行和无界的检测)
16. [完整的数值示例](#完整的数值示例)
17. [在 minipulp 中的实现对照](#在-minipulp-中的实现对照)
18. [复杂度分析](#复杂度分析)
19. [与其他算法的比较](#与其他算法的比较)
20. [总结](#总结)

---

## 几何直觉

线性规划在多面体上优化线性目标。最优解一定在**顶点**上。

单纯形法的核心思想：**沿多面体的边，从一个顶点走到更优的相邻顶点**，直到找不到更优的邻居。

### 二维示例

考虑：

$$
\begin{aligned}
\max \quad & 3x + 2y \\
\text{s.t.} \quad & 2x + y \leq 100 \\
& x + y \leq 80 \\
& x \leq 40 \\
& x, y \geq 0
\end{aligned}
$$

可行域是一个五边形：

```
        y
        │
   80 ──●──────●
        │ \    │
        │  \   │
   60 ──●   \  │
        │    \ │
        │     \│
   40 ──●──────●─── x
        │      40  50
        │
        0
```

顶点：(0,0), (40,0), (40,40), (20,60), (0,80)。

在顶点计算目标值 $3x + 2y$：

- (0,0): 0
- (40,0): 120
- (40,40): 200
- (20,60): 180
- (0,80): 160

最优顶点是 (40,40)，目标值 200。

### 为什么最优解在顶点

线性目标 $c^T x$ 的等高线是平行超平面。最优解是等高线最后接触可行域的点。由于可行域是凸多面体，等高线最后接触的点一定是顶点（或边/面，但边上至少有一个顶点取相同值）。

### 单纯形法的几何过程

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

1. 从一个顶点出发（通常是原点）。
2. 检查相邻顶点是否有更优的。
3. 如果有，走到那个更优的相邻顶点。
4. 重复，直到没有更优的邻居——当前顶点最优。

### 为什么叫"单纯形"

单纯形（simplex）是 $n$ 维空间中最简单的多面体（$n+1$ 个顶点的凸包）。单纯形法在可行域的"单纯形"结构上移动，因此得名。

---

## 线性规划的标准形式

单纯形法要求问题化为**标准形式**：

$$
\begin{aligned}
\min \quad & c^T x \\
\text{s.t.} \quad & A x = b \\
& x \geq 0
\end{aligned}
$$

其中 $A \in \mathbb{R}^{m \times n}$，$b \in \mathbb{R}^m$，$c, x \in \mathbb{R}^n$，且 $b \geq 0$。

### 标准形式的特征

1. **目标是最小化**：如果是最大化，取负目标。
2. **约束是等式**：不等式通过添加松弛变量转化为等式。
3. **变量非负**：自由变量通过变量替换转化为非负变量。
4. **右端项非负**：如果某行 $b_i < 0$，整行乘以 $-1$。

### 为什么要标准形式

标准形式让单纯形法的逻辑统一：

- 等式约束对应矩阵行，便于高斯消元。
- 非负变量对应基变量/非基变量的划分。
- 非负右端项保证初始基本解可行。

---

## 一般形式到标准形式的转化

### 1. 最大化转最小化

$$
\max c^T x \iff \min (-c)^T x
$$

最优解相同，最优值取负。

### 2. 不等式转等式

**小于等于约束** $a_i^T x \leq b_i$：添加松弛变量 $s_i \geq 0$：

$$
a_i^T x + s_i = b_i, \quad s_i \geq 0
$$

**大于等于约束** $a_i^T x \geq b_i$：添加剩余变量 $s_i \geq 0$：

$$
a_i^T x - s_i = b_i, \quad s_i \geq 0
$$

### 3. 自由变量替换

如果 $x_j$ 是自由变量（无界），拆成两个非负变量：

$$
x_j = x_j^+ - x_j^-, \quad x_j^+, x_j^- \geq 0
$$

### 4. 有下界变量平移

如果 $x_j \geq l_j$，令 $x_j' = x_j - l_j \geq 0$，代入消去 $x_j$。

### 5. 右端项非负

如果某行 $b_i < 0$，整行乘以 $-1$：

$$
a_i^T x = b_i \iff (-a_i)^T x = -b_i
$$

同时翻转约束方向（如果是不等式）。

### 转化示例

原问题：

$$
\begin{aligned}
\max \quad & 3x + 2y \\
\text{s.t.} \quad & 2x + y \leq 100 \\
& x + y \leq 80 \\
& x \leq 40 \\
& x, y \geq 0
\end{aligned}
$$

转化后（标准形式）：

$$
\begin{aligned}
\min \quad & -3x - 2y \\
\text{s.t.} \quad & 2x + y + s_1 = 100 \\
& x + y + s_2 = 80 \\
& x + s_3 = 40 \\
& x, y, s_1, s_2, s_3 \geq 0
\end{aligned}
$$

矩阵形式：

$$
A = \begin{pmatrix} 2 & 1 & 1 & 0 & 0 \\ 1 & 1 & 0 & 1 & 0 \\ 1 & 0 & 0 & 0 & 1 \end{pmatrix}, \quad
b = \begin{pmatrix} 100 \\ 80 \\ 40 \end{pmatrix}, \quad
c = \begin{pmatrix} -3 \\ -2 \\ 0 \\ 0 \\ 0 \end{pmatrix}
$$

---

## 多面体的几何结构

### 多面体的定义

**多面体**（polyhedron）是有限个线性不等式的解集：

$$
P = \{x \in \mathbb{R}^n \mid A x \leq b\}
$$

### 顶点

$x \in P$ 是**顶点**（vertex/extreme point），如果 $x$ 不能表示为 $P$ 中其他两点的严格凸组合：

$$
x = \lambda y + (1-\lambda) z, \quad y, z \in P, \lambda \in (0, 1) \implies y = z = x
$$

### 边

$x, y \in P$ 之间的**边**（edge）是 $P$ 的一维面，$x$ 和 $y$ 是边的端点。

### 有界性

- 如果 $P$ 有界（多胞形/polytope），最优解一定存在。
- 如果 $P$ 无界，问题可能无界（目标可以无限优化）。

### 顶点数量的上界

$n$ 个变量、$m$ 个约束的多面体，顶点数最多 $\binom{n}{m}$。这可能指数大，但单纯形法在实践中通常只访问 $O(n)$ 个顶点。

---

## 基本可行解的代数定义

### 基本解

考虑标准形式 $Ax = b, x \geq 0$，其中 $A \in \mathbb{R}^{m \times n}$，$\text{rank}(A) = m$。

**基**（basis）$B$ 是 $\{1, \ldots, n\}$ 的 $m$ 元子集，使得 $A_B$（$A$ 的 $B$ 列子矩阵）可逆。

**基本解**：令非基变量 $x_N = 0$，解基变量 $x_B = A_B^{-1} b$。

### 基本可行解

如果 $x_B \geq 0$，基本解是**基本可行解**（basic feasible solution, BFS）。

### 退化的基本可行解

如果 $x_B$ 有零分量，基本可行解是**退化**的（degenerate）。退化对应多个基表示同一顶点。

### 示例

标准形式：

$$
A = \begin{pmatrix} 2 & 1 & 1 & 0 & 0 \\ 1 & 1 & 0 & 1 & 0 \\ 1 & 0 & 0 & 0 & 1 \end{pmatrix}, \quad
b = \begin{pmatrix} 100 \\ 80 \\ 40 \end{pmatrix}
$$

取基 $B = \{3, 4, 5\}$（松弛变量）：

$$
A_B = I, \quad x_B = b = \begin{pmatrix} 100 \\ 80 \\ 40 \end{pmatrix} \geq 0
$$

这是基本可行解，对应原问题的 $(x, y) = (0, 0)$。

---

## 顶点与基本可行解的等价性

**定理**：$x$ 是多面体 $P = \{x \mid Ax = b, x \geq 0\}$ 的顶点当且仅当 $x$ 是基本可行解。

**证明**：

（$\Rightarrow$）设 $x$ 是顶点。令 $J = \{j \mid x_j > 0\}$（正分量下标）。可以证明 $A_J$ 的列线性无关（否则 $x$ 可以表示为其他两点的凸组合，矛盾）。因此可以把 $J$ 扩展成基 $B$，$x$ 是对应的基本可行解。

（$\Leftarrow$）设 $x$ 是基本可行解，对应基 $B$。若 $x = \lambda y + (1-\lambda) z$，$y, z \in P$，$\lambda \in (0,1)$。由于 $x_N = 0$ 且 $y, z \geq 0$，有 $y_N = z_N = 0$。因此 $y_B = z_B = A_B^{-1} b = x_B$，即 $y = z = x$。所以 $x$ 是顶点。$\blacksquare$

### 推论

- 顶点数 = 基本可行解数 $\leq \binom{n}{m}$。
- 如果最优解存在，一定有最优顶点。
- 单纯形法在顶点间移动，等价于在基本可行解间转轴。

---

## 单纯形表的矩阵表示

### 初始表

把变量分为基变量 $x_B$ 和非基变量 $x_N$。重排矩阵：

$$
A = [B \mid N], \quad c = \begin{pmatrix} c_B \\ c_N \end{pmatrix}, \quad x = \begin{pmatrix} x_B \\ x_N \end{pmatrix}
$$

约束 $Ax = b$ 变成：

$$
B x_B + N x_N = b
$$

目标 $c^T x = c_B^T x_B + c_N^T x_N$。

### 消元后的表

从约束解出 $x_B$：

$$
x_B = B^{-1} b - B^{-1} N x_N
$$

代入目标：

$$
\begin{aligned}
z &= c_B^T x_B + c_N^T x_N \\
  &= c_B^T (B^{-1} b - B^{-1} N x_N) + c_N^T x_N \\
  &= c_B^T B^{-1} b + (c_N^T - c_B^T B^{-1} N) x_N
\end{aligned}
$$

### 单纯形表

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

- $\bar{N} = B^{-1} N$（非基变量的系数）
- $\bar{b} = B^{-1} b \geq 0$（基变量的值，可行性）
- $\bar{c}_N = c_N - c_B^T B^{-1} N$（**检验数/缩减成本**）
- $z = c_B^T B^{-1} b$（当前目标值）

### 表的含义

- **约束行**：$x_B + \bar{N} x_N = \bar{b}$，即 $x_B = \bar{b} - \bar{N} x_N$。
- **检验行**：$z = z_0 + \bar{c}_N^T x_N$，即目标用非基变量表示。

当前基本可行解：$x_N = 0, x_B = \bar{b}$，目标值 $z_0$。

---

## 检验数的推导

### 检验数的定义

非基变量 $x_j$ 的检验数（缩减成本）：

$$
\bar{c}_j = c_j - c_B^T B^{-1} A_j
$$

其中 $A_j$ 是 $A$ 的第 $j$ 列。

### 检验数的含义

检验数 $\bar{c}_j$ 表示**把非基变量 $x_j$ 从 0 增加到 1（同时调整基变量保持可行）时，目标的改变量**。

推导：令 $x_j = \epsilon$，其他非基变量仍为 0。从约束 $x_B = \bar{b} - B^{-1} A_j \epsilon$。目标：

$$
z = c_B^T (\bar{b} - B^{-1} A_j \epsilon) + c_j \epsilon = z_0 + (c_j - c_B^T B^{-1} A_j) \epsilon = z_0 + \bar{c}_j \epsilon
$$

因此 $\bar{c}_j$ 是 $x_j$ 增加单位时目标的改变率。

### 最小化问题的检验数

对于最小化问题：

- $\bar{c}_j < 0$：增加 $x_j$ 会**减小**目标，应该进基。
- $\bar{c}_j > 0$：增加 $x_j$ 会**增大**目标，不应该进基。
- $\bar{c}_j = 0$：增加 $x_j$ 不改变目标，退化情况。

### 最大化问题的检验数

对于最大化问题（或最小化 $-c^T x$），符号相反：

- $\bar{c}_j > 0$：增加 $x_j$ 会**增大**目标，应该进基。
- $\bar{c}_j < 0$：不应该进基。

minipulp 统一转化为最小化处理，因此用 $\bar{c}_j < 0$ 作为进基判据。

---

## 最优性条件的证明

**定理（最优性条件）**：对于最小化问题，若所有检验数 $\bar{c}_N \geq 0$，当前基本可行解最优。

**证明**：

当前目标值 $z_0 = c_B^T B^{-1} b$。任意可行解 $x$ 满足 $x_N \geq 0$，其目标值：

$$
z = z_0 + \bar{c}_N^T x_N
$$

若所有 $\bar{c}_N \geq 0$ 且 $x_N \geq 0$，则 $\bar{c}_N^T x_N \geq 0$，因此 $z \geq z_0$。

当前基本可行解 $x_N = 0$ 使 $z = z_0$，达到下界，因此最优。$\blacksquare$

### 直觉解释

$\bar{c}_j < 0$ 意味着把非基变量 $x_j$ 增大（从 0 变正），目标会下降。所以只要有 $\bar{c}_j < 0$，就能改进。当所有 $\bar{c}_j \geq 0$ 时，没有任何改进方向，当前解最优。

### 退化的最优性

如果有 $\bar{c}_j = 0$，当前解仍最优，但可能不唯一——把 $x_j$ 增大不会改变目标，会得到另一个最优解。这说明最优解可能是一个面，而非单个顶点。

---

## 转轴操作的详细步骤

转轴（pivot）是从一个基本可行解移动到相邻基本可行解的操作。

### 1. 选进基变量

找 $\bar{c}_j < 0$ 的列 $j$。这个非基变量 $x_j$ 将从 0 变正，进入基。

**选择规则**：

- **Dantzig 规则**：选 $\bar{c}_j$ 最负的列。实践中快，但可能循环。
- **Bland 规则**：选下标最小的 $\bar{c}_j < 0$ 的列。保证不循环，但可能慢。
- **陡边规则**：选目标下降最陡的方向。实践中很快。

minipulp 用 Bland 规则（教学优先正确性）。

### 2. 选离基变量

在列 $j$ 中找 $\bar{a}_{ij} > 0$ 的行，计算比值 $\bar{b}_i / \bar{a}_{ij}$，选最小比值的行 $r$：

$$
r = \arg\min_i \frac{\bar{b}_i}{\bar{a}_{ij}}, \quad \bar{a}_{ij} > 0
$$

这一步叫**最小比值测试**（minimum ratio test）。

**为什么要求 $\bar{a}_{ij} > 0$**：保证 $x_j$ 增大时 $x_{B_i}$ 减小（而非增大），才能在某个点让 $x_{B_r}$ 减到 0 离基。

**若所有 $\bar{a}_{ij} \leq 0$**：$x_j$ 可以无限增大而不违反 $x_B \geq 0$，问题**无界**。

### 3. 高斯消元

以 $\bar{a}_{rj}$ 为主元，做高斯消元：

1. **主元行归一化**：第 $r$ 行除以 $\bar{a}_{rj}$，使主元变成 1。
2. **其他行消元**：第 $i$ 行减去 $\bar{a}_{ij}$ 倍的主元行，使主元列其他元素变成 0。

### 转轴的数学表示

转轴前：

$$
x_{B_r} + \sum_{k \in N} \bar{a}_{rk} x_k = \bar{b}_r
$$

转轴后（$x_j$ 进基，$x_{B_r}$ 离基）：

$$
x_j = \frac{\bar{b}_r}{\bar{a}_{rj}} - \sum_{k \in N, k \neq j} \frac{\bar{a}_{rk}}{\bar{a}_{rj}} x_k - \frac{1}{\bar{a}_{rj}} x_{B_r}
$$

其他行类似消元。

### 转轴后的基本可行解

$$
x_j = \frac{\bar{b}_r}{\bar{a}_{rj}}, \quad x_{B_i} = \bar{b}_i - \bar{a}_{ij} \cdot \frac{\bar{b}_r}{\bar{a}_{rj}} \quad (i \neq r), \quad \text{其他非基变量} = 0
$$

目标值变化：

$$
z_{\text{new}} = z_0 + \bar{c}_j \cdot \frac{\bar{b}_r}{\bar{a}_{rj}}
$$

由于 $\bar{c}_j < 0$ 且 $\bar{b}_r / \bar{a}_{rj} > 0$，目标下降。

---

## 最小比值测试的原理

### 目的

最小比值测试保证转轴后 $\bar{b} \geq 0$（可行性不破坏）。

### 推导

转轴前，$x_j$ 从 0 增大。基变量 $x_{B_i}$ 随之变化：

$$
x_{B_i} = \bar{b}_i - \bar{a}_{ij} x_j
$$

要保持 $x_{B_i} \geq 0$：

- 若 $\bar{a}_{ij} \leq 0$：$x_{B_i}$ 随 $x_j$ 增大而增大或不变，无约束。
- 若 $\bar{a}_{ij} > 0$：$x_{B_i}$ 随 $x_j$ 增大而减小，要求 $x_j \leq \bar{b}_i / \bar{a}_{ij}$。

因此 $x_j$ 的最大允许值：

$$
x_j^{\max} = \min_{i: \bar{a}_{ij} > 0} \frac{\bar{b}_i}{\bar{a}_{ij}}
$$

取最小比值的行 $r$，$x_{B_r}$ 第一个减到 0，成为离基变量。

### 退化情况

如果最小比值为 0（即某个 $\bar{b}_i = 0$），转轴后 $x_j = 0$，目标值不变。这是**退化转轴**——基变了但顶点没变。

---

## Bland 规则与避免循环

### 循环问题

单纯形法理论上可能**循环**（在退化解间无限转圈，目标值不变）。循环只在退化情况下发生。

### 循环的例子

某些精心构造的问题会让 Dantzig 规则循环。虽然实际中罕见，但理论上可能。

### Bland 规则

**Bland 规则**：

- **进基变量**：选 $\bar{c}_j < 0$ 中**下标最小**的。
- **离基变量**：选最小比值中**下标最小**的。

**定理（Bland）**：使用 Bland 规则的单纯形法有限步终止。

### 证明思路

反证法：假设循环。在循环中，某些变量反复进出基。设 $j^*$ 是这些变量中下标最大的。分析 $j^*$ 进基和离基的时刻，导出矛盾（$\bar{c}_{j^*}$ 既 < 0 又 $\geq 0$）。

### Bland 规则的代价

Bland 规则保证不循环，但可能比 Dantzig 规则慢——它不考虑改进幅度，只按下标选。实践中通常用 Dantzig 规则 + 退化处理（如扰动法），但教学版优先正确性，用 Bland 规则。

### minipulp 的实现

```python
# Bland 规则：选第一个 reduced_cost < 0
for j in range(n_total):
    reduced = cost[j] - sum(c_basis[i] * A[i][j] for i in range(m))
    if reduced < -_EPS:
        pivot_col = j
        break
```

选第一个满足条件的列，即下标最小的。

---

## 两阶段法的完整推导

### 问题：初始可行基从哪来？

单纯形法需要一个初始基本可行解。如果原问题只有 `<=` 约束且 $b \geq 0$，松弛变量直接构成初始基。但如果有 `>=` 或 `==` 约束，松弛/剩余变量不能直接构成可行基。

### 阶段一：求可行基

引入**人工变量** $a$，解辅助问题：

$$
\begin{aligned}
\min \quad & \sum_i a_i \\
\text{s.t.} \quad & A x + I a = b \\
& x, a \geq 0
\end{aligned}
$$

人工变量天然构成初始基：$a = b \geq 0$（假设 $b \geq 0$）。

### 阶段一的解读

- 人工变量是"违规"的度量——只有当约束无法满足时才需要 $a_i > 0$。
- 最小化 $\sum a_i$ 就是尽量减少违规。
- 若最优值 $= 0$：所有 $a_i = 0$，原约束满足，得到原问题的可行基。
- 若最优值 $> 0$：原问题**不可行**（无法让所有约束同时满足）。

### 阶段一后的处理

如果阶段一最优值 $= 0$，但某些人工变量仍在基中（取值为 0 的退化情况），需要把它们从基中驱赶出去：

1. 对每个在基中的人工变量 $a_k$（所在行 $r$）：
2. 在行 $r$ 找一个非人工变量 $x_j$，使 $\bar{a}_{rj} \neq 0$。
3. 以 $\bar{a}_{rj}$ 为主元转轴，$a_k$ 离基，$x_j$ 进基。
4. 如果找不到这样的 $x_j$，说明行 $r$ 是冗余的（可以删除）。

### 阶段二：求最优

从阶段一的可行基出发，用原目标函数继续单纯形迭代：

1. 丢弃人工变量（或固定为 0）。
2. 用原目标 $c^T x$ 计算检验数。
3. 继续转轴，直到所有检验数 $\geq 0$。

### 两阶段法的完整流程

```
1. 标准化问题（max → min, 加松弛/剩余变量, 右端项非负）
2. 添加人工变量
3. 阶段一：min Σ a_i
   - 初始基：人工变量
   - 单纯形迭代
   - 若最优值 > 0：原问题不可行，停止
   - 若最优值 = 0：驱赶基中人工变量
4. 阶段二：min c^T x
   - 初始基：阶段一得到的可行基
   - 单纯形迭代
   - 若无界：原问题无界
   - 若最优：得到最优解
5. 回填解值
```

---

## 退化处理

### 退化的定义

基本可行解是**退化**的，如果某些基变量取值为 0（$\bar{b}_i = 0$）。

### 退化的几何意义

退化对应多个基表示同一顶点。几何上，退化的顶点由多于 $n$ 个约束超平面相交（$n$ 是变量数）。

### 退化带来的问题

1. **循环**：退化转轴（目标值不变）可能反复发生，导致循环。
2. **性能下降**：退化转轴浪费计算，不推进算法。

### 处理方法

1. **Bland 规则**：保证不循环，但可能慢。
2. **扰动法**（lexicographic）：给 $\bar{b}$ 加微小扰动，破坏退化。
3. **两阶段法 + Bland**：minipulp 的选择，简单且正确。

### minipulp 的处理

minipulp 用 Bland 规则避免循环，不做特殊退化处理。对于教学目的，这足够了。生产求解器用更复杂的方法（如对偶单纯形 + steepest edge）。

---

## 不可行和无界的检测

### 不可行

**检测**：阶段一最优值 $> 0$。

**解释**：人工变量无法全部驱赶到 0，说明原约束无法同时满足。

**示例**：

$$
\begin{aligned}
\min \quad & x \\
\text{s.t.} \quad & x \leq 1 \\
& x \geq 3 \\
& x \geq 0
\end{aligned}
$$

$x$ 不能同时 $\leq 1$ 和 $\geq 3$，问题不可行。

阶段一引入人工变量 $a_1, a_2$：

$$
\min a_1 + a_2 \quad \text{s.t.} \quad x + s_1 + a_1 = 1, \quad x - s_2 + a_2 = 3
$$

最优解 $x = 1, a_1 = 0, a_2 = 2$，最优值 $2 > 0$，检测到不可行。

### 无界

**检测**：某次迭代中，进基列 $j$ 的所有 $\bar{a}_{ij} \leq 0$。

**解释**：$x_j$ 可以无限增大而不违反 $x_B \geq 0$，目标无限下降。

**证明**：令 $x_j = t \to \infty$，$x_{B_i} = \bar{b}_i - \bar{a}_{ij} t$。由于 $\bar{a}_{ij} \leq 0$，$x_{B_i} \geq \bar{b}_i \geq 0$。目标 $z = z_0 + \bar{c}_j t \to -\infty$（$\bar{c}_j < 0$）。

**示例**：

$$
\begin{aligned}
\min \quad & -x \\
\text{s.t.} \quad & x - y = 0 \\
& x, y \geq 0
\end{aligned}
$$

$x$ 可以无限增大（$y = x$ 同步增大），目标 $-x \to -\infty$，问题无界。

---

## 完整的数值示例

### 问题

$$
\begin{aligned}
\max \quad & 3x + 2y \\
\text{s.t.} \quad & 2x + y \leq 100 \\
& x + y \leq 80 \\
& x \leq 40 \\
& x, y \geq 0
\end{aligned}
$$

### 转化为标准形式

$$
\begin{aligned}
\min \quad & -3x - 2y \\
\text{s.t.} \quad & 2x + y + s_1 = 100 \\
& x + y + s_2 = 80 \\
& x + s_3 = 40 \\
& x, y, s_1, s_2, s_3 \geq 0
\end{aligned}
$$

### 初始单纯形表

基 $B = \{s_1, s_2, s_3\}$（松弛变量），非基 $N = \{x, y\}$。

$$
\begin{array}{c|ccccc|c}
  & x & y & s_1 & s_2 & s_3 & \text{RHS} \\
\hline
s_1 & 2 & 1 & 1 & 0 & 0 & 100 \\
s_2 & 1 & 1 & 0 & 1 & 0 & 80 \\
s_3 & 1 & 0 & 0 & 0 & 1 & 40 \\
\hline
z & -3 & -2 & 0 & 0 & 0 & 0 \\
\end{array}
$$

当前解：$x = 0, y = 0, s_1 = 100, s_2 = 80, s_3 = 40$，目标 $z = 0$。

### 迭代 1

**检验数**：$\bar{c}_x = -3, \bar{c}_y = -2$。选 $x$（最负）进基。

**最小比值**：

- $s_1$ 行：$100 / 2 = 50$
- $s_2$ 行：$80 / 1 = 80$
- $s_3$ 行：$40 / 1 = 40$ ← 最小

选 $s_3$ 离基，主元 $a_{31} = 1$。

**转轴**（以第 3 行第 1 列为主元）：

主元行归一化（主元已是 1）：

$$
x + s_3 = 40
$$

其他行消元：

- $s_1$ 行：$s_1 - 2 \cdot (x + s_3 = 40) \Rightarrow s_1 - 2 s_3 = 100 - 80 = 20$，即 $y + s_1 - 2 s_3 = 20$（保留 $y$）

  实际：原 $s_1$ 行 $2x + y + s_1 = 100$，减去 $2 \times$ 主元行 $2x + 2 s_3 = 80$，得 $y + s_1 - 2 s_3 = 20$。

- $s_2$ 行：原 $x + y + s_2 = 80$，减去 $1 \times$ 主元行 $x + s_3 = 40$，得 $y + s_2 - s_3 = 40$。

- $z$ 行：原 $z = -3x - 2y$，加上 $3 \times$ 主元行 $3x + 3 s_3 = 120$，得 $z + y + 3 s_3 = 120$，即 $z = -2y + 3 s_3 + 120$... 

  实际：$z - (-3) \cdot$ 主元行：$z + 3x + 3 s_3 = 120$，但 $z = -3x - 2y$，所以 $-2y + 3 s_3 = 120 - z$，即 $z = 120 + 2y - 3 s_3$... 

  让我重新算：检验行是 $z + 3x + 2y = 0$（把目标写成 $z - c^T x = 0$ 的形式，$c = (-3, -2, 0, 0, 0)$，所以 $z + 3x + 2y = 0$）。

  消元：$z$ 行减去 $(-3) \times$ 主元行 = $z$ 行 $+ 3 \times$ 主元行：
  $(z + 3x + 2y) + 3(x + s_3) = 0 + 3 \cdot 40$
  $z + 3x + 2y + 3x + 3 s_3 = 120$... 

  不对，应该是：$z$ 行的 $x$ 系数是 $-3$（检验数），要消成 0。$z$ 行减去 $(-3) \times$ 主元行：

  $z$ 行：$(z, -3, -2, 0, 0, 0, | 0)$
  主元行：$(0, 1, 0, 0, 0, 1, | 40)$（$x + s_3 = 40$）
  $z$ 行 $- (-3) \times$ 主元行 = $z$ 行 $+ 3 \times$ 主元行：
  $(z, -3+3, -2, 0, 0, 3, | 0+120) = (z, 0, -2, 0, 0, 3, | 120)$

  所以 $z - 2y + 3 s_3 = 120$，即 $z = 120 + 2y - 3 s_3$。

**迭代 1 后的表**：

$$
\begin{array}{c|ccccc|c}
  & x & y & s_1 & s_2 & s_3 & \text{RHS} \\
\hline
s_1 & 0 & 1 & 1 & 0 & -2 & 20 \\
s_2 & 0 & 1 & 0 & 1 & -1 & 40 \\
x   & 1 & 0 & 0 & 0 & 1  & 40 \\
\hline
z   & 0 & -2 & 0 & 0 & 3  & 120 \\
\end{array}
$$

当前解：$x = 40, y = 0, s_1 = 20, s_2 = 40, s_3 = 0$，目标 $z = 120$（即原问题 $-z = -120$，最大化值 $= 120$）。

### 迭代 2

**检验数**：$\bar{c}_y = -2 < 0$，$y$ 进基。

**最小比值**：

- $s_1$ 行：$20 / 1 = 20$ ← 最小
- $s_2$ 行：$40 / 1 = 40$
- $x$ 行：$y$ 系数是 0，跳过

选 $s_1$ 离基，主元 $a_{12} = 1$。

**转轴**（以第 1 行第 2 列为主元）：

主元行归一化（主元已是 1）：

$$
y + s_1 - 2 s_3 = 20
$$

其他行消元：

- $s_2$ 行：原 $y + s_2 - s_3 = 40$，减去 $1 \times$ 主元行 $y + s_1 - 2 s_3 = 20$，得 $s_2 - s_1 + s_3 = 20$。
- $x$ 行：$y$ 系数是 0，不变。
- $z$ 行：原 $z - 2y + 3 s_3 = 120$，减去 $(-2) \times$ 主元行 = $+ 2 \times$ 主元行：
  $(z - 2y + 3 s_3) + 2(y + s_1 - 2 s_3) = 120 + 40$
  $z + 2 s_1 - s_3 = 160$

**迭代 2 后的表**：

$$
\begin{array}{c|ccccc|c}
  & x & y & s_1 & s_2 & s_3 & \text{RHS} \\
\hline
y   & 0 & 1 & 1  & 0 & -1 & 20 \\
s_2 & 0 & 0 & -1 & 1 & 1  & 20 \\
x   & 1 & 0 & 0  & 0 & 1  & 40 \\
\hline
z   & 0 & 0 & 2  & 0 & 1  & 160 \\
\end{array}
$$

当前解：$x = 40, y = 20, s_1 = 0, s_2 = 20, s_3 = 0$，目标 $z = 160$。

### 检查最优性

检验数：$\bar{c}_{s_1} = 2 > 0$，$\bar{c}_{s_3} = 1 > 0$。所有非基变量检验数 $\geq 0$，**最优**！

最优解：$x = 40, y = 20$，最大目标值 $= -z = -(-160) = 160$... 

等等，让我重新检查。原问题是最大化 $3x + 2y$，转化为最小化 $-3x - 2y$。最小化问题的最优值是 $z = -160$，因此最大化的最优值是 $-z = 160$。

验证：$3 \cdot 40 + 2 \cdot 20 = 120 + 40 = 160$。✓

### 迭代轨迹

| 迭代 | 基 | $x$ | $y$ | 目标值 |
|------|----|-----|-----|--------|
| 0 | $\{s_1, s_2, s_3\}$ | 0 | 0 | 0 |
| 1 | $\{s_1, s_2, x\}$ | 40 | 0 | 120 |
| 2 | $\{y, s_2, x\}$ | 40 | 20 | 160 |

每步目标值递增，2 步达到最优。

---

## 在 minipulp 中的实现对照

minipulp 的 `SimplexCore` 实现了两阶段单纯形法。本节对照代码和算法。

### 整体流程

```python
class SimplexCore(LpSolver):
    def actualSolve(self, problem: LpProblem) -> LpStatus:
        if not problem.valid():
            raise ValueError("问题未设置目标函数")

        std = self._extract(problem)          # 1. 提取矩阵并标准化
        if std is None:
            return LpStatus.INFEASIBLE

        status, solution = self._solve(std)   # 2. 两阶段单纯形
        self._backfill(std, status, solution) # 3. 回填 varValue
        return status
```

### 1. 提取矩阵：`_extract`

```python
def _extract(self, problem: LpProblem) -> dict | None:
    var_list = problem.variables()
    n = len(var_list)
    var_index = {var: i for i, var in enumerate(var_list)}

    # 提取目标系数
    cost = [0.0] * n
    obj = problem.objective
    for var, coef in obj.terms.items():
        cost[var_index[var]] = float(coef)
    if problem.sense == LpSense.MAXIMIZE:
        cost = [-c for c in cost]    # max 转 min

    # 提取约束
    rows = []
    rhs = []
    senses = []
    for con in problem.constraints.values():
        row = [0.0] * n
        for var, coef in con.terms.items():
            row[var_index[var]] = float(coef)
        rows.append(row)
        rhs.append(float(-con.constant))    # 常数项移到右边
        senses.append(con.sense)

    # 变量平移（处理下界）
    shifts = [0.0] * n
    for i, var in enumerate(var_list):
        lb = var.lowBound
        if lb is not None:
            shifts[i] = float(lb)
            for r in range(len(rows)):
                rhs[r] -= rows[r][i] * shifts[i]

    # 上界作为额外约束
    for i, var in enumerate(var_list):
        ub = var.upBound
        if ub is not None:
            row = [0.0] * n
            row[i] = 1.0
            rows.append(row)
            rhs.append(float(ub) - shifts[i])
            senses.append(LpConstraintSense.LE)

    return {...}
```

关键步骤：

1. **max 转 min**：最大化目标取负。
2. **常数项移位**：`rhs = -con.constant`。
3. **变量平移**：$x' = x - lb \geq 0$，调整右端项。
4. **上界转约束**：$x \leq ub$ 变成额外行。

### 2. 构造单纯形表：`_build_tableau`

```python
def _build_tableau(self, rows, rhs, senses, n, m):
    A = [list(r) for r in rows]
    b = list(rhs)
    senses = list(senses)

    # 右端项非负化
    for i in range(m):
        if b[i] < -_EPS:
            for j in range(n):
                A[i][j] = -A[i][j]
            b[i] = -b[i]
            if senses[i] == LpConstraintSense.LE:
                senses[i] = LpConstraintSense.GE
            elif senses[i] == LpConstraintSense.GE:
                senses[i] = LpConstraintSense.LE

    n_total = n
    basis = [-1] * m
    artificial_cols = []

    for i in range(m):
        sense = senses[i]
        if sense == LpConstraintSense.LE:
            # 加松弛变量
            col = n_total
            for r in range(m):
                A[r].append(1.0 if r == i else 0.0)
            basis[i] = col
            n_total += 1
        elif sense == LpConstraintSense.GE:
            # 加剩余变量 + 人工变量
            col_surplus = n_total
            for r in range(m):
                A[r].append(-1.0 if r == i else 0.0)
            n_total += 1
            col_art = n_total
            for r in range(m):
                A[r].append(1.0 if r == i else 0.0)
            basis[i] = col_art
            artificial_cols.append(col_art)
            n_total += 1
        else:  # EQ
            # 加人工变量
            col_art = n_total
            for r in range(m):
                A[r].append(1.0 if r == i else 0.0)
            basis[i] = col_art
            artificial_cols.append(col_art)
            n_total += 1

    return A, b, basis, n_total, artificial_cols
```

关键步骤：

1. **右端项非负化**：$b_i < 0$ 时整行乘 $-1$，翻转约束方向。
2. **`<=` 约束**：加松弛变量（系数 +1），松弛变量进基。
3. **`>=` 约束**：加剩余变量（系数 -1）和人工变量（系数 +1），人工变量进基。
4. **`==` 约束**：加人工变量（系数 +1），人工变量进基。

### 3. 单纯形主循环：`_simplex_loop`

```python
def _simplex_loop(self, A, b, cost, basis, n_total, m):
    max_iter = 10000
    for _ in range(max_iter):
        c_basis = [cost[basis[i]] for i in range(m)]

        # 1. 算检验数，选进基列（Bland 规则）
        pivot_col = -1
        for j in range(n_total):
            reduced = cost[j] - sum(c_basis[i] * A[i][j] for i in range(m))
            if reduced < -_EPS:
                pivot_col = j
                break
        if pivot_col == -1:
            return LpStatus.OPTIMAL    # 所有检验数 >= 0，最优

        # 2. 最小比值测试，选离基行
        pivot_row = -1
        min_ratio = math.inf
        for i in range(m):
            if A[i][pivot_col] > _EPS:
                ratio = b[i] / A[i][pivot_col]
                if ratio < min_ratio - _EPS:
                    min_ratio = ratio
                    pivot_row = i
        if pivot_row == -1:
            return LpStatus.UNBOUNDED   # 无正系数，无界

        # 3. 转轴
        self._pivot(A, b, pivot_row, pivot_col, m, n_total)
        basis[pivot_row] = pivot_col

    return LpStatus.UNDEFINED
```

每步迭代：

1. **检验数**：$\bar{c}_j = c_j - c_B^T A_j$。
2. **进基**：第一个 $\bar{c}_j < 0$（Bland 规则）。
3. **离基**：最小比值 $b_i / A_{ij}$（$A_{ij} > 0$）。
4. **无界检测**：无 $A_{ij} > 0$ 则无界。
5. **转轴**：高斯消元。

### 4. 转轴：`_pivot`

```python
def _pivot(self, A, b, pr, pc, m, n_total):
    pivot_val = A[pr][pc]
    # 主元行归一化
    for j in range(n_total):
        A[pr][j] /= pivot_val
    b[pr] /= pivot_val

    # 其他行消元
    for i in range(m):
        if i == pr:
            continue
        factor = A[i][pc]
        if _is_zero(factor):
            continue
        for j in range(n_total):
            A[i][j] -= factor * A[pr][j]
        b[i] -= factor * b[pr]
```

1. **归一化**：主元行除以主元值。
2. **消元**：每行减去 `factor` 倍的主元行，`factor = A[i][pc]`。

### 5. 两阶段法：`_solve`

```python
def _solve(self, std):
    ...
    A, b, basis, n_total, artificial_cols = self._build_tableau(...)

    if artificial_cols:
        # 阶段一：min Σ a_i
        phase1_cost = [0.0] * n_total
        for j in artificial_cols:
            phase1_cost[j] = 1.0

        status = self._simplex_loop(A, b, phase1_cost, basis, n_total, m)
        if status != LpStatus.OPTIMAL:
            return status, [0.0] * n

        # 检查人工变量是否全为 0
        art_value = sum(b[i] for i in range(m) if basis[i] in artificial_cols)
        if art_value > _EPS:
            return LpStatus.INFEASIBLE, [0.0] * n    # 不可行

        # 驱赶基中的人工变量
        art_set = set(artificial_cols)
        for i in range(m):
            if basis[i] in art_set:
                for j in range(n_total):
                    if j in art_set:
                        continue
                    if abs(A[i][j]) > _EPS:
                        self._pivot(A, b, i, j, m, n_total)
                        basis[i] = j
                        break

        # 清除人工变量列
        for j in artificial_cols:
            for i in range(m):
                A[i][j] = 0.0

    # 阶段二：min c^T x
    full_cost = [0.0] * n_total
    for j in range(n):
        full_cost[j] = cost[j]

    status = self._simplex_loop(A, b, full_cost, basis, n_total, m)
    if status != LpStatus.OPTIMAL:
        return status, [0.0] * n

    # 提取解
    solution = [0.0] * n_total
    for i in range(m):
        solution[basis[i]] = b[i]
    return status, solution[:n]
```

### 6. 回填：`_backfill`

```python
def _backfill(self, std, status, solution):
    var_list = std["var_list"]
    shifts = std["shifts"]

    if status != LpStatus.OPTIMAL:
        for var in var_list:
            var.varValue = None
        return

    for i, var in enumerate(var_list):
        var.varValue = solution[i] + shifts[i]    # 加回平移量
```

解值加回平移量：$x = x' + \text{shift} = x' + lb$。

---

## 复杂度分析

### 最坏情况

单纯形法的最坏复杂度是**指数级**的。Klee 和 Minty (1972) 构造了一个例子，单纯形法访问所有 $\binom{n}{m} \approx 2^n$ 个顶点。

### 实际情况

实践中，单纯形法通常在 $O(n)$ 到 $O(n \log n)$ 步内终止。这被称为"平滑复杂度"——虽然最坏指数，但平均多项式。

### 影响复杂度的因素

1. **退化程度**：退化转轴不推进算法，拖慢迭代。
2. **问题规模**：变量数 $n$ 和约束数 $m$ 越大，每步迭代越慢（$O(mn)$）。
3. **选择规则**：Dantzig 规则通常比 Bland 规则快，但可能循环。
4. **问题结构**：某些问题结构（如网络流）有专门的高效算法。

### minipulp 的性能

minipulp 的 `SimplexCore` 是教学实现，适合小规模问题（$n, m < 100$）。大规模问题应用 CBC/GLPK 等生产求解器，它们有：

- 稀疏矩阵存储（不存零元素）。
- LU 分解更新（不每次重新求逆）。
- Steepest edge 规则（比 Dantzig 更稳定）。
- 预求解（消除冗余约束和固定变量）。

---

## 与其他算法的比较

### 单纯形法 vs 内点法

| 特性 | 单纯形法 | 内点法 |
|------|---------|--------|
| 路径 | 沿边走（顶点到顶点） | 穿过内部 |
| 解 | 顶点解（基本可行解） | 内部解（可能非顶点） |
| 复杂度 | 最坏指数，平均多项式 | 多项式 |
| 退化 | 敏感 | 不敏感 |
| 热启动 | 支持 | 不支持 |
| 实践 | 通常快 | 大问题快 |

### 单纯形法 vs 对偶单纯形法

对偶单纯形法在对偶问题上运行单纯形法。它在以下情况有优势：

1. **预求解后**：预求解可能让对偶可行但原始不可行，对偶单纯形法直接开始。
2. **割平面法**：添加割平面后对偶可行，对偶单纯形法高效。
3. **分支定界**：分支后对偶可行，对偶单纯形法热启动。

### 单纯形法 vs 椭球法

椭球法（Khachiyan, 1979）是第一个多项式时间 LP 算法，但实践中比单纯形法慢得多。它的意义是理论上的——证明 LP 多项式可解。

---

## 单纯形法的变体

### 修订单纯形法

修订单纯形法（revised simplex）不维护整个单纯形表，只维护基矩阵的 LU 分解。每步迭代：

1. 解 $B^T y = c_B$ 得对偶变量 $y$。
2. 算检验数 $\bar{c}_j = c_j - y^T A_j$。
3. 解 $B d = A_j$ 得转轴方向 $d$。
4. 最小比值测试。
5. 更新 LU 分解（rank-1 更新）。

优点：稀疏矩阵高效，内存占用小。生产求解器都用修订单纯形法。

### 对偶单纯形法

在对偶问题上运行单纯形法。保持对偶可行（$\bar{c} \geq 0$），逐步达到原始可行（$\bar{b} \geq 0$）。

### 原始对偶单纯形法

结合原始和对偶信息，同时追求原始可行和对偶可行。

---

## 单纯形法的数值稳定性

### 病态问题

某些问题的基矩阵 $B$ 条件数很大，导致 $B^{-1}$ 计算误差大。这会让单纯形法数值不稳定。

### 处理方法

1. **LU 分解 + 列主元**：比直接求逆稳定。
2. **缩放**：把矩阵的行和列缩放到相近量级。
3. **精度控制**：用 `_EPS` 判断零，避免浮点噪声。
4. **基重算**：定期重新计算 LU 分解，清除误差累积。

### minipulp 的处理

minipulp 用 `_EPS = 1e-9` 判断零，不做缩放或基重算。对于教学目的足够，但大规模或病态问题可能不准。

---

## 单纯形法的几何解读

### 顶点跳跃

单纯形法在多面体的顶点间跳跃。每步跳跃：

1. **沿边移动**：从一个顶点沿一条边移动。
2. **到达下一个顶点**：边碰到另一个约束，到达新顶点。
3. **目标下降**：每步目标值下降（非退化情况）。

### 检验数的几何意义

检验数 $\bar{c}_j$ 是目标函数沿第 $j$ 条边的方向导数。$\bar{c}_j < 0$ 表示这条边方向目标下降，应该沿这条边走。

### 最小比值的几何意义

最小比值测试确定沿边走多远——走到边的另一端（碰到下一个约束）。如果可以无限走（边无界），问题无界。

### 退化的几何意义

退化顶点由多于 $n$ 个约束相交。单纯形法可能在这个顶点"原地转圈"（基变了但顶点没变），这就是循环。

---

## 单纯形法的代数解读

### 基变换

每次转轴是一次基变换：一个变量进基，一个变量离基。新基矩阵 $B'$ 是旧基 $B$ 替换一列。

### 检验数的代数意义

检验数 $\bar{c}_j = c_j - c_B^T B^{-1} A_j$ 是目标函数在当前基下的"非正交分量"。$\bar{c}_j = 0$ 表示 $A_j$ 在 $c_B$ 张成的空间中。

### 最优性的代数条件

所有 $\bar{c}_j \geq 0$ 等价于 $c_N \geq c_B^T B^{-1} N$，即 $c \geq A^T y$（$y = c_B^T B^{-1}$ 是对偶变量）。这正是对偶可行条件。

### 互补松弛

最优时，$x_j \cdot \bar{c}_j = 0$ 对所有 $j$。即：

- 基变量 $x_j > 0$（非退化时），$\bar{c}_j = 0$。
- 非基变量 $x_j = 0$，$\bar{c}_j \geq 0$。

这是 KKT 条件中的互补松弛。

---

## 对偶视角

### 对偶问题

原问题 $\min c^T x$ s.t. $Ax = b, x \geq 0$ 的对偶：

$$
\max b^T y \quad \text{s.t.} \quad A^T y \leq c
$$

### 强对偶定理

若原问题有最优解 $x^*$，对偶有最优解 $y^*$，且 $c^T x^* = b^T y^*$。

### 单纯形法求解对偶

单纯形法在求原问题最优的同时，也得到对偶最优解 $y = c_B^T B^{-1}$。检验数 $\bar{c}_j = c_j - A_j^T y$ 是对偶约束的松弛量。

### 互补松弛的验证

最优时：

- 原始可行：$Ax^* = b, x^* \geq 0$。
- 对偶可行：$A^T y^* \leq c$（即 $\bar{c} \geq 0$）。
- 互补松弛：$x_j^* \cdot \bar{c}_j = 0$。

---

## 单纯形法的历史

### Dantzig 的贡献

George Dantzig 于 1947 年发明单纯形法。他的洞察是：

1. 线性规划的最优解在顶点。
2. 顶点对应基本可行解。
3. 可以通过基变换在顶点间移动。

### 早期应用

单纯形法在二战期间用于军事规划（运输、调度）。战后广泛应用于工业、经济、管理。

### 理论发展

- **Klee-Minty (1972)**：构造指数最坏例子。
- **Khachiyan (1979)**：椭球法，多项式时间。
- **Karmarkar (1984)**：内点法，实用多项式时间。

### 现代发展

- **修订单纯形法**：稀疏高效实现。
- **对偶单纯形法**：预求解和分支定界的核心。
- **热启动**：从上次解开始，加速求解。

---

## 单纯形法的教学价值

### 为什么学单纯形法

1. **直觉清晰**：顶点跳跃的几何图像易于理解。
2. **理论完整**：最优性、对偶、互补松弛都有清晰形式。
3. **实践重要**：生产求解器仍以单纯形法为主。
4. **基础**：理解整数规划（分支定界）和内点法的基础。

### minipulp 的教学定位

minipulp 的 `SimplexCore` 用最透明的 Python 实现单纯形法：

1. **零依赖**：不用 numpy，只用原生 list。
2. **代码透明**：每步操作都可见，可逐步跟踪。
3. **对照算法**：代码结构与算法步骤一一对应。

---

## 调试单纯形法

### 打印单纯形表

每步迭代打印单纯形表，检查：

1. 基变量正确。
2. 右端项非负。
3. 检验数计算正确。
4. 转轴后表正确。

### 检查最优性

最优时验证：

1. 所有检验数 $\geq 0$。
2. 原始可行：$Ax = b, x \geq 0$。
3. 对偶可行：$A^T y \leq c$。
4. 互补松弛：$x_j \cdot \bar{c}_j = 0$。

### 检查不可行

阶段一最优值 $> 0$ 时，验证人工变量确实无法驱赶到 0。

### 检查无界

无界检测时，验证进基列所有系数 $\leq 0$，且目标确实可以无限下降。

---

## 单纯形法的常见陷阱

### 1. 浮点精度

```python
if reduced < -_EPS:    # 而不是 if reduced < 0
```

浮点运算可能产生 $10^{-16}$ 的噪声，用 `_EPS` 避免误判。

### 2. 退化循环

不用 Bland 规则可能循环。minipulp 用 Bland 规则保证终止。

### 3. 右端项负

```python
if b[i] < -_EPS:
    # 整行乘 -1
```

右端项必须非负，负的整行翻转。

### 4. 人工变量残留

阶段一后必须驱赶基中的人工变量，否则阶段二会出错。

### 5. 解的回填

```python
var.varValue = solution[i] + shifts[i]    # 别忘了加平移量
```

变量平移后，解值要加回下界。

---

## 单纯形法的扩展

### 有界变量单纯形法

变量有上下界 $l \leq x \leq u$ 时，不用把上界转成约束，而是直接处理。这减少约束数，提高效率。

### 网络单纯形法

网络流问题的基矩阵是全单位模的，单纯形法可以整数运算，无浮点误差。这是最高效的网络流算法。

### 大 M 法

替代两阶段法，用大常数 $M$ 惩罚人工变量：$\min c^T x + M \sum a_i$。简单但数值不稳定（$M$ 太大导致浮点问题）。minipulp 用两阶段法而非大 M 法。

---

## 总结

单纯形法是线性规划的经典算法，核心思想是**在多面体顶点间跳跃，沿目标下降的方向移动，直到最优**。

### 核心概念

1. **标准形式**：$\min c^T x$ s.t. $Ax = b, x \geq 0$。
2. **基本可行解**：令非基变量为 0，解基变量，对应顶点。
3. **检验数**：$\bar{c}_j = c_j - c_B^T B^{-1} A_j$，指示改进方向。
4. **最优性**：所有 $\bar{c}_j \geq 0$ 时最优。
5. **转轴**：进基（选 $\bar{c}_j < 0$）、离基（最小比值）、高斯消元。
6. **两阶段法**：阶段一求可行基，阶段二求最优。
7. **Bland 规则**：避免循环。

### minipulp 的实现

minipulp 的 `SimplexCore` 用纯 Python 实现两阶段单纯形法，代码透明，适合教学。核心方法：

- `_extract`：提取矩阵并标准化。
- `_build_tableau`：构造单纯形表。
- `_simplex_loop`：主循环（检验数、进基、离基、转轴）。
- `_pivot`：高斯消元。
- `_backfill`：回填解值。

理解单纯形法，就理解了线性规划求解的核心。

---

## 后记：从单纯形法到现代求解器

单纯形法虽然古老（1947 年），但至今仍是生产求解器的核心。现代求解器（CBC、Gurobi、CPLEX）在单纯形法基础上添加：

1. **预求解**：消除冗余约束、固定变量、缩放。
2. **稀疏矩阵**：只存非零元素，高效。
3. **LU 分解**：不每次重新求逆，rank-1 更新。
4. **对偶单纯形法**：处理预求解和分支定界。
5. **热启动**：从上次解开始，加速。
6. **并行化**：多线程处理分支定界。

但核心思想不变——在顶点间跳跃，沿目标下降方向移动。理解单纯形法，就理解了这些现代求解器的基础。

---

## 参考阅读

- **Dantzig, G. B. (1963)**：*Linear Programming and Extensions*，单纯形法的奠基之作。
- **Chvátal, V. (1983)**：*Linear Programming*，经典教材，对单纯形法和对偶理论的清晰讲解。
- **Bland, R. G. (1977)**："New finite pivoting rules for the simplex method"，Bland 规则的原始论文。
- **Klee, V. & Minty, G. (1972)**："How good is the simplex algorithm?"，指数最坏例子。
- **Bertsimas, D. & Tsitsiklis, J. (1997)**：*Introduction to Linear Optimization*，现代教材，涵盖单纯形法、对偶、内点法。

---

> **核心要点**：单纯形法在多面体顶点间跳跃，每步通过转轴操作（基变换）沿目标下降方向移动。检验数指示改进方向，最小比值测试保证可行性，Bland 规则避免循环。两阶段法处理一般问题：阶段一求可行基，阶段二求最优。理解这些，就理解了 minipulp 的 `SimplexCore`。
