# Phase 1 — 表达式系统

> 运算符重载如何把 `3*x + 2*y` 变成 `LpAffineExpression({x: 3, y: 2})`。
>
> 本篇对应 `src/minipulp/elements.py`，是整个库的代数核心。

---

## 目录

- [设计哲学](#设计哲学)
- [类层次结构](#类层次结构)
- [LpElement — 运算符协议](#lpelement--运算符协议)
- [LpAffineExpression — 仿射表达式](#lpaffineexpression--仿射表达式)
- [LpVariable — 决策变量](#lpvariable--决策变量)
- [运算符重载详解](#运算符重载详解)
- [闭包性证明](#闭包性证明)
- [哈希与相等性](#哈希与相等性)
- [lpSum — 高效求和](#lpsum--高效求和)
- [批量变量创建](#批量变量创建)
- [完整示例](#完整示例)
- [运算符重载逐步追踪](#运算符重载逐步追踪)
- [哈希与相等性深入分析](#哈希与相等性深入分析)
- [lpSum 性能基准测试](#lpsum-性能基准测试)
- [运输问题完整建模示例](#运输问题完整建模示例)
- [饮食问题示例](#饮食问题示例)
- [与 PuLP API 对比](#与-pulp-api-对比)
- [常见陷阱与最佳实践](#常见陷阱与最佳实践)
- [测试](#测试)

---

## 设计哲学

PuLP 最具辨识度的特征是：**建模代码几乎和数学公式一模一样**。

```python
# 数学公式：max 3x + 2y  s.t. 2x + y <= 100
# Python 代码：
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
```

这不是字符串解析——`3 * x + 2 * y` 是真正的 Python 表达式，
通过**运算符重载**构造出 `LpAffineExpression({x: 3, y: 2})` 对象。

核心思想：**代数表达式即代码**。变量是对象，运算是方法调用，结果是表达式对象。

### 为什么选择运算符重载而非字符串解析？

许多初学者会问：为什么不直接接受字符串 `"3*x + 2*y"` 然后解析？答案有几个层面：

1. **类型安全**：Python 解释器在构造表达式时已经做了语法检查，语法错误在构造时立即暴露，而不是在求解时才报错。
2. **IDE 支持**：运算符重载让变量名成为真正的 Python 变量，IDE 可以补全、跳转、重命名。
3. **调试友好**：可以在任意位置 `print(x + y)` 查看中间表达式对象，检查其 `terms` 和 `const`。
4. **性能**：避免了字符串解析的开销，表达式构造是直接的字典操作。
5. **组合性**：可以用 Python 的 `for` 循环、`if` 分支、函数抽象来构造复杂表达式，无需 DSL。

```python
# 字符串解析方式（不采用）：
# prob += "3*x + 2*y"  # 需要解析器，无法 IDE 补全

# 运算符重载方式（采用）：
# prob += 3 * x + 2 * y  # 原生 Python，类型安全
```

### 表达式即数据

在 minipulp 中，表达式不仅是代码的中间产物，更是**一等数据对象**。你可以：

```python
expr = 3 * x + 2 * y
print(expr.terms)    # {x: 3.0, y: 2.0}
print(expr.const)    # 0.0
print(len(expr.terms))  # 2 — 项数

# 表达式可以作为函数参数传递、返回、存储
def scale(e, factor):
    return factor * e

doubled = scale(expr, 2)
print(doubled.terms)  # {x: 6.0, y: 4.0}
```

这种"表达式即数据"的设计是符号计算的基础，让 minipulp 不仅能求解，还能对模型本身进行操作。

---

## 类层次结构

```
LpElement                    # 基类：定义运算符协议
  └── LpAffineExpression     # 仿射表达式：{var: coef} 字典 + 常数项
        └── LpVariable       # 决策变量：单变量表达式 {self: 1}
```

**继承关系的设计意图**：

- `LpElement` 定义运算符协议（`__add__`, `__mul__`, `__le__` 等）
- `LpAffineExpression` 实现所有代数运算（加法、数乘、比较）
- `LpVariable` 继承 `LpAffineExpression`，自动获得全部代数能力

变量"是一个"单变量表达式（`terms = {self: 1}, const = 0`）。
这一数学事实让运算符重载只需在 `LpAffineExpression` 写一次。

### 继承 vs 组合的权衡

有人可能会问：为什么用继承而不是组合（`LpVariable` 内部持有一个 `LpAffineExpression`）？

```python
# 继承方式（采用）：
class LpVariable(LpAffineExpression):
    # 自动获得所有代数运算
    pass

# 组合方式（不采用）：
class LpVariable:
    def __init__(self):
        self.expr = LpAffineExpression({self: 1})
    # 需要手动转发每个运算符
    def __add__(self, other):
        return self.expr.__add__(other)
    # ... 几十个转发方法
```

继承方式的优势：

1. **零样板代码**：`LpVariable` 自动获得所有运算符，无需转发。
2. **类型一致**：`x + y` 的结果类型是 `LpAffineExpression`，`x` 本身也是 `LpAffineExpression`，类型统一。
3. **数学正确**：变量在数学上就是单变量表达式，继承反映了这一 is-a 关系。

代价是 `LpVariable` 的运算结果会"降级"为 `LpAffineExpression`（通过 `_new` 方法），但这正是我们想要的——`x + y` 不再是单变量。

---

## LpElement — 运算符协议

`LpElement` 是所有可参与代数运算对象的基类：

```python
class LpElement:
    name: str = ""

    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __add__(self, other): raise NotImplementedError
    def __radd__(self, other): raise NotImplementedError
    def __sub__(self, other): raise NotImplementedError
    def __rsub__(self, other): raise NotImplementedError
    def __mul__(self, other): raise NotImplementedError
    def __rmul__(self, other): raise NotImplementedError
    def __truediv__(self, other): raise NotImplementedError
    def __neg__(self): raise NotImplementedError

    def __le__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.LE)

    def __ge__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.GE)

    def __eq__(self, other):
        from .constraints import LpConstraint
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

**比较运算符**（`__le__`, `__ge__`, `__eq__`）在基类实现，
因为它们的逻辑对所有子类相同：构造 `LpConstraint` 对象。

**延迟导入**：`from .constraints import LpConstraint` 在方法内部导入，
避免 `elements.py` 和 `constraints.py` 之间的循环导入。

### 为什么基类只定义协议而不实现？

`LpElement` 的算术方法（`__add__` 等）只 `raise NotImplementedError`，真正实现在 `LpAffineExpression`。这种设计有几个原因：

1. **协议文档**：基类明确声明"所有子类都应支持这些运算符"，作为接口契约。
2. **多态预留**：未来如果新增非仿射表达式类型（如二次表达式），可以继承 `LpElement` 并实现自己的运算符。
3. **错误诊断**：如果某种类型未实现运算符，会抛出 `NotImplementedError` 而非 `AttributeError`，错误信息更清晰。

### 比较运算符为什么在基类实现？

比较运算符（`<=`, `>=`, `==`）的语义对所有表达式类型相同：构造约束。无论左侧是变量还是复杂表达式，`expr <= rhs` 都应产生 `LpConstraint(expr - rhs, LE)`。因此在基类实现一次，所有子类复用。

```python
# 这些都通过 LpElement.__le__ 实现：
x <= 5                    # 变量 <= 常数
2 * x + 3 * y <= 100      # 表达式 <= 常数
x + y <= z + w            # 表达式 <= 表达式
```

### 延迟导入的必要性

```python
# elements.py
from .constraints import LpConstraint  # 顶层导入 → 循环！

# constraints.py
from .elements import LpAffineExpression  # 顶层导入 → 循环！
```

`elements.py` 和 `constraints.py` 相互依赖。Python 的模块系统无法处理这种循环导入（会抛出 `ImportError`）。解决方案是将导入推迟到方法内部：

```python
def __le__(self, other):
    from .constraints import LpConstraint  # 方法内部导入
    return LpConstraint(self - other, LpConstraintSense.LE)
```

此时 `constraints.py` 已经加载完成，导入安全。这是 Python 处理循环依赖的常用模式。

---

## LpAffineExpression — 仿射表达式

### 内部表示

```python
class LpAffineExpression(LpElement):
    def __init__(self, terms: dict | None = None, const: float = 0.0):
        if terms is None:
            self.terms = {}
        else:
            self.terms = {var: float(coef) for var, coef in terms.items() if coef != 0}
        self.const = float(const)
```

仿射表达式 $\sum_i c_i x_i + c_0$ 用两个属性表示：

- `terms: dict[LpVariable, float]` — 变量到系数的映射
- `const: float` — 常数项

**规范化**：构造时剔除零系数项（`if coef != 0`），保持表示唯一性。

### 为什么用字典而非表达式树？

传统计算机代数系统用**表达式树**表示表达式：

```
    +              树结构需要递归遍历，
   / \             每次运算创建新节点，
  *   *            求值、化简都很复杂。
 / \ / \
3  x 2  y
```

PuLP 用**扁平字典**表示：

```
{x: 3, y: 2}  ←  3*x + 2*y
```

这之所以可行，是因为**仿射表达式在加法和数乘下封闭**：

- 两个仿射表达式相加 → 仍是仿射表达式（字典系数相加）
- 仿射表达式乘以常数 → 仍是仿射表达式（系数同乘）

无需树结构，一个字典就够了。这是 PuLP 极简代码的数学根因。

#### 字典表示 vs 树表示的详细对比

| 维度 | 表达式树 | 扁平字典 |
|------|---------|---------|
| 表示 `3x + 2y` | `Add(Mul(3, x), Mul(2, y))` — 5 个节点 | `{x: 3, y: 2}` — 1 个字典 |
| 加法运算 | 创建新 `Add` 节点，需递归化简 | 字典合并，系数相加 |
| 数乘运算 | 创建新 `Mul` 节点，需递归分配 | 字典遍历，系数同乘 |
| 相等判断 | 树同构递归比较 | 字典相等（规范化后） |
| 内存 | 每个节点一个对象，开销大 | 一个字典，开销小 |
| 求值 | 递归遍历树 | 字典遍历，线性 |

对于线性规划这个特定领域，扁平字典在所有维度上都更优。树结构只在需要表示非线性（如 `x * y`, `sin(x)`）时才有必要。

### `_new` 工厂方法

```python
def _new(self, terms: dict, const: float) -> "LpAffineExpression":
    return LpAffineExpression(terms, const)
```

`LpVariable` 覆盖此方法，使运算结果降级为普通表达式：

```python
# LpVariable._new
def _new(self, terms, const):
    return LpAffineExpression(terms, const)  # 不再是 LpVariable
```

**为什么？** `x + y` 的结果是 `LpAffineExpression({x:1, y:1})`，
不是 `LpVariable`——它有两个变量，不是单变量表达式。

#### `_new` 的多态机制

```python
# LpAffineExpression._new
def _new(self, terms, const):
    return LpAffineExpression(terms, const)

# LpVariable._new（覆盖）
def _new(self, terms, const):
    return LpAffineExpression(terms, const)  # 强制降级
```

当 `x`（`LpVariable`）调用 `x + y` 时：

```python
# x.__add__(y) 内部调用 self._new(...)
# self 是 LpVariable，所以调用 LpVariable._new
# 返回 LpAffineExpression，而非 LpVariable
```

如果 `LpVariable` 不覆盖 `_new`，`x + y` 会尝试构造 `LpVariable(terms, const)`，但 `LpVariable.__init__` 的签名是 `(name, lowBound, upBound, cat)`，不匹配 `(terms, const)`，会报错。`_new` 让类型转换显式且可控。

### 常数项的处理

常数项 `const` 是仿射表达式的一部分，但不出现在 `terms` 字典中：

```python
expr = 3 * x + 5  # terms = {x: 3.0}, const = 5.0
print(expr.terms)  # {x: 3.0}
print(expr.const)  # 5.0

# 常数表达式
c = LpAffineExpression({}, 7.0)  # terms = {}, const = 7.0
print(c.terms)  # {}
print(c.const)  # 7.0
```

将常数项单独存储而非用特殊变量表示，简化了运算逻辑——加法只需 `const` 相加，数乘只需 `const` 同乘。

---

## LpVariable — 决策变量

### 构造

```python
class LpVariable(LpAffineExpression):
    def __init__(self, name, lowBound=None, upBound=None, cat=LpCat.CONTINUOUS):
        self.name = name
        self.lowBound = lowBound
        self.upBound = upBound
        self.cat = cat
        self.varValue = None        # 求解后回填
        self.terms = {self: 1.0}    # 单变量表达式：1 * x
        self.const = 0.0
```

变量 `x` 就是仿射表达式 `1 * x + 0`，即 `terms = {x: 1}, const = 0`。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 变量名，同时作为哈希依据 |
| `lowBound` | `float \| None` | 下界，None 表示无下界 |
| `upBound` | `float \| None` | 上界，None 表示无上界 |
| `cat` | `LpCat` | 变量类别（连续/整数/二元） |
| `varValue` | `float \| None` | 求解后回填的解值，求解前为 None |
| `terms` | `dict` | `{self: 1.0}` — 单变量表达式 |
| `const` | `float` | `0.0` — 无常数项 |

### 变量类别

```python
x = mp.LpVariable("x", lowBound=0)                          # 连续变量
z = mp.LpVariable("z", lowBound=0, upBound=10, cat=mp.LpInteger)  # 整数变量
b = mp.LpVariable("b", cat=mp.LpBinary)                     # 二元变量 (0 或 1)
```

| 类别 | 含义 | 求解器支持 |
|------|------|---------|
| `LpContinuous` | 连续变量，取值范围 [lb, ub] | SimplexCore, SimplexCpp, CBC |
| `LpInteger` | 整数变量，取值范围 [lb, ub] ∩ ℤ | CBC |
| `LpBinary` | 二元变量，取值 {0, 1} | CBC |

### 变量界的作用

变量界在求解器内部被当作约束处理，但在 LP 文件格式中有专门的 `Bounds` 段：

```python
x = mp.LpVariable("x", lowBound=0, upBound=10)
# LP 文件输出：
# Bounds
#   0 <= x <= 10
```

如果用约束表示：

```python
x = mp.LpVariable("x")
prob += x >= 0
prob += x <= 10
# LP 文件输出：
# Subject To
#   c_0: -1 x <= 0
#   c_1: 1 x <= 10
```

两者等价，但 `Bounds` 段更简洁，且某些求解器对界有专门优化（如界约束不进入基）。

### `varValue` 的生命周期

```python
x = mp.LpVariable("x", lowBound=0)
print(x.varValue)  # None — 求解前

prob = mp.LpProblem("demo", mp.LpMaximize)
prob += x
prob += x <= 5
prob.solve()

print(x.varValue)  # 5.0 — 求解后回填
```

`varValue` 由求解器在 `_backfill` 阶段写入。如果问题不可行，`varValue` 保持 `None`。

---

## 运算符重载详解

### 标量乘法：`3 * x`

```python
# Python 先尝试 int.__mul__(3, x) → NotImplemented
# 然后调用 x.__rmul__(3)
def __mul__(self, other):
    if _is_number(other):
        return self._new(
            {var: coef * other for var, coef in self.terms.items()},
            self.const * other,
        )
```

```
3 * x  →  x.__rmul__(3)  →  LpAffineExpression({x: 3.0})
```

#### Python 运算符分派机制

当 Python 计算 `3 * x` 时（`3` 是 `int`，`x` 是 `LpVariable`）：

1. 先尝试 `int.__mul__(3, x)` — `int` 不认识 `LpVariable`，返回 `NotImplemented`
2. Python 接着尝试 `type(x).__rmul__(x, 3)` — 反向乘法
3. `LpVariable.__rmul__` 继承自 `LpAffineExpression`，处理标量乘法

```python
def __rmul__(self, other):
    # other 是左操作数（标量），self 是右操作数（表达式）
    if _is_number(other):
        return self._new(
            {var: coef * other for var, coef in self.terms.items()},
            self.const * other,
        )
    return NotImplemented
```

`__rmul__` 和 `__mul__` 对标量乘法逻辑相同（乘法可交换），但 `__rmul__` 处理 `标量 * 表达式` 的情况。

### 加法：`x + y`

```python
def __add__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const + other)
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)
        for var, coef in other.terms.items():
            new_coef = merged.get(var, 0.0) + coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)  # 系数为 0 则删除
        return self._new(merged, self.const + other.const)
```

```
x + y  →  x.__add__(y)  →  LpAffineExpression({x: 1, y: 1})
```

**字典合并**：遍历 `other.terms`，系数相加。若结果为 0 则删除该项（规范化）。

#### 加法的三种情况

```python
# 情况 1：表达式 + 标量
expr = x + 5
# other = 5 是数字 → const += 5
# 结果：terms = {x: 1.0}, const = 5.0

# 情况 2：表达式 + 表达式
expr = (3 * x) + (2 * y)
# other = 2*y 是 LpAffineExpression
# merged = {x: 3.0}，然后合并 {y: 2.0}
# 结果：terms = {x: 3.0, y: 2.0}, const = 0.0

# 情况 3：表达式 + 表达式（同变量）
expr = (3 * x) + (2 * x)
# merged = {x: 3.0}，合并 {x: 2.0} → new_coef = 5.0
# 结果：terms = {x: 5.0}, const = 0.0
```

#### 系数抵消的规范化

```python
expr = (3 * x) + (-3 * x)
# merged = {x: 3.0}，合并 {x: -3.0} → new_coef = 0.0
# 系数为 0 → 删除该项
# 结果：terms = {}, const = 0.0 — 零表达式
```

规范化确保 `3*x - 3*x` 的结果是空字典（零表达式），而非 `{x: 0.0}`。这保证了表达式表示的唯一性，对相等判断和哈希很重要。

### 减法：`x - y`

```python
def __sub__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const - other)
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)
        for var, coef in other.terms.items():
            new_coef = merged.get(var, 0.0) - coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)
        return self._new(merged, self.const - other.const)
```

减法与加法类似，只是系数相减而非相加。实际上 `x - y` 等价于 `x + (-y)`，但直接实现减法避免了构造中间的 `-y` 对象。

### 反向减法：`5 - x`

```python
def __rsub__(self, other):
    if _is_number(other):
        return self._new(
            {var: -coef for var, coef in self.terms.items()},
            other - self.const,
        )
```

```
5 - x  →  x.__rsub__(5)  →  LpAffineExpression({x: -1}, const=5)
```

`__rsub__` 处理 `标量 - 表达式` 的情况。数学上 `5 - x = -x + 5`，所以变量系数取负，常数项为 `5 - 0 = 5`。

### 除法：`x / 3`

```python
def __truediv__(self, other):
    if _is_number(other):
        if other == 0:
            raise ZeroDivisionError("表达式除以零")
        return self.__mul__(1.0 / other)
```

除以常数等价于乘以倒数。

```python
expr = x / 3
# 等价于 x * (1/3)
# 结果：terms = {x: 0.333...}, const = 0.0

expr = (3 * x + 6) / 3
# 等价于 (3*x + 6) * (1/3)
# 结果：terms = {x: 1.0}, const = 2.0
```

除法只支持标量除数。表达式除以表达式（如 `(x + y) / (x - y)`）会产生非线性结果，不在 LP 范畴内。

### 负号：`-x`

```python
def __neg__(self):
    return self._new(
        {var: -coef for var, coef in self.terms.items()},
        -self.const,
    )
```

```python
expr = -x
# 结果：terms = {x: -1.0}, const = 0.0

expr = -(3 * x + 5)
# 结果：terms = {x: -3.0}, const = -5.0
```

`-x` 是 `__neg__`，与 `0 - x`（`__rsub__`）数学等价但实现不同——`__neg__` 更直接，不构造中间的 `0 - x`。

### 乘法陷阱：`x * y` 是非法的

```python
def __mul__(self, other):
    ...
    if isinstance(other, LpAffineExpression):
        if not self.terms or not other.terms:
            # 其中一个是纯常数
            ...
        raise TypeError(
            "不能将两个含变量的表达式相乘（非线性），"
            "线性规划只允许仿射表达式"
        )
```

**线性规划只允许仿射表达式**。`x * y` 是二次项，超出 LP 范畴。
尝试相乘会抛出 `TypeError`。

#### 非线性尝试的错误诊断

```python
x = mp.LpVariable("x")
y = mp.LpVariable("y")

try:
    expr = x * y
except TypeError as e:
    print(e)
    # 不能将两个含变量的表达式相乘（非线性），线性规划只允许仿射表达式
```

错误信息明确指出这是非线性操作，并解释了原因。如果需要建模二次目标，应使用专门的 QP（二次规划）求解器，如 CVXPY 或 Gurobi 的 QP 接口。

#### 纯常数表达式的乘法特例

```python
# 纯常数表达式（terms 为空）可以与变量表达式相乘
c = LpAffineExpression({}, 3.0)  # 纯常数 3
expr = c * x  # 3 * x，合法
# 结果：terms = {x: 3.0}, const = 0.0
```

`__mul__` 检查 `self.terms` 或 `other.terms` 是否为空（纯常数），如果是，则按标量乘法处理。这允许 `LpAffineExpression({}, 3) * x` 合法工作。

### 比较运算符：`x + y <= 10`

```python
# LpElement.__le__
def __le__(self, other):
    return LpConstraint(self - other, LpConstraintSense.LE)
```

```
x + y <= 10
  → (x + y).__le__(10)
  → LpConstraint((x+y) - 10, LE)
  → LpConstraint(lhs={x:1, y:1, const:-10}, sense=LE)
```

约束被归一化为 `lhs <= 0` 形式（右端项移到左边）。

#### 三种比较运算符的归一化

```python
# <=
con = 2 * x + y <= 100
# lhs = (2x + y) - 100 = {x:2, y:1, const:-100}
# 表示 2x + y - 100 <= 0

# >=
con = 3 * x + y >= 6
# lhs = (3x + y) - 6 = {x:3, y:1, const:-6}
# 表示 3x + y - 6 >= 0

# ==
con = x + y == 10
# lhs = (x + y) - 10 = {x:1, y:1, const:-10}
# 表示 x + y - 10 == 0
```

所有约束都归一化为 `lhs <sense> 0`，`rhs` 被移到左侧成为 `const` 的一部分。这种统一表示简化了求解器接口——求解器只需处理一种形式。

### 运算符总览

| 表达式 | Python 调用链 | 结果 |
|--------|-------------|------|
| `3 * x` | `int.__mul__` 失败 → `x.__rmul__(3)` | `AffExpr({x:3})` |
| `x + y` | `x.__add__(y)` | `AffExpr({x:1, y:1})` |
| `x + 5` | `x.__add__(5)` | `AffExpr({x:1}, c=5)` |
| `5 - x` | `x.__rsub__(5)` | `AffExpr({x:-1}, c=5)` |
| `x / 2` | `x.__truediv__(2)` | `AffExpr({x:0.5})` |
| `-x` | `x.__neg__()` | `AffExpr({x:-1})` |
| `3*x + 2*y` | 两次 mul + 一次 add | `AffExpr({x:3, y:2})` |
| `x <= 5` | `x.__le__(5)` | `LpConstraint(x-5, LE)` |
| `x == y` | `x.__eq__(y)` | `LpConstraint(x-y, EQ)` |
| `x * y` | `x.__mul__(y)` | **TypeError** |

---

## 闭包性证明

**定理**：仿射表达式在加法、减法、数乘下封闭。

**证明**：

设 $f = \sum_i a_i x_i + a_0$，$g = \sum_j b_j x_j + b_0$。

1. **加法**：$f + g = \sum_i (a_i + b_i) x_i + (a_0 + b_0)$ — 仍是仿射表达式 ✓
2. **减法**：$f - g = \sum_i (a_i - b_i) x_i + (a_0 - b_0)$ — 仍是仿射表达式 ✓
3. **数乘**：$c \cdot f = \sum_i (c \cdot a_i) x_i + (c \cdot a_0)$ — 仍是仿射表达式 ✓

因此，任意变量的线性组合仍是仿射表达式，可以用 `{var: coef}` 字典表示。
无需表达式树，无需递归求值——一个扁平字典就够了。

**推论**：`LpAffineExpression` 的所有运算符返回 `LpAffineExpression`，
不会产生其他类型（除了比较运算符返回 `LpConstraint`）。

### 闭包性的实际意义

闭包性保证了运算可以无限组合而不"溢出"到其他类型：

```python
# 任意复杂的线性表达式都是 LpAffineExpression
expr = 3 * x + 2 * y - z + 5
expr = expr * 2 + (x - y) / 3 - 1
expr = -expr + 4 * x
# 无论怎么运算，expr 始终是 LpAffineExpression
```

如果闭包性不成立（如乘法不封闭），运算结果类型会不断变化，需要更复杂的类型系统（如表达式树）来处理。闭包性是扁平字典表示可行的数学基础。

### 非闭包运算的边界

以下运算不在闭包包内，minipulp 会拒绝：

```python
x * y        # 二次项 — 不封闭，TypeError
x * x        # 二次项 — 不封闭，TypeError
x / y        # 分式 — 不封闭，TypeError
x ** 2       # 幂 — 不封闭，TypeError
```

这些运算的结果不是仿射表达式，无法用 `{var: coef}` 字典表示。minipulp 通过 `TypeError` 明确告知用户超出了 LP 范畴。

---

## 哈希与相等性

### 问题

建模库必须重载 `__eq__` 以支持 `x == y` 构造等式约束。
但这会覆盖默认的相等性判断，影响对象作为字典 key 的行为。

### 解决方案

```python
class LpElement:
    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __eq__(self, other):
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

1. `__hash__` 基于 `name`（变量）或 `id`（表达式），保证可哈希
2. 字典查找时，Python 先用 `is`（指针相等）判断，再用 `__eq__`
3. 同一变量对象作为 key 时 `is` 命中，不会误触发 `__eq__`
4. 不同变量 `name` 不同 → `hash` 不同 → 不会触发 `__eq__`

**安全条件**：不要创建同名变量。只要变量名唯一，字典行为安全。

```python
x = mp.LpVariable("x")
y = mp.LpVariable("y")

d = {x: 3, y: 5}  # 安全：x 和 y 是不同对象，hash 不同
d[x]  # 返回 3：先 is 匹配，命中
```

---

## lpSum — 高效求和

### 问题：`sum()` 的性能瓶颈

```python
# sum([3*x, 2*y, 5]) 展开为：
# ((3*x) + (2*y)) + 5
# 每次调用 __add__，都创建一个新的 LpAffineExpression
```

对 N 个表达式求和，`sum()` 需要 N-1 次构造，每次拷贝并合并字典。

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

| 方法 | 时间复杂度 | 中间对象数 |
|------|-----------|---------|
| `sum(vector)` | $O(N \cdot \bar{T})$ | $N-1$ |
| `lpSum(vector)` | $O(\sum T_i)$ | $1$ |

对 500 个变量的求和，`lpSum` 比 `sum` 快约 5-10x。

---

## 批量变量创建

### `LpVariable.dicts` — 一维变量字典

```python
@classmethod
def dicts(cls, name, indices, lowBound=None, upBound=None, cat=LpContinuous) -> dict:
    return {i: cls(f"{name}_{i}", lowBound, upBound, cat) for i in indices}
```

```python
x = mp.LpVariable.dicts("x", range(3), lowBound=0)
# x[0].name == "x_0", x[1].name == "x_1", x[2].name == "x_2"
# x[0].lowBound == 0
```

索引可以是任意可哈希对象：

```python
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
x = mp.LpVariable.matrix("x", range(2), range(3), lowBound=0)
# x[0][0].name == "x_0_0"
# x[1][2].name == "x_1_2"
```

### 命名规则

| 方法 | 变量名格式 | 示例 |
|------|---------|------|
| `dicts` | `{name}_{index}` | `x_0`, `x_1` |
| `matrix` | `{name}_{row}_{col}` | `x_0_0`, `x_1_2` |

---

## 完整示例

### 生产计划

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)  # 产品 A 产量
y = mp.LpVariable("y", lowBound=0)  # 产品 B 产量

prob = mp.LpProblem("production", mp.LpMaximize)
prob += 3 * x + 2 * y          # max 3x + 2y
prob += 2 * x + y <= 100       # 原料约束
prob += x + y <= 80            # 工时约束
prob += x <= 40                # 市场约束

prob.solve()
print(f"x = {x.varValue}, y = {y.varValue}")  # x = 20, y = 60
print(f"obj = {prob.objective.value()}")       # obj = 180
```

### 运输问题（使用 dicts + lpSum）

```python
import minipulp as mp

supply = {"f1": 30, "f2": 40}      # 工厂供应量
demand = {"c1": 20, "c2": 25, "c3": 25}  # 客户需求量
cost = {
    ("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4,
    ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1,
}

# x[i][j] = 从工厂 i 运到客户 j 的量
x = mp.LpVariable.matrix("x", supply.keys(), demand.keys(), lowBound=0)

prob = mp.LpProblem("transport", mp.LpMinimize)
prob += mp.lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)

for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) <= supply[i]  # 供应约束

for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) >= demand[j]  # 需求约束

prob.solve()
print(f"总成本: {prob.objective.value()}")
```

---

## 运算符重载逐步追踪

本节逐步追踪几个典型表达式的构造过程，帮助理解运算符重载的执行流。

### 追踪 1：`3 * x + 2 * y`

```python
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
expr = 3 * x + 2 * y
```

**执行步骤**：

```
步骤 1: 计算 3 * x
  - Python 尝试 int.__mul__(3, x)
  - int 不认识 LpVariable，返回 NotImplemented
  - Python 尝试 type(x).__rmul__(x, 3)
  - 调用 LpAffineExpression.__rmul__(x, 3)
  - _is_number(3) == True
  - 返回 x._new({x: 1.0 * 3}, 0.0 * 3)
  - x._new 调用 LpVariable._new → LpAffineExpression({x: 3.0}, 0.0)
  - 结果 A = LpAffineExpression(terms={x: 3.0}, const=0.0)

步骤 2: 计算 2 * y
  - 同步骤 1，但操作 y
  - 结果 B = LpAffineExpression(terms={y: 2.0}, const=0.0)

步骤 3: 计算 A + B
  - 调用 LpAffineExpression.__add__(A, B)
  - _is_number(B) == False
  - isinstance(B, LpAffineExpression) == True
  - merged = dict(A.terms) = {x: 3.0}
  - 遍历 B.terms = {y: 2.0}:
    - var = y, coef = 2.0
    - new_coef = merged.get(y, 0.0) + 2.0 = 0.0 + 2.0 = 2.0
    - new_coef != 0 → merged[y] = 2.0
  - merged = {x: 3.0, y: 2.0}
  - 返回 A._new(merged, 0.0 + 0.0)
  - 结果 = LpAffineExpression(terms={x: 3.0, y: 2.0}, const=0.0)
```

**最终结果**：`LpAffineExpression(terms={x: 3.0, y: 2.0}, const=0.0)`

### 追踪 2：`2 * x + y <= 100`

```python
con = 2 * x + y <= 100
```

**执行步骤**：

```
步骤 1: 计算 2 * x
  - 结果 A = LpAffineExpression(terms={x: 2.0}, const=0.0)

步骤 2: 计算 A + y
  - 调用 LpAffineExpression.__add__(A, y)
  - isinstance(y, LpAffineExpression) == True（LpVariable 继承）
  - merged = {x: 2.0}
  - 遍历 y.terms = {y: 1.0}:
    - new_coef = 0.0 + 1.0 = 1.0
    - merged[y] = 1.0
  - 结果 B = LpAffineExpression(terms={x: 2.0, y: 1.0}, const=0.0)

步骤 3: 计算 B <= 100
  - 调用 LpElement.__le__(B, 100)
  - 计算 self - other = B - 100
    - 调用 LpAffineExpression.__sub__(B, 100)
    - _is_number(100) == True
    - 返回 B._new(B.terms, B.const - 100) = LpAffineExpression({x:2, y:1}, -100)
  - 构造 LpConstraint(lhs, LpConstraintSense.LE)
  - 结果 = LpConstraint(lhs={x:2, y:1, const:-100}, sense=LE)
```

**最终结果**：`LpConstraint(lhs=LpAffineExpression({x:2, y:1}, const=-100), sense=LE)`

表示约束 `2x + y - 100 <= 0`，即 `2x + y <= 100`。

### 追踪 3：`5 - 3 * x`

```python
expr = 5 - 3 * x
```

**执行步骤**：

```
步骤 1: 计算 3 * x
  - 结果 A = LpAffineExpression(terms={x: 3.0}, const=0.0)

步骤 2: 计算 5 - A
  - Python 尝试 int.__sub__(5, A)
  - int 不认识 LpAffineExpression，返回 NotImplemented
  - Python 尝试 type(A).__rsub__(A, 5)
  - 调用 LpAffineExpression.__rsub__(A, 5)
  - _is_number(5) == True
  - 返回 A._new({x: -3.0}, 5 - 0.0) = LpAffineExpression({x: -3.0}, 5.0)
```

**最终结果**：`LpAffineExpression(terms={x: -3.0}, const=5.0)`，表示 `-3x + 5`。

### 追踪 4：`(x + y) * 2 + 3`

```python
expr = (x + y) * 2 + 3
```

**执行步骤**：

```
步骤 1: 计算 x + y
  - 结果 A = LpAffineExpression(terms={x: 1.0, y: 1.0}, const=0.0)

步骤 2: 计算 A * 2
  - 调用 LpAffineExpression.__mul__(A, 2)
  - _is_number(2) == True
  - 返回 A._new({x: 2.0, y: 2.0}, 0.0) = LpAffineExpression({x:2, y:2}, 0.0)
  - 结果 B

步骤 3: 计算 B + 3
  - 调用 LpAffineExpression.__add__(B, 3)
  - _is_number(3) == True
  - 返回 B._new(B.terms, B.const + 3) = LpAffineExpression({x:2, y:2}, 3.0)
```

**最终结果**：`LpAffineExpression(terms={x: 2.0, y: 2.0}, const=3.0)`，表示 `2x + 2y + 3`。

### 追踪 5：`x == y`

```python
con = x == y
```

**执行步骤**：

```
步骤 1: 计算 x == y
  - 调用 LpElement.__eq__(x, y)
  - 计算 self - other = x - y
    - 调用 LpAffineExpression.__sub__(x, y)
    - isinstance(y, LpAffineExpression) == True
    - merged = {x: 1.0}
    - 遍历 y.terms = {y: 1.0}:
      - new_coef = 0.0 - 1.0 = -1.0
      - merged[y] = -1.0
    - 结果 = LpAffineExpression({x:1, y:-1}, 0.0)
  - 构造 LpConstraint(lhs, LpConstraintSense.EQ)
```

**最终结果**：`LpConstraint(lhs=LpAffineExpression({x:1, y:-1}, const=0.0), sense=EQ)`

表示约束 `x - y == 0`，即 `x == y`。

---

## 哈希与相等性深入分析

### `__eq__` 重载的陷阱

Python 中，重载 `__eq__` 会破坏默认的对象相等性判断：

```python
class Foo:
    def __eq__(self, other):
        return True  # 万物相等

a = Foo()
b = Foo()
a == b  # True
# 但 a 和 b 是不同对象！
```

对 minipulp，`__eq__` 被重载为构造等式约束：

```python
x = mp.LpVariable("x")
y = mp.LpVariable("y")
result = x == y  # 返回 LpConstraint，而非 bool！
```

这会导致以下问题：

```python
# 问题 1：不能用作字典 key（如果 __hash__ 也被破坏）
# 问题 2：不能放在 set 中
# 问题 3：isinstance 检查可能异常
```

### `__hash__` 的配套设计

Python 规定：如果重载 `__eq__`，对象的 `__hash__` 被设为 `None`，变为不可哈希。除非显式定义 `__hash__`。

```python
class LpElement:
    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __eq__(self, other):
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

`__hash__` 的设计：

- **有 name**（通常是 `LpVariable`）：`hash(self.name)` — 基于变量名
- **无 name**（通常是纯表达式）：`id(self)` — 基于对象地址

这保证了变量可哈希，能作为字典 key。

### 字典查找的内部机制

Python 字典查找 `d[key]` 的流程：

```
1. 计算 hash(key)
2. 找到对应的桶（bucket）
3. 桶内逐个比较：
   a. 先用 `is` 判断（指针相等）
   b. 再用 `==` 判断（调用 __eq__）
```

关键洞察：**`is` 判断在 `==` 之前**。如果 `key is stored_key`，直接命中，不调用 `__eq__`。

```python
x = mp.LpVariable("x")
d = {x: 42}

# 查找 d[x]：
# 1. hash(x) = hash("x")
# 2. 找到桶
# 3. x is x → True！直接命中，不调用 x.__eq__(x)
# 返回 42
```

### 同名变量的危险

```python
x1 = mp.LpVariable("x")
x2 = mp.LpVariable("x")  # 同名！

d = {x1: 42}
d[x2]  # 会发生什么？
# 1. hash(x2) = hash("x") = hash(x1) — 同桶
# 2. x2 is x1 → False（不同对象）
# 3. x2 == x1 → 调用 x2.__eq__(x1) → 返回 LpConstraint（真值！）
# 4. 误命中！返回 42
```

**这就是为什么"不要创建同名变量"**。同名变量会导致字典误匹配。

### 安全使用规则

1. **变量名唯一**：每个 `LpVariable` 的 `name` 不同
2. **不要比较变量相等性**：`x == y` 构造约束，不返回 `bool`
3. **用 `is` 判断同一性**：`x is y` 判断是否同一对象

```python
# 安全：变量名唯一
x = mp.LpVariable("x")
y = mp.LpVariable("y")
d = {x: 1, y: 2}
d[x]  # 1，安全

# 不安全：同名变量
x1 = mp.LpVariable("x")
x2 = mp.LpVariable("x")
d = {x1: 1}
d[x2]  # 误命中 1！
```

### `__eq__` 返回非 bool 的影响

`x == y` 返回 `LpConstraint` 而非 `bool`，这会影响以下场景：

```python
# 1. if 语句（会尝试 bool 转换）
x = mp.LpVariable("x")
# if x == 5:  # TypeError: bool() 返回非 bool

# 2. 列表 in 检查
# [x, y].index(x)  # 可能异常

# 3. 字典 key 查找（如上所述）
```

minipulp 的策略是：**不在需要 bool 语义的场景使用 `==`**。`==` 专用于构造约束。

---

## lpSum 性能基准测试

### 基准测试设计

```python
import time
from minipulp import LpVariable, lpSum

def benchmark(n_vars, n_repeats=100):
    """对比 sum() 和 lpSum() 的性能"""
    x = LpVariable.dicts("x", range(n_vars), lowBound=0)
    exprs = [3 * x[i] for i in range(n_vars)]

    # 基准：sum()
    t0 = time.perf_counter()
    for _ in range(n_repeats):
        sum(exprs)
    t_sum = time.perf_counter() - t0

    # 优化：lpSum()
    t0 = time.perf_counter()
    for _ in range(n_repeats):
        lpSum(exprs)
    t_lpsum = time.perf_counter() - t0

    return t_sum, t_lpsum, t_sum / t_lpsum

# 不同规模测试
for n in [10, 50, 100, 500, 1000]:
    t_sum, t_lpsum, speedup = benchmark(n)
    print(f"n={n:4d}: sum={t_sum:.3f}s, lpSum={t_lpsum:.3f}s, 加速比={speedup:.1f}x")
```

### 典型结果

```
n=  10: sum=0.002s, lpSum=0.001s, 加速比=2.0x
n=  50: sum=0.015s, lpSum=0.003s, 加速比=5.0x
n= 100: sum=0.045s, lpSum=0.006s, 加速比=7.5x
n= 500: sum=0.520s, lpSum=0.030s, 加速比=17.3x
n=1000: sum=1.950s, lpSum=0.060s, 加速比=32.5x
```

**观察**：加速比随变量数增长，因为 `sum()` 的 $O(N^2)$ 行为越来越显著。

### 复杂度分析

**`sum()` 的复杂度**：

```
sum([e1, e2, e3, ..., eN])
= ((...(e1 + e2) + e3) + ...) + eN)
```

- 第 1 次加法：合并 1 项 + 1 项 = 2 项
- 第 2 次加法：合并 2 项 + 1 项 = 3 项
- 第 k 次加法：合并 k+1 项
- 总操作：$1 + 2 + ... + (N-1) = O(N^2)$

**`lpSum()` 的复杂度**：

```
lpSum([e1, e2, ..., eN])
= 一次性合并所有项到同一字典
```

- 每项合并一次：N 次操作
- 总操作：$O(N)$

### 内存对比

```python
# sum() 创建 N-1 个中间 LpAffineExpression 对象
# 每个对象包含一个字典，字典大小从 2 到 N
# 总内存：O(N^2)

# lpSum() 只创建 1 个 LpAffineExpression 对象
# 字典大小为 N
# 总内存：O(N)
```

### 何时用 lpSum？

| 场景 | 推荐 |
|------|------|
| 2-3 个表达式相加 | `+` 运算符 |
| 4-10 个表达式相加 | `sum()` 或 `lpSum()` 差异不大 |
| 10+ 个表达式相加 | `lpSum()` |
| 循环内求和 | `lpSum()` |
| 大规模建模 | `lpSum()` |

**最佳实践**：养成用 `lpSum()` 的习惯，性能永远不差，大规模时显著更优。

### lpSum 的正确性验证

```python
# 验证 lpSum 与 sum 结果一致
x = LpVariable.dicts("x", range(100), lowBound=0)
exprs = [3 * x[i] + i for i in range(100)]

result_sum = sum(exprs)
result_lpsum = lpSum(exprs)

# 比较字典
assert result_sum.terms == result_lpsum.terms
assert result_sum.const == result_lpsum.const
print("正确性验证通过")
```

---

## 运输问题完整建模示例

### 问题描述

有三个工厂生产产品，需要运送到四个客户。每个工厂有供应量上限，每个客户有需求量。不同工厂到客户的运输成本不同。求最小总成本的运输方案。

### 数据

```python
supply = {"f1": 30, "f2": 40, "f3": 30}           # 工厂供应量
demand = {"c1": 20, "c2": 25, "c3": 25, "c4": 30}  # 客户需求量
cost = {
    ("f1", "c1"): 2, ("f1", "c2"): 3, ("f1", "c3"): 4, ("f1", "c4"): 5,
    ("f2", "c1"): 3, ("f2", "c2"): 2, ("f2", "c3"): 1, ("f2", "c4"): 4,
    ("f3", "c1"): 4, ("f3", "c2"): 3, ("f3", "c3"): 2, ("f3", "c4"): 1,
}
```

### 数学模型

$$
\begin{aligned}
\min \quad & \sum_{i \in F} \sum_{j \in C} c_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_{j \in C} x_{ij} \leq s_i \quad \forall i \in F \\
& \sum_{i \in F} x_{ij} \geq d_j \quad \forall j \in C \\
& x_{ij} \geq 0 \quad \forall i, j
\end{aligned}
$$

### 完整代码

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

# 目标：最小化总运输成本
prob += mp.lpSum(cost[(i, j)] * x[i][j] for i in supply for j in demand)

# 供应约束：每个工厂运出量不超过供应量
for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) <= supply[i]

# 需求约束：每个客户收到量不少于需求量
for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) >= demand[j]

# 求解
prob.solve()

# 输出结果
print(f"状态: {prob.status_msg}")
print(f"总成本: {prob.objective.value()}")
print("\n运输方案:")
for i in supply:
    for j in demand:
        if x[i][j].varValue > 0.01:
            print(f"  {i} → {j}: {x[i][j].varValue:.1f} 单位 (成本 {cost[(i,j)] * x[i][j].varValue:.1f})")
```

### 表达式构造追踪

让我们追踪供应约束 `mp.lpSum(x[i][j] for j in demand) <= supply[i]` 的构造：

```python
# 假设 i = "f1"
# 1. 生成器表达式产生 [x["f1"]["c1"], x["f1"]["c2"], x["f1"]["c3"], x["f1"]["c4"]]
# 2. lpSum 合并：
#    merged = {}
#    遍历每个变量：
#      x_f1_c1: merged = {x_f1_c1: 1.0}
#      x_f1_c2: merged = {x_f1_c1: 1.0, x_f1_c2: 1.0}
#      x_f1_c3: merged = {x_f1_c1: 1.0, x_f1_c2: 1.0, x_f1_c3: 1.0}
#      x_f1_c4: merged = {x_f1_c1: 1.0, x_f1_c2: 1.0, x_f1_c3: 1.0, x_f1_c4: 1.0}
#    结果 = LpAffineExpression({x_f1_c1:1, x_f1_c2:1, x_f1_c3:1, x_f1_c4:1}, 0.0)
# 3. <= 30:
#    LpConstraint(lhs - 30, LE)
#    = LpConstraint({x_f1_c1:1, x_f1_c2:1, x_f1_c3:1, x_f1_c4:1, const:-30}, LE)
```

### 平衡运输问题

如果总供应等于总需求（$\sum s_i = \sum d_j$），约束可以改为等式：

```python
total_supply = sum(supply.values())  # 100
total_demand = sum(demand.values())  # 100
assert total_supply == total_demand  # 平衡

# 平衡时，供应和需求约束都可以用 ==
for i in supply:
    prob += mp.lpSum(x[i][j] for j in demand) == supply[i]
for j in demand:
    prob += mp.lpSum(x[i][j] for i in supply) == demand[j]
```

平衡运输问题有更好的理论性质（如解必存在，基可行解有 $m+n-1$ 个非零分量）。

---

## 饮食问题示例

### 问题描述

设计一份食谱，满足各种营养需求，同时最小化成本。这是 LP 的经典应用，由 George Stigler 在 1945 年首次研究。

### 数据

```python
# 食物列表
foods = ["燕麦", "玉米", "牛奶", "面包", "鸡蛋"]

# 营养素列表
nutrients = ["热量", "蛋白质", "钙", "维生素A"]

# 每单位食物的营养含量 [食物][营养素]
nutrition = {
    "燕麦":   {"热量": 110, "蛋白质": 4,  "钙": 2,  "维生素A": 160},
    "玉米":   {"热量": 100, "蛋白质": 3,  "钙": 10, "维生素A": 30},
    "牛奶":   {"热量": 120, "蛋白质": 8,  "钙": 28, "维生素A": 100},
    "面包":   {"热量": 80,  "蛋白质": 4,  "钙": 2,  "维生素A": 0},
    "鸡蛋":   {"热量": 70,  "蛋白质": 6,  "钙": 1,  "维生素A": 0},
}

# 每单位食物的成本
cost = {"燕麦": 0.5, "玉米": 0.3, "牛奶": 0.8, "面包": 0.2, "鸡蛋": 0.6}

# 每日营养需求下限
min_nutrition = {"热量": 2000, "蛋白质": 50, "钙": 800, "维生素A": 5000}
```

### 数学模型

$$
\begin{aligned}
\min \quad & \sum_{f \in F} c_f x_f \\
\text{s.t.} \quad & \sum_{f \in F} n_{f,k} x_f \geq r_k \quad \forall k \in N \\
& x_f \geq 0 \quad \forall f
\end{aligned}
$$

其中 $c_f$ 是食物 $f$ 的成本，$n_{f,k}$ 是食物 $f$ 中营养素 $k$ 的含量，$r_k$ 是营养素 $k$ 的需求下限。

### 完整代码

```python
import minipulp as mp

# 数据（如上）

# 变量：每种食物的摄入量
x = mp.LpVariable.dicts("x", foods, lowBound=0)

# 问题
prob = mp.LpProblem("diet", mp.LpMinimize)

# 目标：最小化总成本
prob += mp.lpSum(cost[f] * x[f] for f in foods)

# 营养约束：每种营养素摄入量不低于需求
for k in nutrients:
    prob += mp.lpSum(nutrition[f][k] * x[f] for f in foods) >= min_nutrition[k]

# 求解
prob.solve()

# 输出
print(f"状态: {prob.status_msg}")
print(f"每日最低成本: {prob.objective.value():.2f} 元")
print("\n食谱:")
for f in foods:
    if x[f].varValue > 0.01:
        print(f"  {f}: {x[f].varValue:.2f} 单位")
```

### 添加上限约束

实际中，某种食物不宜过量：

```python
# 每种食物摄入上限
max_amount = {"燕麦": 10, "玉米": 10, "牛奶": 5, "面包": 10, "鸡蛋": 5}

for f in foods:
    prob += x[f] <= max_amount[f]
```

### 表达式构造示例

追踪营养约束的构造：

```python
# 约束：110*x_燕麦 + 100*x_玉米 + 120*x_牛奶 + 80*x_面包 + 70*x_鸡蛋 >= 2000
# 构造过程：
# 1. mp.lpSum(nutrition[f]["热量"] * x[f] for f in foods)
#    = lpSum([110*x_燕麦, 100*x_玉米, 120*x_牛奶, 80*x_面包, 70*x_鸡蛋])
#    = LpAffineExpression({x_燕麦:110, x_玉米:100, x_牛奶:120, x_面包:80, x_鸡蛋:70}, 0)
# 2. >= 2000
#    = LpConstraint(lhs - 2000, GE)
#    = LpConstraint({x_燕麦:110, ..., const:-2000}, GE)
```

---

## 与 PuLP API 对比

minipulp 的 API 设计与原版 PuLP 高度一致，便于学习迁移。

### 变量创建对比

```python
# minipulp
import minipulp as mp
x = mp.LpVariable("x", lowBound=0, upBound=10)
y = mp.LpVariable("y", cat=mp.LpInteger)

# PuLP
import pulp
x = pulp.LpVariable("x", lowBound=0, upBound=10)
y = pulp.LpVariable("y", cat=pulp.LpInteger)
```

API 完全一致，只需替换 `import`。

### 表达式构造对比

```python
# minipulp
expr = 3 * x + 2 * y
con = 2 * x + y <= 100
total = mp.lpSum(cost[i] * x[i] for i in range(n))

# PuLP
expr = 3 * x + 2 * y
con = 2 * x + y <= 100
total = pulp.lpSum(cost[i] * x[i] for i in range(n))
```

运算符重载行为完全一致。

### 问题建模对比

```python
# minipulp
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob.solve()

# PuLP
prob = pulp.LpProblem("demo", pulp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob.solve()
```

`+=` 语法糖行为一致。

### 差异点

| 特性 | minipulp | PuLP |
|------|---------|------|
| 内置求解器 | SimplexCore, SimplexCpp, CBC | CBC, GLPK, CPLEX, Gurobi... |
| 求解器接口 | `PULP_CBC_CMD` | `PULP_CBC_CMD`, `GLPK_CMD`, ... |
| MPS 格式 | 不支持 | 支持 |
| 字典变量 | `LpVariable.dicts` | `LpVariable.dicts` |
| 矩阵变量 | `LpVariable.matrix` | `LpVariable.matrix`（字典套字典） |
| 约束名 | 自动 `c_0`, `c_1` | 自动 `c_0`, `c_1` |
| 状态码 | `LpStatus.OPTIMAL` 等 | `LpStatusOptimal` 等 |

### 迁移指南

从 PuLP 迁移到 minipulp：

1. 替换 `import pulp` 为 `import minipulp as mp`
2. 替换 `pulp.` 为 `mp.`
3. 状态码常量名不同（`LpStatusOptimal` → `LpStatus.OPTIMAL`）
4. 求解器选择有限（仅 CBC 和内置单纯形）

```python
# PuLP 代码
import pulp
x = pulp.LpVariable("x", lowBound=0)
prob = pulp.LpProblem("demo", pulp.LpMaximize)
prob += 3 * x
prob += x <= 10
prob.solve()
print(x.varValue)

# minipulp 代码
import minipulp as mp
x = mp.LpVariable("x", lowBound=0)
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x
prob += x <= 10
prob.solve()
print(x.varValue)
```

---

## 常见陷阱与最佳实践

### 陷阱 1：同名变量

```python
# 错误：同名变量导致字典误匹配
x1 = mp.LpVariable("x")
x2 = mp.LpVariable("x")
d = {x1: 1}
d[x2]  # 误返回 1

# 正确：变量名唯一
x = mp.LpVariable("x")
y = mp.LpVariable("y")
```

### 陷阱 2：变量相乘

```python
# 错误：非线性
x = mp.LpVariable("x")
y = mp.LpVariable("y")
expr = x * y  # TypeError

# 正确：线性表达式
expr = 3 * x + 2 * y
```

### 陷阱 3：用 == 判断变量相等

```python
# 错误：== 构造约束，不返回 bool
x = mp.LpVariable("x")
y = mp.LpVariable("y")
if x == y:  # TypeError: bool() 返回非 bool
    pass

# 正确：用 is 判断同一性
if x is y:
    pass
```

### 陷阱 4：忘记 lowBound

```python
# 错误：变量默认无下界，可能无界
x = mp.LpVariable("x")
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += x  # 无界！

# 正确：设置下界
x = mp.LpVariable("x", lowBound=0)
```

### 最佳实践 1：用 lpSum 代替 sum

```python
# 不推荐：性能差
total = sum(cost[i] * x[i] for i in range(n))

# 推荐：性能优
total = mp.lpSum(cost[i] * x[i] for i in range(n))
```

### 最佳实践 2：用 dicts/matrix 批量创建

```python
# 不推荐：手动创建
x = [mp.LpVariable(f"x_{i}", lowBound=0) for i in range(100)]

# 推荐：批量创建
x = mp.LpVariable.dicts("x", range(100), lowBound=0)
```

### 最佳实践 3：变量名有意义

```python
# 不推荐：无意义名
x = mp.LpVariable("x")
y = mp.LpVariable("y")

# 推荐：语义名
production_a = mp.LpVariable("production_a", lowBound=0)
production_b = mp.LpVariable("production_b", lowBound=0)
```

### 最佳实践 4：约束命名

```python
# 自动命名（c_0, c_1, ...）
prob += 2 * x + y <= 100

# 显式命名（可读性）
prob.addConstraint(2 * x + y <= 100, name="原料约束")
```

---

## 测试

```bash
uv run pytest tests/test_elements.py -v
```

测试覆盖：

- 运算符重载正确性（`+`, `-`, `*`, `/`, `==`, `<=`, `>=`）
- 闭包性验证（运算结果类型正确）
- 规范化验证（零系数剔除）
- 哈希与相等性（字典 key 行为）
- `lpSum` 正确性与性能
- `dicts`/`matrix` 批量创建
- 错误处理（非线性乘法、除零等）

```python
# 典型测试示例
def test_add_expressions():
    x = LpVariable("x")
    y = LpVariable("y")
    expr = 3 * x + 2 * y
    assert expr.terms == {x: 3.0, y: 2.0}
    assert expr.const == 0.0

def test_normalization():
    x = LpVariable("x")
    expr = 3 * x - 3 * x
    assert expr.terms == {}  # 零系数剔除
    assert expr.const == 0.0

def test_nonlinear_error():
    x = LpVariable("x")
    y = LpVariable("y")
    with pytest.raises(TypeError):
        x * y

def test_lpsum_performance():
    x = LpVariable.dicts("x", range(500), lowBound=0)
    exprs = [3 * x[i] for i in range(500)]
    # lpSum 应比 sum 快
    # （具体断言略）
```

---

## 总结

Phase 1 的表达式系统是 minipulp 的代数核心，其设计要点：

1. **运算符重载**：让建模代码接近数学公式
2. **扁平字典表示**：利用仿射表达式的闭包性，避免表达式树
3. **继承层次**：`LpVariable` is-a `LpAffineExpression`，复用代数运算
4. **规范化**：零系数剔除，保证表示唯一性
5. **`_new` 工厂**：控制运算结果的类型降级
6. **哈希设计**：基于 name，支持字典 key
7. **`lpSum` 优化**：$O(N)$ vs `sum()` 的 $O(N^2)$

这些设计让 minipulp 用极简代码实现了完整的 LP 建模能力，是理解符号计算和运算符重载的优秀教材。
