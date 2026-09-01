# 四大设计原则

> PuLP 能成为 Python 生态最流行的线性规划建模库，靠的不是功能最多，而是设计最清晰。本项目复刻其核心，提炼出四大设计原则。理解这四点，就理解了 PuLP 90% 的设计哲学。

---

## 目录

- [原则一：建模与求解分离](#原则一建模与求解分离)
- [原则二：代数表达式即代码](#原则二代数表达式即代码)
- [原则三：仿射表达式的闭包性](#原则三仿射表达式的闭包性)
- [原则四：多后端可插拔](#原则四多后端可插拔)
- [四原则的关系](#四原则的关系)
- [与其他建模库的对比](#与其他建模库的对比)
- [设计模式视角](#设计模式视角)
- [工程实践启示](#工程实践启示)
- [历史背景](#历史背景)
- [工业应用案例](#工业应用案例)
- [教学价值讨论](#教学价值讨论)
- [从 minipulp 到 PuLP 的迁移指南](#从-minipulp-到-pulp-的迁移指南)

---

## 原则一：建模与求解分离

**问题描述和求解算法是两个独立的世界，通过文件格式通信。**

### 两层架构

线性规划的工作流天然分两层：

```
建模层（人类关心什么）          求解层（机器怎么算）
┌─────────────────┐           ┌─────────────────┐
│  LpProblem      │  LP 文件  │  LpSolver       │
│  - 变量         │ ───────→ │  - 单纯形法     │
│  - 约束         │           │  - 分支定界     │
│  - 目标         │ ←─────── │  - 内点法       │
│  - 解值         │  .sol 文件│                 │
└─────────────────┘           └─────────────────┘
    minipulp                     CBC / GLPK / ...
```

### 为什么分离？

1. **解耦**：建模代码不依赖具体求解器，换求解器只换一个参数。
2. **生态**：OR（运筹学）社区有成熟的文件格式标准（LP、MPS），任何求解器都能读写。
3. **可替换**：同一模型可送不同求解器对比性能，无需改建模代码。
4. **可测试**：建模层和求解层可以独立测试，互不影响。
5. **可复用**：同一个模型可以用于不同的应用场景（求解、灵敏度分析、对偶分析等）。

### 在 minipulp 中的体现

```python
# 建模层——完全不知道求解器的存在
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

# 求解层——同一模型，不同求解器，零修改
prob.solve(solver=SimplexCore())    # 纯 Python 单纯形法
prob.solve(solver=SimplexCpp())     # C++ 单纯形法
prob.solve(solver=PULP_CBC_CMD())   # CBC 工业求解器
prob.solve()                        # 默认求解器（自动选择）
```

`LpProblem` 完全不知道求解器内部如何工作，`LpSolver` 也完全不关心模型怎么建的。二者在 `solve()` 方法中短暂交汇，通过 LP 文件格式交换信息。

### 接口设计

```python
class LpSolver:
    """求解器抽象基类。"""
    def available(self) -> bool: ...
    def actualSolve(self, problem: LpProblem) -> LpStatus: ...

class LpProblem:
    """问题容器。"""
    def solve(self, solver: LpSolver = None) -> LpStatus:
        if solver is None:
            solver = _get_default_solver()
        self.status = solver.solve(self)
        return self.status
```

`LpProblem.solve()` 只依赖 `LpSolver` 接口，不依赖任何具体实现。这是**依赖倒置原则**的体现。

### 文件格式作为通信协议

```
LpProblem → write_lp() → model.lp → cbc → model.sol → parse_sol() → varValue
```

LP 格式是 CPLEX 定义的人类可读文本格式，是 OR 生态的"通用语言"。
任何建模库都能写 LP 文件，任何求解器都能读 LP 文件。
这种标准化接口使得组件之间可以自由组合。

#### LP 文件格式示例

一个简单的线性规划问题：

$$
\max \quad 3x + 2y \\
\text{s.t.} \quad 2x + y \le 100 \\
\quad x + y \le 80 \\
\quad x \le 40 \\
\quad x, y \ge 0
$$

对应的 LP 文件：

```
\ Problem: demo
Maximize
  obj: 3 x + 2 y
Subject To
  c1: 2 x + 1 y <= 100
  c2: 1 x + 1 y <= 80
  c3: 1 x <= 40
Bounds
  x >= 0
  y >= 0
End
```

#### MPS 文件格式对比

MPS（Mathematical Programming System）是更古老、更紧凑的格式，由 IBM 在 1960 年代定义：

```
NAME          demo
ROWS
 N  obj
 L  c1
 L  c2
 L  c3
COLUMNS
    x   obj   3.0   c1   2.0
    x   c2    1.0   c3   1.0
    y   obj   2.0   c1   1.0
    y   c2    1.0
RHS
    rhs c1    100.0 c2   80.0
    rhs c3    40.0
ENDATA
```

| 特性 | LP 格式 | MPS 格式 |
|------|---------|----------|
| 可读性 | 人类可读 | 机器可读 |
| 历史 | CPLEX 定义 | IBM 定义（1960s） |
| 体积 | 较大 | 较紧凑 |
| 列导向 | 否 | 是 |
| 默认边界 | 需显式写 | 0 ≤ x ≤ ∞ |

### 对比：紧耦合设计

有些建模库将求解器嵌入建模对象：

```python
# 紧耦合设计（不好）
prob = Problem(solver="cbc")  # 求解器在构造时就绑死
prob.solve()  # 无法换求解器
```

这种设计的问题：

- 换求解器需要重新构造问题
- 求解器的依赖污染了建模层
- 无法用同一模型对比不同求解器

### 分离原则的深层价值

分离不仅是为了"能换求解器"，更深层价值在于：

1. **关注点分离**（Separation of Concerns）：建模者关心业务逻辑，求解器开发者关心算法效率，两者各司其职。
2. **独立演进**：建模 API 可以重新设计而不影响求解器；求解器可以升级算法而不影响建模代码。
3. **并行开发**：团队可以分头工作——业务专家建模型，算法专家写求解器。
4. **测试隔离**：建模层的测试不需要真正求解（只验证模型结构）；求解器的测试不需要业务模型（用随机矩阵）。
5. **部署灵活性**：建模代码可以在浏览器中运行（如 Pyodide），求解器在远程服务器上，通过文件传输通信。

```python
# 测试建模层——不需要求解器
def test_model_construction():
    prob = mp.LpProblem("test", mp.LpMaximize)
    prob += 3 * x + 2 * y
    prob += 2 * x + y <= 100
    assert len(prob.constraints) == 1
    assert prob.objective.terms[x] == 3.0

# 测试求解器——不需要业务模型
def test_simplex_solver():
    prob = build_random_lp(n_vars=10, n_constraints=20)
    status = SimplexCore().solve(prob)
    assert status == mp.LpStatusOptimal
```

---

## 原则二：代数表达式即代码

**用运算符重载让数学公式直接变成可执行代码，无需字符串解析。**

### 传统方式 vs PuLP 方式

传统建模库用字符串描述模型：

```python
# 传统方式（笨拙）
solver = Solver()
solver.add_variable("x")
solver.add_variable("y")
solver.add_constraint("2*x + y <= 100")  # 字符串，需解析
solver.set_objective("max 3*x + 2*y")
```

问题：

1. **字符串是黑盒**：IDE 无法检查语法错误
2. **解析开销**：每次调用都要解析字符串
3. **不直观**：和数学公式差距大
4. **无类型安全**：变量名拼写错误不会报错

PuLP 用 Python 运算符重载，让代码读起来就是数学公式：

```python
# PuLP 方式（优雅）
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
prob += 3 * x + 2 * y          # 这就是数学公式
prob += 2 * x + y <= 100       # 这也是数学公式
```

优势：

1. **IDE 友好**：语法错误在编辑时就能发现
2. **零解析开销**：运算符直接构造对象
3. **直观**：代码 ≈ 数学公式
4. **类型安全**：变量是对象，拼错名字会 AttributeError

### 背后的机制

`2 * x` 触发 `x.__rmul__(2)`，返回一个 `LpAffineExpression({x: 2})` 对象。
`2*x + y` 触发 `__add__`，合并字典得到 `{x: 2, y: 1}`。
`<= 100` 触发 `__le__`，构造 `LpConstraint`。

每一步都在构造对象，而非做数值计算。详见 [运算符重载机制](operator-overloading.md)。

### 运算符重载的调用链

```python
# 3 * x + 2 * y <= 100 的完整调用链：
#
# 步骤 1: 3 * x
#   int.__mul__(3, x) → NotImplemented
#   x.__rmul__(3) → LpAffineExpression({x: 3.0})
#
# 步骤 2: 2 * y
#   int.__mul__(2, y) → NotImplemented
#   y.__rmul__(2) → LpAffineExpression({y: 2.0})
#
# 步骤 3: (3*x) + (2*y)
#   LpAffineExpression.__add__({x:3}, {y:2})
#   → LpAffineExpression({x:3, y:2})
#
# 步骤 4: (3*x+2*y) <= 100
#   LpElement.__le__(LpAffineExpression, 100)
#   → LpConstraint(lhs={x:3, y:2, const:-100}, sense=LE)
```

### 为什么不用字符串？

字符串解析的致命缺陷：

```python
# 字符串方式的问题
solver.add_constraint("2*x + y <= 100")  # x 未定义？拼写错误？
solver.add_constraint("2*x + y <= 100")  # 重复添加？
solver.add_constraint("2*x + y <= 1OO")  # O 不是 0，但字符串不报错
```

运算符重载方式：

```python
# 运算符方式的优势
x = mp.LpVariable("x")
prob += 2 * x + y <= 100  # y 未定义 → NameError，立即报错
prob += 2 * x + y <= 1OO  # O 不是 0 → NameError
```

### 运算符重载的历史渊源

运算符重载并非 Python 发明。其历史可以追溯到：

- **C++（1985）**：`operator+`、`operator*` 等成员函数，被科学计算库（如 Eigen、Blitz++）广泛使用。
- **Fortran（1957）**：天然支持数学符号，无需"重载"——运算符就是数学运算。
- **ALGOL 68（1968）**：第一个显式支持运算符定义的语言。
- **Smalltalk（1972）**：一切都是对象，运算符就是消息传递。
- **Python（1991）**：`__add__`、`__mul__` 等双下方法，借鉴了 Smalltalk 的消息传递思想。

Python 的贡献在于将运算符重载做到了**足够简单且足够安全**——简单到 NumPy、PuLP 这样的库能广泛使用，安全到不会像 C++ 那样产生意外的隐式转换。

### 与其他语言的对比

| 语言 | 运算符重载方式 | LP 建模库 |
|------|-------------|----------|
| Python | `__add__` 等双下方法 | PuLP, Pyomo, CVXPY |
| C++ | `operator+` 成员函数 | OR-Tools (C++ API) |
| Java | 不支持运算符重载 | 无直接支持，用链式 API |
| Julia | 多重派发 | JuMP.jl |
| Rust | trait + impl | good_lp |
| MATLAB | 运算符即函数 | YALMIP |

Julia 的 JuMP.jl 是一个特别有趣的对比——它利用 Julia 的多重派发实现了比 Python 更灵活的运算符重载：

```julia
# JuMP.jl (Julia)
model = Model(HiGHS.Optimizer)
@variable(model, x >= 0)
@variable(model, y >= 0)
@objective(model, Max, 3x + 2y)
@constraint(model, 2x + y <= 100)
optimize!(model)
```

JuMP 用宏（macro）而非运算符重载来构造模型，这避免了 Python 中 `__eq__` 的陷阱，但也牺牲了部分灵活性。

---

## 原则三：仿射表达式的闭包性

**变量的任意线性组合仍是仿射表达式，一个 `{var: coef}` 字典就够了。**

这是整个库能用极简代码表示任意线性表达式的数学根因。

### 数学定义

仿射表达式形如 $f(x) = c_1 x_1 + c_2 x_2 + \cdots + c_n x_n + b$。

关键性质（闭包性）：

$$
\alpha \cdot f(x) + \beta \cdot g(x) = \text{仍是仿射表达式}
$$

### 推论

因此：

- 变量 $x$ 是仿射表达式（$1 \cdot x + 0$）
- $3x$ 是仿射表达式（$3 \cdot x + 0$）
- $3x + 2y$ 是仿射表达式（$3 \cdot x + 2 \cdot y + 0$）
- $3x + 2y + 5$ 是仿射表达式（$3 \cdot x + 2 \cdot y + 5$）
- $2(3x + 2y) = 6x + 4y$ 是仿射表达式

### 闭包性的形式化证明

设 $f(x) = \mathbf{a}^T \mathbf{x} + b$ 和 $g(x) = \mathbf{c}^T \mathbf{x} + d$ 是两个仿射表达式，$\alpha, \beta$ 是标量。

$$
\alpha f(x) + \beta g(x) = \alpha(\mathbf{a}^T \mathbf{x} + b) + \beta(\mathbf{c}^T \mathbf{x} + d)
$$

$$
= (\alpha \mathbf{a} + \beta \mathbf{c})^T \mathbf{x} + (\alpha b + \beta d)
$$

$$
= \mathbf{e}^T \mathbf{x} + f \quad \text{（仍是仿射表达式）}
$$

其中 $\mathbf{e} = \alpha \mathbf{a} + \beta \mathbf{c}$，$f = \alpha b + \beta d$。

**证毕。** 仿射函数在加法和标量乘法下封闭，构成一个向量空间。

### 为什么不需要表达式树？

**无需表达式树**——不需要 AST、不需要递归求值，一个扁平字典 `{x: 3, y: 2}` 加一个常数 `5` 就完整表示了。

对比：如果允许非线性（如 $x \cdot y$），就必须用表达式树，因为 $x \cdot y$ 不是仿射表达式，闭包性被破坏。这正是线性规划"线性"二字的价值。

```
线性规划（闭包性成立）          非线性规划（闭包性破坏）
{x: 3, y: 2}, const=5           表达式树：
一个字典就够了                       +
                                   / \
                                 *   2
                                / \
                               x   y
需要递归遍历
```

### 闭包性 vs 其他代数结构

| 代数结构 | 封闭运算 | 表示方式 | 复杂度 |
|---------|---------|---------|--------|
| 仿射表达式 | 加法、标量乘 | 扁平字典 | $O(n)$ |
| 多项式 | 加法、乘法 | 系数列表 | $O(n^d)$ |
| 有理函数 | 加法、乘法、除法 | 表达式树 | $O(\text{树大小})$ |
| 任意非线性 | 所有运算 | AST | $O(\text{树大小})$ |

闭包性越弱，表示越复杂。线性规划恰好处于"闭包性足够强"的甜点。

### 在 minipulp 中的体现

```python
class LpAffineExpression:
    def __init__(self, terms: dict, const: float = 0):
        self.terms = terms    # {LpVariable: coef}
        self.const = const    # 常数项
```

运算符重载就是字典合并：

```python
def __add__(self, other):
    merged = dict(self.terms)
    for var, coef in other.terms.items():
        merged[var] = merged.get(var, 0) + coef  # 系数相加
    return LpAffineExpression(merged, self.const + other.const)
```

没有树，没有递归，没有 AST。一个字典合并操作就是全部。

详见 [仿射表达式闭包性](affine-closure.md)。

### 闭包性的工程意义

闭包性不仅是数学优美，更有直接工程价值：

1. **内存效率**：一个字典 vs 一棵树，内存占用差 5-10 倍。
2. **速度**：字典合并 $O(n)$ vs 树遍历 $O(n \log n)$ 或更差。
3. **简化求解器**：求解器只需读字典，无需递归求值表达式树。
4. **规范化**：所有表达式都是同一格式，无需"化简"步骤。

```python
# 闭包性的直接体现：无论多复杂的表达式，最终都是一个字典
expr = 3 * x + 2 * y - 5 * z + 10
# expr.terms = {x: 3.0, y: 2.0, z: -5.0}
# expr.const = 10.0
# 就这么简单——没有嵌套，没有树
```

---

## 原则四：多后端可插拔

**求解器是一组同接口的子类，换后端只换一个参数。**

### 求解器层次

所有求解器继承 `LpSolver`，实现同一个接口：

```python
class LpSolver:
    def available(self) -> bool: ...      # 求解器是否可用
    def actualSolve(self, problem) -> LpStatus: ...  # 实际求解
```

minipulp 的三层求解器：

| 层级 | 求解器 | 教学要点 | 性能 |
|------|--------|----------|------|
| L0 | `SimplexCore` | 纯 Python 单纯形法，代码透明 | 基准 |
| L1 | `SimplexCpp` | C++ + pybind11，Python/C++ 分工 | 10-50x |
| L2 | `PULP_CBC_CMD` | CBC 命令行对接，工业级通信范式 | 工业级 |

```python
prob.solve(solver=SimplexCore())      # L0：教学，透明
prob.solve(solver=SimplexCpp())       # L1：性能加速
prob.solve(solver=PULP_CBC_CMD())     # L2：工业，高效
```

### 为什么可插拔？

因为 `LpProblem.solve()` 只依赖 `LpSolver` 接口，不依赖具体实现。这是面向对象设计中的"依赖倒置"——高层模块不依赖低层模块，二者都依赖抽象。

```python
class LpProblem:
    def solve(self, solver: LpSolver = None) -> LpStatus:
        if solver is None:
            solver = _get_default_solver()  # 自动选择最优可用
        self.status = solver.solve(self)
        return self.status
```

### 默认求解器选择

```python
def _get_default_solver():
    """优先级：SimplexCpp → SimplexCore。"""
    from .solvers import SimplexCpp, SimplexCore
    cpp = SimplexCpp()
    if cpp.available():
        return cpp      # C++ 扩展已编译 → 用快的
    return SimplexCore()  # 否则回退纯 Python
```

**零配置**：用户无需关心用哪个求解器——有 C++ 就用快的，没有就用纯 Python。

### 添加新求解器

只需继承 `LpSolver` 并实现两个方法：

```python
class MySolver(LpSolver):
    name = "MySolver"

    def available(self) -> bool:
        # 检查求解器是否可用
        ...

    def actualSolve(self, problem: LpProblem) -> LpStatus:
        # 1. 从 problem 提取矩阵
        # 2. 调用求解器
        # 3. 回填 varValue
        ...

# 使用
prob.solve(solver=MySolver())
```

无需修改 `LpProblem` 或任何其他代码——这就是开闭原则（对扩展开放，对修改关闭）。

### 求解器生态系统

真实的 LP 求解器生态极其丰富，minipulp 的可插拔设计让接入新求解器非常容易：

| 求解器 | 类型 | 开源 | 特点 |
|--------|------|------|------|
| CBC | 单纯形+分支定界 | 是 | COIN-OR 项目，PuLP 默认 |
| GLPK | 单纯形+内点 | 是 | GNU 项目，轻量 |
| HiGHS | 单纯形+内点 | 是 | 高性能，新一代 |
| CPLEX | 单纯形+内点 | 否 | IBM 商业，工业标杆 |
| Gurobi | 单纯形+内点 | 否 | 商业，公认最快 |
| Xpress | 单纯形+内点 | 否 | FICO 商业 |
| SCIP | 分支定界 | 是 | Zuse Institute Berlin |
| OR-Tools | CP/LP/MIP | 是 | Google |

```python
# 理论上，接入任何求解器都只需实现两个方法
class HiGHSSolver(LpSolver):
    def available(self):
        return shutil.which("highs") is not None

    def actualSolve(self, problem):
        problem.writeLP("temp.lp")
        subprocess.run(["highs", "--model_file", "temp.lp",
                        "--solution_file", "temp.sol"])
        self._parse_solution(problem, "temp.sol")
        return LpStatusOptimal
```

---

## 四原则的关系

```
原则一（分离）─── 原则四（可插拔）
    │                    │
    │  LP 文件           │  同接口
    │                    │
原则二（代数即代码）── 原则三（闭包性）
    │                    │
    │  运算符重载         │  字典表示
    └────────────────────┘
```

- 原则一、四 是**架构层面**的分离（建模 vs 求解）
- 原则二、三 是**实现层面**的技巧（运算符重载 + 字典表示）
- 原则二依赖原则三：正因为闭包性，运算符重载的结果才能用字典表示
- 原则一依赖原则二：正因为代数即代码，建模层才能与求解层干净分离
- 原则四依赖原则一：正因为分离，求解器才能可插拔

### 依赖关系

```
原则三（闭包性）
  ↓ 使可能
原则二（代数即代码）
  ↓ 使可能
原则一（分离）
  ↓ 使可能
原则四（可插拔）
```

闭包性是一切的数学基础。没有闭包性，就需要表达式树，运算符重载变得复杂，
建模层和求解层的分离也变得困难。

### 原则之间的张力

四原则并非总是和谐共存，有时存在张力：

1. **原则二 vs 原则三**：运算符重载支持非线性（`x * y`）会破坏闭包性。minipulp 选择禁止非线性，用 `TypeError` 保护闭包性。
2. **原则一 vs 性能**：文件中转有 I/O 开销。对于极大规模问题，内存中直接传矩阵更快。PuLP 选择了分离，牺牲了少量性能。
3. **原则四 vs 简单**：太多求解器选项会让用户困惑。minipulp 用"默认求解器"机制缓解——零配置就能用。

```python
# 原则二与原则三的张力：非线性被禁止
try:
    expr = x * y  # 试图构造非线性表达式
except TypeError as e:
    # "不能将两个含变量的表达式相乘（非线性）"
    # 闭包性被保护
    pass
```

---

## 与其他建模库的对比

### minipulp / PuLP

```python
x = mp.LpVariable("x", lowBound=0)
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob.solve()
```

特点：运算符重载、字典表示、文件中转

### Pyomo

```python
m = pyo.ConcreteModel()
m.x = pyo.Var(domain=pyo.NonNegativeReals)
m.y = pyo.Var(domain=pyo.NonNegativeReals)
m.obj = pyo.Objective(expr=3*m.x + 2*m.y, sense=pyo.maximize)
m.con = pyo.Constraint(expr=2*m.x + m.y <= 100)
pyo.SolverFactory('cbc').solve(m)
```

特点：也用运算符重载，但支持非线性（表达式树）、更重量级

#### Pyomo 的设计哲学

Pyomo 的全称是 "Python Optimization Modeling Objects"，由 Sandia 国家实验室开发。其设计理念与 PuLP 有显著不同：

1. **支持非线性**：Pyomo 允许 `x * y`、`x**2`、`sin(x)` 等非线性表达式，因此必须用表达式树。
2. **块结构**：Pyomo 支持 `Block`，可以将模型分层组织，适合大规模建模。
3. **抽象模型**：Pyomo 区分 `AbstractModel`（符号模型）和 `ConcreteModel`（数据已填充的模型），支持先建模型后填数据。
4. **约束生成**：Pyomo 支持用 Python 函数批量生成约束：

```python
# Pyomo 的约束生成
m = pyo.ConcreteModel()
m.I = pyo.RangeSet(5)
m.x = pyo.Var(m.I, domain=pyo.NonNegativeReals)

def con_rule(m, i):
    return sum(m.x[j] for j in range(1, i+1)) <= 10 * i
m.con = pyo.Constraint(m.I, rule=con_rule)
```

对比 PuLP 的等价写法：

```python
# PuLP 的约束生成
x = [mp.LpVariable(f"x_{i}", lowBound=0) for i in range(5)]
for i in range(5):
    prob += sum(x[j] for j in range(i+1)) <= 10 * (i + 1)
```

Pyomo 的方式更"声明式"，PuLP 的方式更"命令式"。

### SciPy linprog

```python
from scipy.optimize import linprog
result = linprog(c=[-3, -2], A_ub=[[2, 1]], b_ub=[100], bounds=[(0, None), (0, None)])
```

特点：直接传矩阵、无建模层、适合小规模问题

#### SciPy 的定位

SciPy 的 `linprog` 不试图成为建模库，而是一个求解函数：

- **无变量概念**：变量是矩阵的列，没有名字。
- **无表达式**：约束直接以矩阵 $A$ 和向量 $b$ 传入。
- **无求解器抽象**：通过 `method` 参数选择算法（'simplex'、'interior-point'、'highs'）。

```python
# SciPy 的矩阵接口
# min  c^T x
# s.t. A_ub x <= b_ub
#      A_eq x  = b_eq
#      lb <= x <= ub

result = linprog(
    c=[-3, -2],           # 目标系数
    A_ub=[[2, 1], [1, 1], [1, 0]],  # 不等式约束矩阵
    b_ub=[100, 80, 40],   # 不等式约束右端
    bounds=[(0, None), (0, None)]   # 变量边界
)
```

这种方式适合：
- 问题规模小、变量少
- 约束以矩阵形式自然出现（如信号处理）
- 不需要可读的模型代码

但对于有业务含义的问题，矩阵接口极不直观：

```python
# 矩阵接口：第 0 个变量是什么？第 2 个约束代表什么？
# 代码无法回答这些问题

# PuLP 接口：x 是"产量"，c1 是"产能约束"
# 代码本身就是文档
x = mp.LpVariable("production", lowBound=0)
prob += 2 * x <= 100  # 产能约束
```

### CVXPY

```python
import cvxpy as cp

x = cp.Variable(nonneg=True)
y = cp.Variable(nonneg=True)
prob = cp.Problem(cp.Maximize(3*x + 2*y), [2*x + y <= 100])
prob.solve()
```

特点：凸优化、DCP（Disciplined Convex Programming）、自动微分

#### CVXPY 的 DCP 原理

CVXPY 的核心创新是 DCP（Disciplined Convex Programming），一套构造凸问题的规则系统：

1. **凸性追踪**：每个表达式标记为"凸"、"凹"或"仿射"。
2. **曲率规则**：凸 + 凸 = 凸，凹 + 凹 = 凹，凸 × 非负 = 凸，等等。
3. **验证**：CVXPY 在构造表达式时自动验证凸性，非凸问题直接报错。

```python
# CVXPY 的凸性追踪
x = cp.Variable(nonneg=True)
expr = x**2        # 凸（square of nonneg is convex）
expr = cp.square(x)  # 显式凸函数
expr = cp.log(x)   # 凹

# 非凸问题会被拒绝
# prob = cp.Problem(cp.Maximize(x * y), [])  # DCPError!
```

对比 minipulp 的"闭包性"：

| 特性 | minipulp（闭包性） | CVXPY（DCP） |
|------|-------------------|-------------|
| 允许的运算 | 加法、标量乘 | 加法、凸/凹函数组合 |
| 表示方式 | 扁平字典 | 表达式树 + 曲率标记 |
| 验证方式 | 运行时 TypeError | 构造时 DCPError |
| 覆盖范围 | 线性规划 | 凸优化 |
| 复杂度 | $O(n)$ | $O(\text{树大小})$ |

minipulp 的闭包性可以看作 DCP 的线性特例——线性函数既是凸的也是凹的，所以任意线性组合都合法。

### Gurobi Python API

```python
import gurobipy as gp

m = gp.Model("demo")
x = m.addVar(lb=0, name="x")
y = m.addVar(lb=0, name="y")
m.setObjective(3*x + 2*y, gp.GRB.MAXIMIZE)
m.addConstr(2*x + y <= 100)
m.optimize()
```

特点：商业求解器、运算符重载、高性能

#### GurobiPy 的设计取舍

Gurobi 的 Python API 与 PuLP 非常相似，但有关键区别：

1. **求解器绑定**：GurobiPy 是 Gurobi 求解器的专属 API，不能用于其他求解器。
2. **内存模型**：GurobiPy 直接操作求解器内存中的模型，无文件中转。
3. **延迟更新**：GurobiPy 默认延迟更新模型，需要手动 `m.update()`：

```python
# GurobiPy 的延迟更新
x = m.addVar(name="x")  # 变量已创建但未加入模型
m.update()               # 必须手动更新才能在约束中使用
m.addConstr(x <= 10)
```

PuLP 不需要手动更新——每次 `prob +=` 立即生效。这更符合 Python 的直觉，但牺牲了批量更新的性能优化机会。

### OR-Tools

```python
from ortools.linear_solver import pywraplp

solver = pywraplp.Solver.CreateSolver('CBC')
x = solver.IntVar(0, solver.infinity(), 'x')
y = solver.IntVar(0, solver.infinity(), 'y')
solver.Maximize(3 * x + 2 * y)
solver.Add(2 * x + y <= 100)
solver.Solve()
```

特点：Google 出品、C++ 核心、支持多种求解器

#### OR-Tools 的架构

OR-Tools 采用与 PuLP 不同的架构：

1. **求解器优先**：`Solver` 对象是核心，变量和约束都挂在求解器上。
2. **无独立模型**：模型和求解器绑定，换求解器需要重建模型。
3. **C++ 核心**：Python 只是薄薄的绑定层，性能极高。

```python
# OR-Tools：模型与求解器绑定
solver1 = pywraplp.Solver.CreateSolver('CBC')
x1 = solver1.IntVar(0, 10, 'x')
# 换求解器需要重建
solver2 = pywraplp.Solver.CreateSolver('GLOP')
x2 = solver2.IntVar(0, 10, 'x')  # 重新创建变量
```

对比 PuLP 的模型独立：

```python
# PuLP：模型与求解器分离
x = mp.LpVariable("x", lowBound=0, upBound=10)
prob = mp.LpProblem("demo")
prob += x
# 同一模型送不同求解器
prob.solve(solver=SimplexCore())
prob.solve(solver=PULP_CBC_CMD())
```

### 对比表

| 特性 | minipulp/PuLP | Pyomo | SciPy | CVXPY | GurobiPy | OR-Tools |
|------|-------------|-------|-------|-------|----------|----------|
| 建模方式 | 运算符重载 | 运算符重载 | 矩阵传入 | 运算符重载 | 运算符重载 | 运算符重载 |
| 表达式表示 | 扁平字典 | 表达式树 | 无 | 表达式树 | 求解器原生 | 求解器原生 |
| 非线性支持 | 不支持 | 支持 | 不支持 | 凸函数 | 二次 | 不支持 |
| 求解器切换 | 换参数 | 换参数 | 换函数 | 换参数 | 不可 | 重建模型 |
| 模型独立 | 是 | 是 | N/A | 是 | 否 | 否 |
| 学习曲线 | 低 | 中 | 低 | 中 | 低 | 低 |
| 适合场景 | LP/MILP | LP/NLP/MILP | 小规模 LP | 凸优化 | LP/MILP/QP | LP/MILP/CP |
| 开源 | 是 | 是 | 是 | 是 | 否 | 是 |

---

## 设计模式视角

从设计模式的角度看 minipulp 的四大原则：

### 策略模式（Strategy）

`LpSolver` 是策略接口，`SimplexCore`/`SimplexCpp`/`PULP_CBC_CMD` 是具体策略。
`LpProblem.solve(solver)` 是上下文，通过传入不同策略改变行为。

```python
# 策略模式
prob.solve(solver=SimplexCore())   # 策略 A
prob.solve(solver=PULP_CBC_CMD())  # 策略 B
```

策略模式的 UML 结构：

```
         ┌──────────┐
         │ LpProblem│  Context
         └────┬─────┘
              │ uses
              ▼
         ┌──────────┐
         │ LpSolver │  Strategy (interface)
         └────┬─────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌────────┐┌────────┐┌──────────┐
│Simplex ││Simplex ││PULP_CBC  │
│Core    ││Cpp     ││_CMD      │
└────────┘└────────┘└──────────┘
```

### 模板方法模式（Template Method）

`LpSolver.solve()` 是模板方法，定义了求解流程：
`available() → actualSolve()`。子类只需实现 `actualSolve()`。

```python
class LpSolver:
    def solve(self, problem):  # 模板方法
        if not self.available():
            raise RuntimeError(...)
        return self.actualSolve(problem)  # 子类实现
```

### 工厂方法模式（Factory Method）

`_get_default_solver()` 是工厂方法，根据环境创建合适的求解器。

```python
def _get_default_solver():
    cpp = SimplexCpp()
    if cpp.available():
        return cpp
    return SimplexCore()
```

### 代理模式（Proxy）

`SimplexCpp` 继承 `SimplexCore`，但将核心计算代理给 C++ 扩展。
对用户来说接口完全相同，但底层实现切换了。

```python
class SimplexCpp(SimplexCore):
    def _solve(self, std):
        # 代理给 C++ _native
        return _native.solve_simplex(...)
```

### 观察者模式（Observer）的潜在应用

虽然 minipulp 当前未使用观察者模式，但在 LP 建模中有潜在应用场景：

```python
# 假想：求解进度通知
class LpProblem:
    def __init__(self):
        self._listeners = []

    def add_listener(self, listener):
        self._listeners.append(listener)

    def solve(self, solver=None):
        for listener in self._listeners:
            listener.on_solve_start(self)
        status = solver.solve(self)
        for listener in self._listeners:
            listener.on_solve_end(self, status)
        return status

# 使用
class ProgressLogger:
    def on_solve_start(self, prob):
        print(f"开始求解 {prob.name}...")
    def on_solve_end(self, prob, status):
        print(f"求解完成: {status}")

prob.add_listener(ProgressLogger())
prob.solve()
```

观察者模式在以下场景有实际价值：

1. **求解进度监控**：大规模问题求解可能耗时数小时，需要进度回调。
2. **模型变更通知**：变量或约束被添加时通知相关组件。
3. **日志记录**：所有操作自动记录，无需在每个调用点手动写日志。
4. **灵敏度分析**：模型参数变化时自动重新求解。

PuLP 实际上在 `PULP_CBC_CMD` 中用了简化版的观察者——通过 `msg` 参数控制是否打印求解器输出：

```python
prob.solve(msg=True)   # 打印求解过程
prob.solve(msg=False)  # 静默
```

### 装饰器模式（Decorator）的潜在应用

装饰器模式可以用来增强求解器功能：

```python
# 假想：用装饰器给求解器添加计时功能
class TimingSolver(LpSolver):
    def __init__(self, inner):
        self._inner = inner

    def available(self):
        return self._inner.available()

    def actualSolve(self, problem):
        start = time.time()
        status = self._inner.actualSolve(problem)
        elapsed = time.time() - start
        print(f"{self._inner.name} 耗时 {elapsed:.2f}s")
        return status

# 使用
prob.solve(solver=TimingSolver(SimplexCore()))
# 输出: SimplexCore 耗时 0.05s
```

更多装饰器应用：

```python
# 重试装饰器
class RetrySolver(LpSolver):
    def __init__(self, inner, max_retries=3):
        self._inner = inner
        self._max_retries = max_retries

    def actualSolve(self, problem):
        for attempt in range(self._max_retries):
            try:
                return self._inner.actualSolve(problem)
            except SolverError:
                if attempt == self._max_retries - 1:
                    raise

# 缓存装饰器
class CachingSolver(LpSolver):
    def __init__(self, inner):
        self._inner = inner
        self._cache = {}

    def actualSolve(self, problem):
        key = problem.hash()
        if key in self._cache:
            return self._cache[key]
        status = self._inner.actualSolve(problem)
        self._cache[key] = status
        return status
```

### 命令模式（Command）

`LpConstraint` 可以看作命令模式的体现——每个约束是一个命令对象，可以被添加、删除、序列化：

```python
# 命令模式
constraint = 2 * x + y <= 100  # 创建命令
prob += constraint              # 执行命令（添加到问题）
prob -= constraint              # 撤销命令（从问题移除）
constraint.writeLP(file)        # 序列化命令
```

### 迭代器模式（Iterator）

`LpProblem` 支持迭代其变量和约束：

```python
# 迭代器模式
for var in prob.variables():
    print(f"{var.name} = {var.varValue}")

for name, constraint in prob.constraints.items():
    print(f"{name}: {constraint}")
```

### 抽象工厂模式（Abstract Factory）

如果 minipulp 要支持不同的建模风格（如矩阵式 vs 代数式），可以用抽象工厂：

```python
# 假想：抽象工厂
class LPFactory:
    def create_variable(self, name): ...
    def create_problem(self, name): ...
    def create_constraint(self, expr): ...

class AlgebraicFactory(LPFactory):
    def create_variable(self, name):
        return LpVariable(name)
    # ...

class MatrixFactory(LPFactory):
    def create_variable(self, name):
        return MatrixVariable(name)
    # ...
```

---

## 工程实践启示

### 启示一：数学性质决定实现方式

闭包性（原则三）决定了可以用扁平字典而非表达式树。
这不是"聪明的优化"，而是数学性质的自然推论。

**启示**：理解问题的数学结构，能让实现事半功倍。

### 启示二：接口分离降低耦合

建模层和求解层通过 `LpSolver` 接口分离，互不知道对方内部实现。
这使得可以独立开发、测试、替换。

**启示**：定义好接口，让模块各司其职。

### 启示三：运算符重载要谨慎

重载 `__eq__` 返回 `LpConstraint` 而非 `bool`，破坏了 Python 的相等性语义。
需要通过 `__hash__` 和 `is` 判断来补偿。

**启示**：运算符重载强大但危险，需要全面考虑副作用。

### 启示四：优雅降级比强制依赖好

C++ 扩展不可用时自动回退纯 Python，而非报错。
用户零配置就能用，有编译环境就更快。

**启示**：可选依赖 + 优雅降级 > 强制依赖。

### 启示五：教学透明优先于性能

`SimplexCore` 用纯 Python 实现，虽然慢但每一步可见。
`SimplexCpp` 用 C++ 实现，快但需要编译。

**启示**：教学代码优先可读性，生产代码优先性能，两者都有价值。

### 启示六：标准化接口的威力

LP 文件格式是 OR 社区的通用语言。minipulp 不需要知道 CBC、GLPK、CPLEX 的内部 API——只要能写 LP 文件，就能对接任何求解器。

**启示**：拥抱标准，不要重新发明轮子。

```python
# 标准化接口让生态成为可能
# minipulp 只需写 LP 文件，就能对接所有求解器
prob.writeLP("model.lp")  # 标准格式
# 任何能读 LP 的求解器都能用这个文件
```

### 启示七：默认值的设计

`prob.solve()` 不传求解器时自动选择最优可用——这是"合理默认"的设计哲学。

**启示**：好的默认值让 80% 的用户零配置就能用，同时保留 20% 的高级用户自定义能力。

```python
# 80% 的用户：零配置
prob.solve()  # 自动选最优

# 20% 的用户：显式指定
prob.solve(solver=PULP_CBC_CMD(msg=True))  # 要看日志
```

### 启示八：分层设计降低认知负担

minipulp 的三层求解器（L0/L1/L2）让不同需求的用户看到不同层次的细节：

- 初学者：只用 `prob.solve()`，不关心求解器
- 学习算法者：读 `SimplexCore` 源码，理解单纯形法
- 追求性能者：编译 `SimplexCpp`，获得加速
- 工业用户：用 `PULP_CBC_CMD`，对接工业求解器

**启示**：好的分层让系统对不同用户呈现不同复杂度。

---

## 历史背景

### Dantzig 与单纯形法的发明

1947 年，George Dantzig 在美国空军工作期间发明了单纯形法（Simplex Method），这是线性规划领域的奠基性工作。

#### 历史故事

Dantzig 在加州大学伯克利分校读研究生时，有一则著名的轶事：

1939 年，Dantzig 迟到到达 Jerzy Neyman 的统计学课堂，黑板上写着两个未解的统计问题。Dantzig 以为是作业，抄下来带回家解决了，并当作作业提交。六周后，Neyman 兴奋地找到 Dantzig——他解决的是统计学中两个著名的未证明定理！

这个故事后来成为电影《心灵捕手》（Good Will Hunting）的灵感来源之一。

#### 单纯形法的诞生

二战期间，Dantzig 在美国空军负责后勤规划。空军需要解决大量资源分配问题：

- 如何用最少的成本完成运输任务？
- 如何在有限的人力物力下最大化战果？

这些问题本质上都是线性规划。Dantzig 在 1947 年提出了单纯形法，用系统化的方式解决这类问题。

单纯形法的核心思想：

1. 线性规划的可行域是凸多面体
2. 最优解一定在顶点（极点）上
3. 沿着多面体的边从一个顶点走到相邻顶点，目标值不断改善
4. 直到无法改善，即为最优

```
     最优解在这里
       ●
      / \
     /   \
    /     \
   ●───────●
  /         \
 ●           ●
（可行域的顶点）
```

#### 单纯形法的影响

单纯形法被誉为"20 世纪十大算法"之一。其影响远超军事领域：

- **工业生产**：石油炼制、钢铁生产、食品加工
- **物流运输**：航线规划、车辆调度
- **金融**：投资组合优化
- **通信**：网络路由
- **能源**：电网调度

Dantzig 因此被称为"线性规划之父"。

### LP 文件格式的历史

LP 格式由 CPLEX 公司（现属 IBM）定义，是线性规划模型的文本表示标准。

#### 格式设计原则

1. **人类可读**：用接近数学公式的语法
2. **逐行解析**：便于词法分析器处理
3. **向后兼容**：新版本不破坏旧格式

```
\ 这是注释
Maximize
  obj: 3 x + 2 y
Subject To
  c1: 2 x + y <= 100
Bounds
  x >= 0
End
```

#### 与 MPS 格式的历史

MPS 格式更古老，由 IBM 在 1960 年代为 MPS/360 系统定义：

- **列导向**：数据按列组织，适合稀疏矩阵
- **固定格式**：字段位置严格固定（1-4 列是关键字等）
- **紧凑**：比 LP 格式更紧凑，适合大规模问题

MPS 格式的固定字段布局：

```
列号:  1-4      5-12    13-14   15-22   23-24   25-36
       关键字   名称    (空)    列名    行名    值
```

这种固定格式来自打孔卡时代——每列对应打孔卡的一列。

### PuLP 的发展历程

PuLP 由 Stu Mitchell 在 2007 年创建，最初用于教学和简单的 LP 建模。

#### 发展时间线

| 年份 | 事件 |
|------|------|
| 2007 | Stu Mitchell 创建 PuLP |
| 2010 | 加入 CBC 求解器支持 |
| 2014 | 发布 1.0 版本 |
| 2019 | PuLP 2.0，全面 Python 3 支持 |
| 2022 | PuLP 2.7，改进性能 |
| 2024 | 持续维护，社区活跃 |

#### PuLP 的设计决策

PuLP 的几个关键设计决策影响了其成功：

1. **运算符重载**：让代码读起来像数学公式
2. **CBC 作为默认求解器**：开源、免费、跨平台
3. **文件中转**：不依赖求解器的 Python API，通过文件通信
4. **轻量级**：不试图做 Pyomo 那样的"大而全"

```python
# PuLP 的标志性 API
prob = LpProblem("demo", LpMaximize)
prob += 3 * x + 2 * y        # 用 += 添加目标
prob += 2 * x + y <= 100     # 用 += 添加约束
```

`+=` 的双关用法是 PuLP 的标志性设计——同一个运算符，第一次调用设置目标，后续调用添加约束。这利用了 Python 的运算符重载，但也有些"魔法"——不够显式。

### 线性规划求解器的历史

| 年份 | 事件 |
|------|------|
| 1947 | Dantzig 发明单纯形法 |
| 1951 | Dantzig 发表论文 |
| 1979 | Khachiyan 证明 LP 多项式可解（椭球法） |
| 1984 | Karmarkar 发明内点法 |
| 1990s | CPLEX、Gurobi 等商业求解器成熟 |
| 2000s | 开源求解器（CBC、GLPK）成熟 |
| 2010s | Python 建模库（PuLP、Pyomo、CVXPY）兴起 |
| 2020s | HiGHS 等新一代开源求解器 |

Khachiyan 的椭球法虽然理论复杂度优于单纯形法（多项式 vs 指数最坏情况），但实际性能远不如单纯形法。Karmarkar 的内点法是第一个既有理论保证又实际可行的多项式算法。

---

## 工业应用案例

线性规划在工业界有极其广泛的应用，以下是几个典型领域。

### 物流运输

#### 案例：快递公司路由优化

某快递公司每天需要从分拣中心向 100 个配送站送货，有 10 辆车可用。目标是最小化总运输成本。

```python
# 物流路由优化模型
import minipulp as mp

# 参数
n_stations = 100  # 配送站数量
n_trucks = 10     # 车辆数量
demand = [...]    # 各站需求量
capacity = 1000   # 车辆容量
cost = [...]      # 从中心到各站的运输成本

# 变量：x[i,j] = 1 表示车辆 i 访问站 j
x = {(i, j): mp.LpVariable(f"x_{i}_{j}", cat="Binary")
     for i in range(n_trucks) for j in range(n_stations)}

prob = mp.LpProblem("delivery", mp.LpMinimize)

# 目标：最小化总成本
prob += sum(cost[j] * x[i, j]
            for i in range(n_trucks) for j in range(n_stations))

# 约束：每个站恰好被访问一次
for j in range(n_stations):
    prob += sum(x[i, j] for i in range(n_trucks)) == 1

# 约束：车辆容量
for i in range(n_trucks):
    prob += sum(demand[j] * x[i, j] for j in range(n_stations)) <= capacity

prob.solve()
```

#### 实际规模

- Amazon 每天求解数万个此类问题
- UPS 的 ORION 系统每年节省 3-5 亿美元燃油成本
- 京东的智能调度系统覆盖全国 500+ 仓库

### 金融投资

#### 案例：投资组合优化

Markowitz 的投资组合理论是 LP/QP 在金融的经典应用：

```python
# 投资组合优化（简化版）
n_assets = 50
expected_return = [...]  # 各资产预期收益
risk = [...]             # 各资产风险（方差）
budget = 1_000_000       # 总预算

# 变量：各资产投资额
x = [mp.LpVariable(f"asset_{i}", lowBound=0) for i in range(n_assets)]

prob = mp.LpProblem("portfolio", mp.LpMaximize)

# 目标：最大化预期收益
prob += sum(expected_return[i] * x[i] for i in range(n_assets))

# 约束：总预算
prob += sum(x) <= budget

# 约束：风险限制
prob += sum(risk[i] * x[i] for i in range(n_assets)) <= 0.05 * budget

# 约束：单一资产不超过 20%
for i in range(n_assets):
    prob += x[i] <= 0.2 * budget

prob.solve()
```

#### 实际应用

- **养老基金**：BlackRock 的 Aladdin 系统管理数万亿美元资产
- **银行**：资产负债管理、资本配置
- **保险**：再保险策略优化
- **对冲基金**：统计套利的权重优化

### 能源电力

#### 案例：电网调度

电力公司需要决定各发电厂的出力，满足需求同时最小化成本：

```python
# 机组组合（Unit Commitment）简化模型
n_plants = 20          # 发电厂数量
n_hours = 24           # 一天 24 小时
demand = [...]         # 各时段用电需求
min_output = [...]     # 各电厂最小出力
max_output = [...]     # 各电厂最大出力
cost = [...]           # 各电厂单位成本

# 变量
p = {(i, t): mp.LpVariable(f"p_{i}_{t}", lowBound=0)  # 出力
     for i in range(n_plants) for t in range(n_hours)}
u = {(i, t): mp.LpVariable(f"u_{i}_{t}", cat="Binary")  # 开停状态
     for i in range(n_plants) for t in range(n_hours)}

prob = mp.LpProblem("dispatch", mp.LpMinimize)

# 目标：最小化总发电成本
prob += sum(cost[i] * p[i, t]
            for i in range(n_plants) for t in range(n_hours))

# 约束：满足需求
for t in range(n_hours):
    prob += sum(p[i, t] for i in range(n_plants)) >= demand[t]

# 约束：出力上下限（与开停状态关联）
for i in range(n_plants):
    for t in range(n_hours):
        prob += p[i, t] >= min_output[i] * u[i, t]
        prob += p[i, t] <= max_output[i] * u[i, t]

prob.solve()
```

#### 实际应用

- **国家电网**：日前调度、实时调度
- **新能源**：风电、光伏出力预测与调度
- **电力市场**：节点电价计算（LMP）
- **储能**：抽水蓄能、电池储能的充放电策略

### 制造业

#### 案例：生产计划

工厂需要决定各产品的生产量，满足产能和需求约束：

```python
# 生产计划
n_products = 10
n_resources = 5  # 原材料、工时等

profit = [...]      # 各产品单位利润
demand = [...]      # 各产品需求上限
available = [...]   # 各资源可用量
usage = [...]       # 各产品对各资源的使用量

# 变量：各产品生产量
x = [mp.LpVariable(f"product_{i}", lowBound=0) for i in range(n_products)]

prob = mp.LpProblem("production", mp.LpMaximize)

# 目标：最大化总利润
prob += sum(profit[i] * x[i] for i in range(n_products))

# 约束：资源限制
for r in range(n_resources):
    prob += sum(usage[i][r] * x[i] for i in range(n_products)) <= available[r]

# 约束：需求上限
for i in range(n_products):
    prob += x[i] <= demand[i]

prob.solve()
```

#### 实际应用

- **石油炼制**：ExxonMobil 用 LP 优化炼油配方，每年节省数亿美元
- **钢铁生产**：配料优化、生产排程
- **食品加工**：原料混合、配方优化
- **汽车制造**：生产线平衡、物料调度

### 通信网络

#### 案例：网络流优化

```python
# 最大流问题
n_nodes = 10
edges = [...]  # 边列表
capacity = {...}  # 各边容量

# 变量：各边流量
f = {e: mp.LpVariable(f"flow_{e}", lowBound=0) for e in edges}

prob = mp.LpProblem("maxflow", mp.LpMaximize)

# 目标：最大化从源到汇的流量
source, sink = 0, n_nodes - 1
prob += sum(f[e] for e in edges if e[0] == source)

# 约束：流量守恒（中间节点）
for node in range(1, n_nodes - 1):
    inflow = sum(f[e] for e in edges if e[1] == node)
    outflow = sum(f[e] for e in edges if e[0] == node)
    prob += inflow - outflow == 0

# 约束：容量限制
for e in edges:
    prob += f[e] <= capacity[e]

prob.solve()
```

#### 实际应用

- **互联网路由**：OSPF 权重优化
- **CDN 调度**：内容分发网络流量调度
- **5G 网络**：资源块分配
- **数据中心**：虚拟机放置、流量工程

### 农业

#### 案例：饲料配方

```python
# 饲料配方优化
n_ingredients = 8  # 玉米、豆粕、鱼粉等
n_nutrients = 6    # 蛋白质、能量、钙、磷等

price = [...]       # 各原料价格
requirement = [...] # 各营养需求
content = [...]     # 各原料各营养含量

# 变量：各原料比例
x = [mp.LpVariable(f"ing_{i}", lowBound=0) for i in range(n_ingredients)]

prob = mp.LpProblem("feed", mp.LpMinimize)

# 目标：最小化成本
prob += sum(price[i] * x[i] for i in range(n_ingredients))

# 约束：配方总和为 1
prob += sum(x) == 1

# 约束：营养需求
for n in range(n_nutrients):
    prob += sum(content[i][n] * x[i] for i in range(n_ingredients)) >= requirement[n]

prob.solve()
```

#### 实际应用

- **饲料配方**：家禽、牲畜饲料优化
- **肥料配比**：NPK 配比优化
- **作物种植**：土地分配、轮作规划
- **食品配方**：满足营养标签的同时最小化成本

---

## 教学价值讨论

### 为什么从零实现一个 LP 库？

minipulp 的核心价值不在于"又一个 LP 库"，而在于教学。从零实现让学习者理解：

1. **运算符重载的实战应用**：不是玩具示例，而是生产级使用
2. **设计模式的真实场景**：策略、模板方法、工厂等模式在真实需求中自然出现
3. **数学与工程的桥梁**：闭包性如何转化为字典表示
4. **Python/C++ 混合编程**：pybind11 的实际应用
5. **测试驱动开发**：每个模块都有完整测试

### 教学路径

minipulp 的三层求解器设计了一条渐进式学习路径：

```
L0: SimplexCore（纯 Python）
    ↓ 理解算法
L1: SimplexCpp（C++ 加速）
    ↓ 理解性能
L2: PULP_CBC_CMD（工业求解器）
    ↓ 理解生态
```

#### L0：理解算法

`SimplexCore` 用纯 Python 实现单纯形法，每一步都可见：

```python
# SimplexCore 的核心循环（简化）
while True:
    # 1. 选入基变量（最负检验数）
    entering = select_entering(tableau)
    if entering is None:
        break  # 最优

    # 2. 选出基变量（最小比值）
    leaving = select_leaving(tableau, entering)
    if leaving is None:
        return UNBOUNDED

    # 3. 旋转变换
    pivot(tableau, entering, leaving)
```

学习者可以：
- 打印每一步的单纯形表
- 观察入基/出基选择
- 理解为什么单纯形法有效

#### L1：理解性能

`SimplexCpp` 用 C++ 实现同样的算法，通过 pybind11 暴露给 Python：

```cpp
// C++ 核心（简化）
Eigen::MatrixXd solve_simplex(Eigen::MatrixXd tableau) {
    while (true) {
        int entering = find_entering(tableau);
        if (entering < 0) break;
        int leaving = find_leaving(tableau, entering);
        pivot(tableau, entering, leaving);
    }
    return tableau;
}
```

学习者可以：
- 对比 Python 和 C++ 的性能差异
- 理解 pybind11 的绑定机制
- 学习 Python/C++ 混合编程的最佳实践

#### L2：理解生态

`PULP_CBC_CMD` 通过子进程调用 CBC 求解器：

```python
# 生成 LP 文件 → 调用 CBC → 解析解
def actualSolve(self, problem):
    problem.writeLP("model.lp")
    subprocess.run(["cbc", "model.lp", "solve", "-solu", "model.sol"])
    self._parse_solution(problem, "model.sol")
```

学习者可以：
- 理解文件格式作为接口
- 学习子进程通信
- 理解工业级求解器的使用方式

### 与其他教学项目的对比

| 项目 | 主题 | 特点 |
|------|------|------|
| minipulp | LP 建模库 | 运算符重载 + 求解器抽象 |
| 500lines | 各种系统 | 每个项目 500 行以内 |
| craftinterpreters | 解释器 | 逐章构建 |
| nand2tetris | 硬件到软件 | 从逻辑门到操作系统 |
| minipulp | LP 库 | 从数学到工程 |

minipulp 的独特价值在于它展示了**数学库的设计哲学**——如何将数学性质（闭包性）转化为工程实现（字典表示），如何用设计模式（策略、模板方法）组织求解器。

### 教学中的常见误区

#### 误区一：重载 `__eq__` 是反模式

很多 Python 教程说"不要重载 `__eq__` 返回非 bool"。但 PuLP 证明，在特定领域（DSL）中，这是合理且必要的设计。

**正确的理解**：运算符重载的"语义"取决于领域。在数学 DSL 中，`==` 表示"构造等式约束"而非"判断相等"。

#### 误区二：文件 I/O 是性能瓶颈

有学生认为"文件中转太慢，应该用内存传递"。但实际测试表明，对于中等规模问题（< 10000 变量），文件 I/O 占比不到 5%。

**正确的理解**：文件 I/O 的好处（解耦、可调试）远大于其成本。

#### 误区三：应该支持非线性

有学生问"为什么不支持 `x * y`？"。答案是：支持非线性会破坏闭包性，需要表达式树，大幅增加复杂度。

**正确的理解**：选择性地"不做"也是设计。minipulp 选择只做线性，换来极大的简洁性。

---

## 从 minipulp 到 PuLP 的迁移指南

minipulp 的 API 刻意与 PuLP 保持一致，迁移非常简单。

### API 对照表

| 功能 | minipulp | PuLP |
|------|----------|------|
| 创建变量 | `mp.LpVariable("x", lowBound=0)` | `pulp.LpVariable("x", lowBound=0)` |
| 创建问题 | `mp.LpProblem("demo", mp.LpMaximize)` | `pulp.LpProblem("demo", pulp.LpMaximize)` |
| 添加目标 | `prob += 3*x + 2*y` | `prob += 3*x + 2*y` |
| 添加约束 | `prob += 2*x + y <= 100` | `prob += 2*x + y <= 100` |
| 求解 | `prob.solve()` | `prob.solve()` |
| 获取解值 | `x.varValue` | `x.varValue` |
| 获取状态 | `prob.status` | `pulp.LpStatus[prob.status]` |

### 迁移示例

#### minipulp 版本

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

prob.solve()
print(f"x = {x.varValue}, y = {y.varValue}")
print(f"最优值 = {prob.objective.value()}")
```

#### PuLP 版本

```python
import pulp

x = pulp.LpVariable("x", lowBound=0)
y = pulp.LpVariable("y", lowBound=0)

prob = pulp.LpProblem("demo", pulp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

prob.solve()
print(f"x = {x.varValue}, y = {y.varValue}")
print(f"最优值 = pulp.value(prob.objective)")
```

只需把 `import minipulp as mp` 改成 `import pulp`，其余几乎不变。

### 差异点

#### 求解器指定

```python
# minipulp
prob.solve(solver=mp.SimplexCore())     # 纯 Python
prob.solve(solver=mp.SimplexCpp())      # C++ 扩展
prob.solve(solver=mp.PULP_CBC_CMD())    # CBC

# PuLP
prob.solve()                             # 默认 CBC
prob.solve(pulp.PULP_CBC_CMD(msg=True)) # CBC 带日志
prob.solve(pulp.GLPK_CMD())              # GLPK
prob.solve(pulp.CPLEX_CMD())             # CPLEX
```

PuLP 支持更多求解器，minipulp 只支持三种（教学目的）。

#### 状态查询

```python
# minipulp
prob.status  # 返回字符串 "Optimal"

# PuLP
prob.status  # 返回整数 1
pulp.LpStatus[prob.status]  # "Optimal"
```

#### 求解器可用性

```python
# minipulp
solver = mp.SimplexCpp()
solver.available()  # bool

# PuLP
pulp.PULP_CBC_CMD().available()  # bool
```

### 迁移建议

1. **先学 minipulp**：理解设计原理，再迁移到 PuLP
2. **保持代码结构**：minipulp 的代码几乎可以直接用于 PuLP
3. **利用 PuLP 的更多求解器**：生产环境用 Gurobi/CPLEX
4. **注意状态码差异**：minipulp 用字符串，PuLP 用整数
5. **利用 PuLP 的成熟生态**：更多文档、更多示例、更多社区支持

```python
# 推荐的迁移路径
# 1. 用 minipulp 学习原理
# 2. 用 PuLP 做小项目
# 3. 用 Gurobi/CPLEX 做大规模生产
```

---

## 总结

理解这四点，你就理解了 PuLP 的设计哲学——也是 minipulp 的全部核心。

| 原则 | 层面 | 核心思想 | 数学/工程基础 |
|------|------|---------|-------------|
| 建模与求解分离 | 架构 | 通过接口解耦 | 依赖倒置原则 |
| 代数表达式即代码 | 实现 | 运算符重载 | Python 数据模型 |
| 仿射表达式闭包性 | 实现 | 字典表示 | 线性代数 |
| 多后端可插拔 | 架构 | 同接口子类 | 策略模式 |

这四原则不仅适用于线性规划建模库，其设计思想可以推广到许多领域：
任何"描述与执行分离"的系统都可以借鉴这套设计。

### 更广泛的启示

这四原则的适用范围远不止线性规划：

1. **数据库查询**：SQL（描述）与查询引擎（执行）分离
2. **机器学习**：模型定义（Keras）与后端（TensorFlow/PyTorch）分离
3. **配置管理**：声明式配置（YAML）与执行引擎（Ansible）分离
4. **UI 框架**：组件声明（JSX）与渲染器（React DOM/React Native）分离

```python
# 这种"描述与执行分离"的模式无处不在
# SQL: 描述要什么数据，不管怎么查
SELECT * FROM users WHERE age > 18;

# Keras: 描述模型结构，不管后端怎么算
model = Sequential([Dense(64), Dense(10)])

# PuLP: 描述优化问题，不管求解器怎么解
prob += 3 * x + 2 * y
prob.solve()
```

minipulp 的四原则，本质上是**好软件设计的通用原则**在 LP 建模领域的具体化。理解这一点，比记住四个原则本身更重要。
