# LP 文件格式规范

> 建模层与求解层的通信协议：CPLEX LP 格式。
>
> 本文是 minipulp 文件 IO 层的设计文档。我们将从最基础的格式动机出发，
> 逐步讲解 CPLEX LP 格式的每一段、每一行的语法，并说明 minipulp 的
> `write_lp` 如何将内部的字典表示序列化为这个格式。

---

## 目录

1. [为什么需要文件格式](#为什么需要文件格式)
2. [LP 格式的历史与定位](#lp-格式的历史与定位)
3. [格式整体结构](#格式整体结构)
4. [各段详解](#各段详解)
5. [目标段详解](#目标段详解)
6. [约束段详解](#约束段详解)
7. [Bounds 段详解](#bounds-段详解)
8. [General / Integer 段详解](#general--integer-段详解)
9. [Binary 段详解](#binary-段详解)
10. [End 段详解](#end-段详解)
11. [注释与空白规则](#注释与空白规则)
12. [系数格式化规则](#系数格式化规则)
13. [归一化约定](#归一化约定)
14. [minipulp 的 write_lp 实现](#minipulp-的-write_lp-实现)
15. [完整示例](#完整示例)
16. [与 CBC 求解器的通信流程](#与-cbc-求解器的通信流程)
17. [MPS 格式对比](#mps-格式对比)
18. [其他格式简介](#其他格式简介)
19. [格式解析的边界情况](#格式解析的边界情况)
20. [工程考量](#工程考量)
21. [总结](#总结)

---

## 为什么需要文件格式

建模库（minipulp）和求解器（CBC、GLPK）是独立程序，需要通过文件交换问题描述。LP 格式是 CPLEX 定义的人类可读格式，是 OR 生态最通用的"语言"。

### 建模与求解的分离

优化生态有一个重要原则：**建模与求解分离**。

```
建模库（minipulp, PuLP, Pyomo）  ←→  求解器（CBC, GLPK, Gurobi, CPLEX）
```

建模库负责把用户的高级描述（变量、约束、目标）转换成求解器能理解的格式。求解器负责实际求解。两者通过文件或 API 通信。

### 为什么用文件而非 API

1. **通用性**：任何求解器都能读 LP 文件，不需要专门 API。
2. **可调试**：LP 文件是人类可读的，可以手动检查问题。
3. **可复现**：保存 LP 文件就能复现求解过程。
4. **简单**：不需要链接求解器库，只需启动子进程。

### 通信流程

```
minipulp ──write_lp──→ model.lp ──cbc──→ model.sol ──parse──→ 回填
```

1. minipulp 把问题写成 `model.lp` 文件。
2. 启动 CBC 子进程，传入 `model.lp`。
3. CBC 求解，输出 `model.sol`（解文件）。
4. minipulp 解析 `model.sol`，把解值回填到 `LpVariable.varValue`。

---

## LP 格式的历史与定位

### CPLEX LP 格式的起源

LP 格式由 CPLEX 公司（现属 IBM）定义，是其商业求解器 CPLEX Optimizer 的输入格式。由于 CPLEX 的影响力，这个格式成为事实标准，被开源求解器（CBC、GLPK、HiGHS）广泛支持。

### 与 MPS 格式的关系

MPS（Mathematical Programming System）是更古老的格式，起源于 1960s 的 IBM 大型机。MPS 是列导向的固定列格式，机器友好但人类难读。LP 格式是行导向的自由格式，人类友好但解析稍慢。

### LP 格式的定位

- **人类可读**：可以用文本编辑器打开检查。
- **行导向**：每行一个约束或一个界，易于理解。
- **自由格式**：字段由空格分隔，不依赖列位置。
- **支持所有 LP 元素**：目标、约束、界、整数变量、二元变量。

---

## 格式整体结构

一个 LP 文件由若干段（section）组成，每段以一个关键字开头：

```
\ Project name: demo          ← 注释行（\ 开头）
Maximize                      ← 目标段
  obj: 3 x + 2 y
Subject To                    ← 约束段
  c_0: 2 x + 1 y <= 100
  c_1: 1 x + 1 y <= 80
Bounds                        ← 变量界段
  x >= 0
  y >= 0
General                       ← 整数变量段（可选）
  z
Binary                        ← 二元变量段（可选）
  b
End                           ← 结束标记
```

### 段的顺序

LP 格式要求段按特定顺序出现：

1. 注释行（可选，`\` 开头）
2. `Maximize` 或 `Minimize`（目标段，必需）
3. `Subject To`（约束段，可选）
4. `Bounds`（界段，可选）
5. `General` 或 `Integer`（整数变量段，可选）
6. `Binary`（二元变量段，可选）
7. `End`（结束标记，必需）

### 段的可选性

- 目标段：必需（没有目标的问题无法求解）。
- 约束段：可选（无约束问题可能是无界的）。
- 界段：可选（省略时所有变量默认 `>= 0`）。
- 整数段：可选（省略时所有变量连续）。
- 二元段：可选（省略时无二元变量）。

---

## 各段详解

下面逐段讲解 LP 格式的语法。每段给出关键字、语法、示例和注意事项。

### 段一览表

| 段 | 关键字 | 必需 | 作用 |
|----|--------|------|------|
| 注释 | `\` | 否 | 人类可读的注释 |
| 目标 | `Maximize` / `Minimize` | 是 | 定义目标函数 |
| 约束 | `Subject To` | 否 | 定义约束条件 |
| 界 | `Bounds` | 否 | 定义变量上下界 |
| 整数 | `General` / `Integer` | 否 | 声明整数变量 |
| 二元 | `Binary` | 否 | 声明 0/1 变量 |
| 结束 | `End` | 是 | 文件结束标记 |

---

## 目标段详解

### 语法

```
Maximize
  obj: <表达式>
```

或

```
Minimize
  obj: <表达式>
```

- `Maximize` / `Minimize`：关键字，独占一行。
- `obj:`：目标行名，可任意（有些求解器要求唯一）。
- `<表达式>`：仿射表达式，如 `3 x + 2 y` 或 `3 x + 2 y + 5`。

### 示例

```
Maximize
  obj: 3 x + 2 y
```

```
Minimize
  cost: 5 x1 + 3 x2 + 7 x3
```

### 系数省略规则

- 系数 1 可省略：`x` 等价于 `1 x`。
- 系数 -1 写成 `-x` 或 `- 1 x`。
- 系数 0 的项不应出现（规范化要求）。

### 常数项

目标函数可以包含常数项：

```
Maximize
  obj: 3 x + 2 y + 5
```

这表示最大化 $3x + 2y + 5$。常数项不影响最优解的位置，只影响最优值。

### 多行目标

长目标可以分成多行（虽然不常见）：

```
Maximize
  obj: 3 x + 2 y
    + 4 z + 5 w
```

有些求解器支持，有些不支持。minipulp 总是写在一行。

---

## 约束段详解

### 语法

```
Subject To
  <约束名>: <表达式> <方向> <右端项>
```

- `Subject To`：关键字，独占一行。也可简写为 `s.t.` 或 `ST`（部分求解器支持）。
- `<约束名>:`：约束名后跟冒号，可任意。
- `<表达式>`：仿射表达式。
- `<方向>`：`<=`、`>=` 或 `=`。
- `<右端项>`：常数。

### 示例

```
Subject To
  c_0: 2 x + 1 y <= 100
  c_1: x - y >= 2
  c_2: x + y = 10
```

### 方向符

| 方向 | 含义 | 数学 |
|------|------|------|
| `<=` | 小于等于 | $\leq$ |
| `>=` | 大于等于 | $\geq$ |
| `=`  | 等于 | $=$ |

### 右端项

右端项必须是常数，不能含变量。如果原约束是 $2x + y \leq 100$，写成：

```
  c_0: 2 x + 1 y <= 100
```

如果原约束是 $2x + y - 100 \leq 0$（内部表示），导出时把常数移到右边：

```
  c_0: 2 x + 1 y <= 100
```

### 约束名

约束名是可选的（部分求解器允许省略），但建议总是提供：

```
  c_0: 2 x + y <= 100    # 有名
  2 x + y <= 100         # 无名（部分求解器支持）
```

minipulp 自动生成约束名 `c_0`, `c_1`, ...。

### 范围约束

某些求解器支持范围约束（range constraint），用一个约束表示 $l \leq expr \leq u$：

```
  c_0: 2 x + y ~ 5
```

其中 `~` 表示范围，下界和上界在单独的 `RANGES` 段定义。minipulp 不使用范围约束，总是拆成两个独立约束。

---

## Bounds 段详解

### 语法

```
Bounds
  <界声明>
```

界声明有多种形式：

### 1. 只有下界

```
  x >= 0
```

变量 $x$ 的下界是 0，上界为正无穷。

### 2. 只有上界

```
  y <= 10
```

变量 $y$ 的上界是 10，下界为负无穷。

### 3. 双界

```
  0 <= z <= 5
```

变量 $z$ 的下界是 0，上界是 5。

### 4. 无界（自由变量）

```
  w free
```

变量 $w$ 无上下界（自由变量）。

### 5. 等于某值

```
  v = 3
```

变量 $v$ 固定为 3。这等价于两个约束 $v \geq 3$ 和 $v \leq 3$，但用 Bounds 段更简洁。

### 默认界

**省略 Bounds 段时，所有变量默认 `>= 0`。**

这是 LP 格式的一个重要约定。如果变量可以是负的，必须显式声明 `x free` 或 `x >= -inf`。

### 示例

```
Bounds
  x >= 0              ← 只有下界
  y <= 10             ← 只有上界
  0 <= z <= 5         ← 双界
  w free              ← 无界（自由变量）
  v = 3               ← 固定值
  -inf <= a <= inf    ← 等价于 free
End
```

### 界的数学含义

| 声明 | 数学含义 |
|------|----------|
| `x >= l` | $x \geq l$ |
| `x <= u` | $x \leq u$ |
| `l <= x <= u` | $l \leq x \leq u$ |
| `x free` | $x \in \mathbb{R}$ |
| `x = v` | $x = v$ |

---

## General / Integer 段详解

### 语法

```
General
  <变量名1>
  <变量名2>
  ...
```

或

```
Integer
  <变量名1>
  <变量名2>
  ...
```

`General` 和 `Integer` 是同义词，都声明整数变量。

### 示例

```
General
  z1
  z2
  z3
```

或一行写多个（部分求解器支持）：

```
General
  z1 z2 z3
```

### 含义

声明为整数的变量，求解时只能取整数值。例如 `z1` 如果下界是 0 上界是 5，求解时只能取 0, 1, 2, 3, 4, 5。

### 与 Bounds 的交互

整数变量的界仍由 Bounds 段定义。`General` 段只声明变量是整数，不定义界：

```
Bounds
  0 <= z <= 5
General
  z
```

这表示 $z \in \{0, 1, 2, 3, 4, 5\}$。

---

## Binary 段详解

### 语法

```
Binary
  <变量名1>
  <变量名2>
  ...
```

### 示例

```
Binary
  b1
  b2
```

### 含义

声明为二元的变量，只能取 0 或 1。等价于整数变量加上界 0 和 1：

```
Bounds
  0 <= b1 <= 1
General
  b1
```

但 `Binary` 段更简洁，且求解器可能对二元变量有专门优化。

### 与 General 的关系

`Binary` 段是 `General` 段的特例。一个变量不应同时出现在两个段中。

---

## End 段详解

### 语法

```
End
```

`End` 关键字独占一行，标记文件结束。

### 可选性

有些求解器不要求 `End`（文件结束就是结束），但建议总是提供以保证兼容性。minipulp 总是写 `End`。

---

## 注释与空白规则

### 注释

以 `\` 开头的行是注释，被求解器忽略：

```
\ This is a comment
\ Project name: demo
Maximize
  obj: 3 x + 2 y
```

通常第一行是 `\ Project name: ...` 注释，标识问题名称。

### 空白

- 段关键字（`Maximize`, `Subject To` 等）必须独占一行。
- 行内用空格分隔 token，数量不限。
- 缩进可选，但建议 2 空格缩进提高可读性。
- 空行被忽略。

### 大小写

- 段关键字大小写敏感：`Maximize` 不能写成 `maximize`（部分求解器宽松，但建议严格）。
- 变量名大小写敏感：`x` 和 `X` 是不同变量。

### 变量名规则

变量名由字母、数字、下划线组成，不能以数字开头：

```
  x          ← 合法
  x_1        ← 合法
  var_name   ← 合法
  1x         ← 非法（以数字开头）
  x-y        ← 非法（含减号，会被解析为 x - y）
```

---

## 系数格式化规则

minipulp 在导出 LP 文件时，需要把浮点系数格式化成字符串。

### 整数 vs 浮点

```python
def _format_coef(coef: float) -> str:
    """系数格式化：整数输出 3，浮点输出 3.5。"""
    if coef == int(coef):
        return str(int(coef))
    return str(coef)
```

- 整数值的系数输出为整数：`3.0` → `"3"`。
- 浮点值输出为浮点：`3.5` → `"3.5"`。

### 符号处理

```python
def _format_terms(terms: dict) -> str:
    if not terms:
        return "0"
    parts = []
    for var, coef in terms.items():
        if coef == 1.0:
            parts.append(f"+ {var.name}")           # + x
        elif coef == -1.0:
            parts.append(f"- {var.name}")           # - y
        elif coef < 0:
            parts.append(f"- {_format_coef(abs(coef))} {var.name}")  # - 3 z
        else:
            parts.append(f"+ {_format_coef(coef)} {var.name}")      # + 2 w
    s = " ".join(parts)
    if s.startswith("+ "):
        s = s[2:]                                    # 去掉开头的 "+ "
    return s
```

### 格式化示例

| 内部表示 | 导出字符串 |
|----------|-----------|
| `{x: 1}` | `x` |
| `{x: -1}` | `- x` |
| `{x: 3}` | `3 x` |
| `{x: -3}` | `- 3 x` |
| `{x: 3, y: 2}` | `3 x + 2 y` |
| `{x: 3, y: -2}` | `3 x - 2 y` |
| `{x: -3, y: -2}` | `- 3 x - 2 y` |
| `{x: 1, y: 1}` | `x + y` |
| `{}` | `0` |

### 系数 1 的省略

系数 1 省略不写：

- `1 x` → `x`
- `-1 x` → `- x`

这让 LP 文件更简洁。

---

## 归一化约定

minipulp 内部和 LP 文件的约束表示有一个关键差异：**常数项的位置**。

### 内部表示

minipulp 把约束存为 `lhs (<=|==|>=) 0` 的齐次形式：

```python
# 内部：3x + 2y - 100 <= 0
LpConstraint(
    terms={x: 3, y: 2},
    const=-100,          # 常数项在左边
    sense=LE
)
```

即 `LpAffineExpression({x: 3, y: 2}, const=-100)`，表示 $3x + 2y - 100$，约束是 $3x + 2y - 100 \leq 0$。

### LP 文件表示

LP 格式要求常数项在右边：

```
  c_0: 3 x + 2 y <= 100
```

### 转换

导出时把常数项移到右边：

```python
rhs = -con.constant    # rhs = -(-100) = 100
```

数学推导：

$$
\text{lhs} + \text{const} \leq 0 \iff \text{lhs} \leq -\text{const}
$$

所以 `rhs = -const`。

### 示例

| 内部 | 导出 |
|------|------|
| `terms={x: 3, y: 2}, const=-100, sense=LE` | `3 x + 2 y <= 100` |
| `terms={x: 1, y: -1}, const=-2, sense=GE` | `x - y >= 2` |
| `terms={x: 1, y: 1}, const=-10, sense=EQ` | `x + y = 10` |

### 为什么内部用齐次形式

1. **运算简单**：约束相加、数乘不需要处理右端项。
2. **闭包性**：约束的线性组合仍是 `lhs <= 0` 形式。
3. **对称性**：`<=`、`>=`、`=` 的处理统一，不需要为 `>=` 特判。

---

## minipulp 的 write_lp 实现

本节逐步讲解 `write_lp` 的实现。

### 函数签名

```python
def write_lp(problem: LpProblem) -> str:
    """将问题序列化为 CPLEX LP 格式文本。"""
```

输入是 `LpProblem`，输出是 LP 格式的字符串。

### 整体流程

```python
def write_lp(problem: LpProblem) -> str:
    if not problem.valid():
        raise ValueError("问题未设置目标函数，无法导出")

    lines: list[str] = []
    # 1. 写注释行
    lines.append(f"\\ Project name: {problem.name}")
    # 2. 写目标段
    ...
    # 3. 写约束段
    ...
    # 4. 写界段
    ...
    # 5. 写整数变量段
    ...
    # 6. 写二元变量段
    ...
    # 7. 写结束标记
    lines.append("End")
    return "\n".join(lines)
```

### 1. 注释行

```python
lines.append(f"\\ Project name: {problem.name}")
```

输出 `\ Project name: demo`。`\` 是转义字符，在字符串中要写 `\\`。

### 2. 目标段

```python
sense_word = "Maximize" if problem.sense == LpSense.MAXIMIZE else "Minimize"
lines.append(sense_word)
obj_terms = _format_terms(problem.objective.terms)
obj_const = problem.objective.const
if obj_const:
    lines.append(f"  obj: {obj_terms} + {_format_coef(obj_const)}")
else:
    lines.append(f"  obj: {obj_terms}")
```

- 根据问题的 `sense` 选择 `Maximize` 或 `Minimize`。
- 用 `_format_terms` 格式化目标的变量项。
- 如果有常数项，附加 `+ const`。

### 3. 约束段

```python
if problem.constraints:
    lines.append("Subject To")
    for name, con in problem.constraints.items():
        terms_str = _format_terms(con.terms)
        rhs = -con.constant           # 常数项移到右边
        op = _CONSTRAINT_OP[con.sense]
        lines.append(f"  {name}: {terms_str} {op} {_format_coef(rhs)}")
```

- 只有有约束时才写 `Subject To` 段。
- 遍历每个约束，格式化为 `name: terms op rhs`。
- `rhs = -con.constant` 把常数项移到右边。
- `_CONSTRAINT_OP` 把内部的方向枚举映射到 LP 格式的符号：

```python
_CONSTRAINT_OP = {
    LpConstraintSense.LE: "<=",
    LpConstraintSense.EQ: "=",
    LpConstraintSense.GE: ">=",
}
```

### 4. 界段

```python
integer_vars = []
binary_vars = []
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

    if var.cat == LpCat.INTEGER:
        integer_vars.append(var.name)
    elif var.cat == LpCat.BINARY:
        binary_vars.append(var.name)

if bounded_lines:
    lines.append("Bounds")
    lines.extend(bounded_lines)
```

遍历所有变量，根据 `lowBound` 和 `upBound` 的组合生成界声明：

| lowBound | upBound | 输出 |
|----------|---------|------|
| None | None | `x free` |
| 有值 | 有值 | `lb <= x <= ub` |
| 有值 | None | `x >= lb` |
| None | 有值 | `x <= ub` |

同时收集整数变量和二元变量，供后续段使用。

### 5. 整数变量段

```python
if integer_vars:
    lines.append("General")
    for v in integer_vars:
        lines.append(f"  {v}")
```

### 6. 二元变量段

```python
if binary_vars:
    lines.append("Binary")
    for v in binary_vars:
        lines.append(f"  {v}")
```

### 7. 结束标记

```python
lines.append("End")
return "\n".join(lines)
```

---

## 完整示例

### Python 代码

```python
import minipulp as mp
from minipulp import write_lp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40
print(write_lp(prob))
```

### 输出

```
\ Project name: demo
Maximize
  obj: 3 x + 2 y
Subject To
  c_0: 2 x + y <= 100
  c_1: x + y <= 80
  c_2: x <= 40
Bounds
  x >= 0
  y >= 0
End
```

### 带整数变量的示例

```python
z = mp.LpVariable("z", lowBound=0, upBound=10, cat=mp.LpInteger)
b = mp.LpVariable("b", cat=mp.LpBinary)
prob += z + b
prob += z + b <= 15
```

输出：

```
\ Project name: demo
Maximize
  obj: z + b
Subject To
  c_0: z + b <= 15
Bounds
  z >= 0
  z <= 10
  b free
General
  z
Binary
  b
End
```

注意：二元变量 `b` 没有显式界（`b free`），因为 `Binary` 段已经隐含 $0 \leq b \leq 1$。

---

## 与 CBC 求解器的通信流程

minipulp 通过子进程调用 CBC 求解器。完整流程如下：

### 1. 写 LP 文件

```python
lp_text = write_lp(problem)
with open("model.lp", "w") as f:
    f.write(lp_text)
```

### 2. 调用 CBC

```python
import subprocess
result = subprocess.run(
    ["cbc", "model.lp", "-solve", "-solu", "model.sol"],
    capture_output=True,
    text=True,
)
```

CBC 读取 `model.lp`，求解，把解写入 `model.sol`。

### 3. 解析解文件

`model.sol` 的格式（CBC 输出）：

```
Status: optimal
Objective: 180
  x 40
  y 40
```

minipulp 解析这个文件，把解值回填到 `LpVariable.varValue`。

### 4. 回填

```python
x.varValue = 40.0
y.varValue = 40.0
```

### 通信流程图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   minipulp  │     │  model.lp   │     │     CBC     │
│             │────▶│             │────▶│             │
│  write_lp   │     │  LP 格式    │     │  求解器     │
└─────────────┘     └─────────────┘     └─────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   minipulp  │     │  model.sol  │     │     CBC     │
│             │◀────│             │◀────│             │
│  parse_sol  │     │  解格式     │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

### CBC 命令行参数

常用参数：

- `-solve`：求解问题。
- `-solu filename`：把解写入指定文件。
- `-max` / `-min`：覆盖目标方向（通常不需要，LP 文件已指定）。
- `-log level`：日志级别。

---

## MPS 格式对比

MPS（Mathematical Programming System）是更古老的格式，起源于 1960s。

### MPS vs LP

| 特性 | LP | MPS |
|------|----|----|
| 起源 | CPLEX | IBM |
| 可读性 | 人类可读 | 机器友好 |
| 格式 | 行导向，自由 | 列导向，固定列 |
| 注释 | `\` 开头 | `*` 开头 |
| 段 | Maximize, Subject To, ... | ROWS, COLUMNS, RHS, ... |
| 默认界 | `x >= 0` | `x >= 0` |
| 精度 | 有限 | 高（固定列可表示更多有效数字） |

### MPS 示例

```
NAME          demo
ROWS
 N  obj
 L  c_0
 L  c_1
COLUMNS
    x        obj      3.0        c_0      2.0
    x        c_1      1.0
    y        obj      2.0        c_0      1.0
    y        c_1      1.0
RHS
    rhs_0    c_0    100.0        c_1     80.0
BOUNDS
    LO bound  x        0.0
    LO bound  y        0.0
ENDATA
```

### MPS 的特点

1. **列导向**：按变量组织数据，每个变量的所有系数列在一起。适合稀疏矩阵。
2. **固定列**：字段在固定列位置，解析快但人类难读。
3. **NAME/ROWS/COLUMNS/RHS/BOUNDS/ENDATA**：段名与 LP 格式不同。
4. **N/L/E/G**：行类型（N=目标，L=小于等于，E=等于，G=大于等于）。

### minipulp 的 MPS 支持

minipulp 的 `write_mps` 尚未实现（Phase 4）：

```python
def write_mps(problem: LpProblem) -> str:
    raise NotImplementedError("Phase 4 实现")
```

---

## 其他格式简介

### NL 格式

AMPL 的 .nl 格式，用于非线性规划。支持任意非线性表达式，由 AMPL 建模语言生成。求解器通过 `nl` 文件 API 读取。

特点：
- 二进制或文本格式。
- 支持非线性函数。
- 包含变量、约束、目标、导数信息。

### OSiL 格式

Optimization Services instance Language，基于 XML 的优化问题格式。标准化、可扩展，但冗长。

特点：
- XML 格式。
- 支持线性和非线性。
- 由 COIN-OR 项目推动。

### JSON 格式

一些现代求解器（如 HiGHS）支持 JSON 格式。易于程序处理，但冗长且不人类友好。

### 求解器原生 API

许多求解器提供 C/C++/Python API，直接在内存中构建问题，无需文件：

```python
# Gurobi Python API
import gurobipy as gp
m = gp.Model()
x = m.addVar(lb=0)
y = m.addVar(lb=0)
m.setObjective(3*x + 2*y, gp.GRB.MAXIMIZE)
m.addConstr(2*x + y <= 100)
m.optimize()
```

优点：无文件 IO 开销，类型安全。缺点：绑定特定求解器，失去通用性。

---

## 格式解析的边界情况

### 1. 空问题

```python
prob = mp.LpProblem("empty", mp.LpMaximize)
# 没有目标，没有约束
write_lp(prob)  # ValueError: 问题未设置目标函数
```

`write_lp` 检查 `problem.valid()`，未设置目标时抛出异常。

### 2. 无约束问题

```python
prob = mp.LpProblem("no_con", mp.LpMaximize)
x = mp.LpVariable("x", lowBound=0)
prob += 3 * x
write_lp(prob)
```

输出（无 `Subject To` 段）：

```
\ Project name: no_con
Maximize
  obj: 3 x
Bounds
  x >= 0
End
```

### 3. 自由变量

```python
x = mp.LpVariable("x")  # 无 lowBound, 无 upBound
```

输出：

```
Bounds
  x free
End
```

### 4. 固定变量

```python
x = mp.LpVariable("x", lowBound=5, upBound=5)
```

输出：

```
Bounds
  5 <= x <= 5
End
```

部分求解器支持 `x = 5` 语法，但 minipulp 用双界形式。

### 5. 负下界

```python
x = mp.LpVariable("x", lowBound=-10)
```

输出：

```
Bounds
  x >= -10
End
```

### 6. 零系数项

由于规范化，零系数项不出现在 LP 文件中：

```python
x = mp.LpVariable("x")
y = mp.LpVariable("y")
prob += 0 * x + 3 * y   # 0*x 被消除
```

输出：

```
Maximize
  obj: 3 y
```

### 7. 浮点精度

```python
prob += 0.1 * x + 0.2 * x  # 浮点误差：0.30000000000000004
```

输出可能包含浮点噪声：

```
Maximize
  obj: 0.30000000000000004 x
```

生产代码应使用 `round` 或 `eps` 清理。

### 8. 变量名冲突

如果两个变量同名（minipulp 不防止），LP 文件会有歧义：

```
Maximize
  obj: 3 x + 2 x    # 哪个 x？
```

求解器可能把它们合并、报错或行为未定义。**不要创建同名变量**。

### 9. 特殊字符变量名

变量名含空格或特殊字符会破坏解析：

```python
x = mp.LpVariable("my var")  # 含空格
```

输出：

```
Maximize
  obj: 3 my var    # 解析器看到 "3", "my", "var" 三个 token
```

**变量名应只含字母、数字、下划线**。

---

## 工程考量

### 1. 大规模问题的内存

`write_lp` 把整个文件构建为字符串列表，最后 `join`。对于百万约束的问题，这会占用大量内存。生产代码可能需要流式写入文件。

### 2. 浮点精度

LP 格式是文本，浮点数以十进制表示。极小或极大的系数可能丢失精度：

```
  c_0: 0.0000000001 x <= 1e-10
```

部分求解器对极小系数敏感。MPS 格式的固定列可以表示更多有效数字。

### 3. 约束名唯一性

minipulp 自动生成约束名 `c_0`, `c_1`, ...。如果用户手动添加同名约束，会覆盖。生产代码应检查唯一性。

### 4. 变量顺序

LP 文件中变量的顺序由 `problem.variables()` 决定，通常是插入顺序。求解器对变量顺序不敏感，但顺序影响文件可读性。

### 5. 段的省略

minipulp 只在有必要时才写段：

- 无约束时不写 `Subject To`。
- 无界信息时不写 `Bounds`（但通常有，因为默认 `>= 0`）。
- 无整数变量时不写 `General`。
- 无二元变量时不写 `Binary`。

这让文件更简洁。

### 6. 注释行

minipulp 只写一行注释 `\ Project name: ...`。用户可以手动添加更多注释，但 minipulp 不提供 API。

### 7. 编码

LP 文件应使用 ASCII 或 UTF-8 编码。变量名含非 ASCII 字符可能不被求解器支持。

---

## LP 格式的完整规范参考

以下是 LP 格式的完整 BNF 范式（简化版）：

```
<lp_file>    ::= <comment>* <objective> <constraints>? <bounds>? <general>? <binary>? "End"

<comment>    ::= "\" <text> "\n"

<objective>  ::= ("Maximize" | "Minimize") "\n" <obj_line>
<obj_line>   ::= <name> ":" <expr> "\n"

<constraints> ::= "Subject To" "\n" <con_line>*
<con_line>   ::= <name> ":" <expr> ("<=" | ">=" | "=") <number> "\n"

<bounds>     ::= "Bounds" "\n" <bound_line>*
<bound_line> ::= <var> "free" "\n"
              | <var> ">=" <number> "\n"
              | <var> "<=" <number> "\n"
              | <number> "<=" <var> "<=" <number> "\n"

<general>    ::= "General" "\n" <var>+
<binary>     ::= "Binary" "\n" <var>+

<expr>       ::= <term> (("+" | "-") <term>)*
<term>       ::= <number>? <var> | <number> <var>

<name>       ::= <identifier>
<var>        ::= <identifier>
<identifier> ::= <letter> (<letter> | <digit> | "_")*
<number>     ::= <integer> | <float>
```

注意：不同求解器对这个规范的解释可能有细微差异。minipulp 生成的是最保守的子集，确保广泛兼容。

---

## 从 LP 文件重建问题

虽然 minipulp 主要做写（`write_lp`），但理解如何从 LP 文件重建问题有助于调试。

### 解析步骤

1. **词法分析**：把文本切成 token（关键字、变量名、数字、运算符）。
2. **语法分析**：根据段关键字组织 token。
3. **语义分析**：把表达式解析成字典表示。
4. **构建问题**：创建 `LpProblem`、`LpVariable`、`LpConstraint`。

### 表达式解析

解析 `3 x + 2 y - 5`：

```
token: 3, x, +, 2, y, -, 5
      ↓
项: (3, x), (2, y), (-5, const)
      ↓
字典: {x: 3, y: 2}, const=-5
```

### 注意事项

- 系数 1 省略：`x + y` 解析为 `{x: 1, y: 1}`。
- 符号处理：`- x` 是 `(-1, x)`，`+ x` 是 `(1, x)`。
- 顺序无关：`3 x + 2 y` 和 `2 y + 3 x` 解析为同一字典。

---

## LP 格式的变体

### CPLEX LP

最标准的变体，本文描述的就是这个。被 CBC、GLPK、HiGHS、CPLEX、Gurobi 支持。

### LINDO LP

LINDO 求解器的 LP 格式，段名和语法略有不同：

```
MAX 3 x + 2 y
SUBJECT TO
  2 x + y <= 100
END
```

### MPL LP

Mathematical Programming Language 的变体，支持更复杂的建模构造（集合、求和）。

### AMPL .mod

AMPL 的建模语言，不是 LP 格式，但可以导出 LP 格式。

minipulp 生成的 LP 文件是 CPLEX LP 变体，最广泛兼容。

---

## 调试 LP 文件

### 手动检查

LP 文件是人类可读的，可以直接打开检查：

```
\ Project name: demo
Maximize
  obj: 3 x + 2 y
Subject To
  c_0: 2 x + y <= 100
  c_1: x + y <= 80
  c_2: x <= 40
Bounds
  x >= 0
  y >= 0
End
```

检查点：

1. 目标方向（Maximize/Minimize）是否正确？
2. 约束方向（<=, >=, =）是否正确？
3. 系数是否正确？
4. 右端项是否正确（注意常数项移到右边的转换）？
5. 界是否正确？
6. 整数/二元变量是否正确声明？

### 用求解器验证

用 CBC 命令行直接求解 LP 文件：

```
$ cbc model.lp -solve -solu model.sol
```

检查 `model.sol` 的解是否合理。

### 对比 PuLP

用 PuLP 建立同样的问题，导出 LP 文件，对比：

```python
import pulp
x = pulp.LpVariable("x", lowBound=0)
y = pulp.LpVariable("y", lowBound=0)
prob = pulp.LpProblem("demo", pulp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40
prob.writeLP("model_pulp.lp")
```

两个 LP 文件应该语义相同（格式可能有细微差异）。

---

## LP 格式与内部表示的对照

### 对照表

| 内部表示 | LP 文件表示 |
|----------|------------|
| `LpProblem("demo", LpMaximize)` | `\ Project name: demo` + `Maximize` |
| `LpProblem("demo", LpMinimize)` | `\ Project name: demo` + `Minimize` |
| `LpAffineExpression({x: 3, y: 2}, const=0)` | `3 x + 2 y` |
| `LpAffineExpression({x: 3, y: 2}, const=5)` | `3 x + 2 y + 5` |
| `LpConstraint({x: 2, y: 1}, const=-100, sense=LE)` | `c_0: 2 x + y <= 100` |
| `LpConstraint({x: 1, y: -1}, const=-2, sense=GE)` | `c_1: x - y >= 2` |
| `LpConstraint({x: 1, y: 1}, const=-10, sense=EQ)` | `c_2: x + y = 10` |
| `LpVariable("x", lowBound=0)` | `x >= 0` in Bounds |
| `LpVariable("x", lowBound=0, upBound=10)` | `0 <= x <= 10` in Bounds |
| `LpVariable("x")` | `x free` in Bounds |
| `LpVariable("z", cat=INTEGER)` | `z` in General |
| `LpVariable("b", cat=BINARY)` | `b` in Binary |

### 转换的关键点

1. **目标方向**：`LpMaximize` → `Maximize`，`LpMinimize` → `Minimize`。
2. **约束方向**：`LE` → `<=`，`GE` → `>=`，`EQ` → `=`。
3. **常数项移位**：内部的 `const` 在左边，导出时移到右边变成 `rhs = -const`。
4. **系数格式化**：整数输出 `3`，浮点输出 `3.5`，系数 1 省略。
5. **界的组合**：根据 lowBound 和 upBound 的有无组合成不同形式。
6. **变量类别**：连续变量不声明，整数变量在 General 段，二元变量在 Binary 段。

---

## 序列化的正确性

### 序列化-反序列化一致性

理想情况下，`parse(write_lp(problem)) == problem`。即把问题写成 LP 文件，再解析回来，应该得到等价的问题。

### 可能的不一致

1. **约束名**：minipulp 生成 `c_0`, `c_1`, ...，解析回来可能用不同名字。
2. **变量顺序**：LP 文件的变量顺序可能与内部不同。
3. **浮点精度**：文本表示可能丢失精度。
4. **规范化**：解析时可能得到不同的规范形式（如 `x + x` 解析为 `{x: 2}`）。

### 实际应用

序列化-反序列化一致性在 minipulp 中不是硬性要求，因为 minipulp 主要做写（导出给求解器），不做读（从 LP 文件导入）。

---

## LP 格式的工程权衡

### 文本 vs 二进制

LP 格式是文本，优点：

- 人类可读，可调试。
- 版本控制友好（diff 有意义）。
- 跨平台，无字节序问题。

缺点：

- 文件较大（数字以十进制表示）。
- 解析慢（需要词法分析）。
- 精度有限（浮点以十进制表示）。

二进制格式（如求解器原生格式）相反：紧凑、快、精确，但不可读。

### 行导向 vs 列导向

LP 格式是行导向（每行一个约束），优点：

- 直观，每行一个约束。
- 易于增量添加约束。

缺点：

- 稀疏矩阵表示不紧凑（每个非零元素都要写变量名）。
- 列操作（如添加变量）需要修改所有行。

MPS 格式是列导向，对稀疏矩阵更紧凑。

### 自由格式 vs 固定列

LP 格式是自由格式（空格分隔），优点：

- 易读，不依赖列位置。
- 适应不同长度的变量名。

缺点：

- 解析稍慢（需要识别 token 边界）。
- 对齐不美观（变量名长度不同）。

MPS 格式是固定列，解析快但难读。

---

## minipulp 的 IO 层设计

### 模块结构

```
lp_io.py
├── _format_coef(coef)         # 系数格式化
├── _format_terms(terms)       # 项字典格式化
├── write_lp(problem)          # 写 LP 文件
└── write_mps(problem)         # 写 MPS 文件（未实现）
```

### 职责分离

- `elements.py`：代数层，定义表达式和变量。
- `constraints.py`：约束层，定义约束。
- `problem.py`：问题层，定义问题。
- `lp_io.py`：IO 层，把问题序列化为文件格式。

IO 层不依赖代数层的运算，只读取问题的只读视图。

### 扩展性

要支持新格式（如 OSiL），只需添加 `write_osil(problem)` 函数。代数层和问题层不需要修改。

---

## 完整的 LP 文件示例集

### 示例 1：简单 LP

```
\ Project name: simple
Maximize
  obj: 3 x + 2 y
Subject To
  c_0: 2 x + y <= 100
  c_1: x + y <= 80
  c_2: x <= 40
Bounds
  x >= 0
  y >= 0
End
```

### 示例 2：最小化

```
\ Project name: min_example
Minimize
  obj: 5 x + 3 y + 7 z
Subject To
  c_0: x + y + z >= 10
  c_1: 2 x + y - z = 5
Bounds
  x >= 0
  y >= 0
  z free
End
```

### 示例 3：整数规划

```
\ Project name: integer
Maximize
  obj: x + y
Subject To
  c_0: x + 2 y <= 10
  c_1: 3 x + y <= 15
Bounds
  x >= 0
  y >= 0
General
  x
  y
End
```

### 示例 4：二元规划

```
\ Project name: binary
Maximize
  obj: 5 b1 + 3 b2 + 2 b3
Subject To
  c_0: b1 + b2 + b3 <= 2
  c_1: b1 + b3 >= 1
Binary
  b1
  b2
  b3
End
```

### 示例 5：混合整数规划

```
\ Project name: mixed
Minimize
  obj: 2 x + 3 y + z
Subject To
  c_0: x + y >= 5
  c_1: y + z <= 10
  c_2: x - z = 2
Bounds
  x >= 0
  0 <= y <= 20
  z free
General
  y
Binary
  z
End
```

### 示例 6：无约束问题

```
\ Project name: no_constraints
Maximize
  obj: 3 x
Bounds
  x >= 0
End
```

### 示例 7：等式约束

```
\ Project name: equality
Minimize
  obj: x + y + z
Subject To
  c_0: x + y + z = 10
  c_1: x - y = 0
Bounds
  x >= 0
  y >= 0
  z >= 0
End
```

### 示例 8：负下界

```
\ Project name: negative_bound
Maximize
  obj: x + y
Subject To
  c_0: x + y <= 10
Bounds
  x >= -5
  y >= -3
End
```

### 示例 9：双界

```
\ Project name: double_bound
Maximize
  obj: x
Subject To
  c_0: x <= 10
Bounds
  0 <= x <= 15
End
```

### 示例 10：大规模问题（示意）

```
\ Project name: large_scale
Minimize
  obj: 1 x_0 + 2 x_1 + 3 x_2 + ... + 100 x_99
Subject To
  c_0: 1 x_0 + 1 x_1 + ... + 1 x_99 >= 50
  c_1: 2 x_0 + 1 x_1 + ... + 0 x_99 <= 100
  ...
  c_199: ...
Bounds
  x_0 >= 0
  x_1 >= 0
  ...
  x_99 >= 0
End
```

---

## LP 格式的常见错误

### 1. 段顺序错误

```
Subject To        ← 错误：目标段必须在约束段之前
  c_0: x <= 1
Maximize
  obj: x
End
```

### 2. 缺少冒号

```
Subject To
  c_0 2 x + y <= 100    ← 错误：缺少冒号
```

### 3. 方向符错误

```
Subject To
  c_0: 2 x + y < 100    ← 错误：应该是 <=
  c_1: 2 x + y > 100    ← 错误：应该是 >=
```

### 4. 右端项含变量

```
Subject To
  c_0: 2 x <= y         ← 错误：右端项必须是常数
```

应该写成：

```
  c_0: 2 x - y <= 0
```

### 5. 变量名非法

```
Subject To
  c_0: 2 x-y <= 100     ← 错误：x-y 被解析为 x - y
```

应该用下划线：

```
  c_0: 2 x_y <= 100
```

### 6. 缺少 End

```
Maximize
  obj: x
Bounds
  x >= 0
                    ← 错误：缺少 End
```

### 7. 重复段

```
Maximize
  obj: x
Maximize            ← 错误：重复段
  obj: y
End
```

---

## 求解器对 LP 格式的解释差异

不同求解器对 LP 格式的解释可能有细微差异：

### 1. 空行处理

- 大部分求解器忽略空行。
- 少数求解器要求紧凑格式，空行报错。

### 2. 大小写

- CPLEX 严格大小写：`Maximize` 不能是 `maximize`。
- GLPK 宽松：接受 `maximize`。
- minipulp 总是写严格大小写。

### 3. 约束名可选性

- CPLEX 要求约束名。
- GLPK 允许省略。
- minipulp 总是写约束名。

### 4. 系数 1 省略

- 所有求解器都支持省略系数 1。
- minipulp 省略系数 1。

### 5. 多变量一行

```
General
  x y z             ← 一行多个变量
```

- CPLEX 支持。
- GLPK 要求每行一个。
- minipulp 每行写一个，最兼容。

### 6. 注释位置

- 大部分求解器只接受行首注释（`\` 在行首）。
- 少数支持行内注释。
- minipulp 只在行首写注释。

---

## LP 格式的版本演进

LP 格式没有正式的版本号，但不同时期的求解器支持不同特性：

### 早期（CPLEX 1.x）

- 基本段：Objective, Subject To, Bounds, End。
- 无整数变量支持。

### 中期（CPLEX 3.x）

- 添加 General/Integer 段。
- 添加 Binary 段。

### 现代（CPLEX 12.x+）

- 添加 RANGES 段（范围约束）。
- 添加 SOS（Special Ordered Sets）段。
- 支持 `free` 关键字。

minipulp 使用最基础的子集，确保所有版本的求解器都能支持。

---

## 从 minipulp 到求解器的完整数据流

```
用户代码
  │
  ▼
LpProblem 对象
  ├── objective: LpAffineExpression({x: 3, y: 2}, const=0)
  ├── constraints: {
  │     "c_0": LpConstraint({x: 2, y: 1}, const=-100, sense=LE),
  │     "c_1": LpConstraint({x: 1, y: 1}, const=-80, sense=LE),
  │     "c_2": LpConstraint({x: 1}, const=-40, sense=LE),
  │   }
  └── variables: [x (lowBound=0), y (lowBound=0)]
  │
  ▼ write_lp()
  │
LP 文本
  \ Project name: demo
  Maximize
    obj: 3 x + 2 y
  Subject To
    c_0: 2 x + y <= 100
    c_1: x + y <= 80
    c_2: x <= 40
  Bounds
    x >= 0
    y >= 0
  End
  │
  ▼ 写入文件 + 调用 CBC
  │
CBC 求解器
  │
  ▼ 求解
  │
解文件
  Status: optimal
  Objective: 180
    x 40
    y 40
  │
  ▼ 解析 + 回填
  │
LpVariable.varValue
  x.varValue = 40.0
  y.varValue = 40.0
```

每一步都是确定性的、可调试的。理解这个数据流，就理解了 minipulp 的 IO 层。

---

## 总结

LP 格式是建模库与求解器之间的通信协议。minipulp 的 `write_lp` 把内部的字典表示序列化为 CPLEX LP 格式文本，核心工作是：

1. **格式化系数**：整数输出 `3`，浮点输出 `3.5`，系数 1 省略。
2. **归一化约束**：把内部 `lhs + const <= 0` 转换为 `lhs <= -const`。
3. **组织段**：按 Objective, Subject To, Bounds, General, Binary, End 顺序输出。
4. **处理界**：根据 lowBound 和 upBound 的组合生成不同形式的界声明。

理解 LP 格式，就理解了 minipulp 如何与求解器通信。这是建模库落地的关键一环。

---

## 后记：格式的设计哲学

LP 格式体现了几个设计哲学：

### 1. 人类优先

LP 格式优先人类可读性，而非机器效率。这让它成为调试和教学的理想格式。

### 2. 最小通用子集

LP 格式只支持线性规划，不支持非线性。这是它的局限，也是它的力量——简单、通用、高效。

### 3. 约定优于配置

默认 `x >= 0` 是一个重要约定，让大多数问题（非负变量）不需要显式声明界。这减少了文件的冗余。

### 4. 段式结构

段式结构（Maximize, Subject To, Bounds, ...）让格式可扩展——新特性可以添加新段，不破坏旧文件。

这些哲学让 LP 格式经久不衰，成为优化生态的通用语言。

---

## 参考阅读

- **CPLEX LP 格式参考**：https://www.ibm.com/docs/icos/12.9.0/linear-programming-file-format
- **CBC 文档**：https://coin-or.github.io/Cbc/
- **GLPK 文档**：https://www.gnu.org/software/glpk/
- **MPS 格式参考**：https://en.wikipedia.org/wiki/MPS_(format)
- **HiGHS 文档**：https://highs.dev/

---

> **核心要点**：LP 格式是建模库与求解器的通信协议。minipulp 的 `write_lp` 把字典表示序列化为 LP 文本，关键是系数格式化、常数项移位、段组织。理解这个流程，就理解了 minipulp 如何与求解器交互。
