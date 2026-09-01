# Phase 4 — CBC 求解器对接

> 工业级通信范式：`LpProblem → .lp 文件 → cbc → .sol 文件 → 回填`。
>
> 本篇对应 `src/minipulp/solvers/cbc_cmd.py`。

---

## 目录

- [设计哲学](#设计哲学)
- [通信流程](#通信流程)
- [PULP_CBC_CMD 求解器](#pulp_cbc_cmd-求解器)
- [.sol 文件解析](#sol-文件解析)
- [整数规划支持](#整数规划支持)
- [完整示例](#完整示例)
- [CBC 求解器完整通信流程图解](#cbc-求解器完整通信流程图解)
- [.sol 文件格式详细说明](#sol-文件格式详细说明)
- [_parse_sol 逐行讲解](#_parse_sol-逐行讲解)
- [整数规划支持详解](#整数规划支持详解)
- [分支定界算法简介](#分支定界算法简介)
- [与 SimplexCore/SimplexCpp 对比](#与-simplexcoresimplexcpp-对比)
- [背包问题示例](#背包问题示例)
- [设施数量问题示例](#设施数量问题示例)
- [旅行商问题示例](#旅行商问题示例)
- [求解器选择指南](#求解器选择指南)
- [时间限制和日志输出](#时间限制和日志输出)
- [测试](#测试)
- [求解器对比](#求解器对比)

---

## 设计哲学

### 文件中转范式

minipulp 与 CBC 求解器的通信采用**文件中转**范式：

```
LpProblem → write_lp → .lp 文件 → subprocess 调 cbc → .sol 文件 → 解析 → 回填
```

这是 OR（运筹学）生态的主流方式。建模库不嵌入求解器代码，
而是通过标准文件格式与求解器进程通信。

**好处**：

1. **解耦**：换求解器只需换命令行，不改建模代码
2. **隔离**：求解器崩溃不影响建模进程
3. **标准化**：LP/MPS 是跨语言、跨平台的通用格式
4. **可调试**：中间文件可检查、可手动运行求解器

**代价**：

1. **文件 I/O 开销**：序列化/反序列化需要时间
2. **临时文件管理**：需要创建、清理临时文件
3. **进程创建开销**：每次求解启动一个新进程

对于大规模问题，求解时间远大于 I/O 开销，文件中转是合理的选择。

### CBC 简介

CBC（Coin-or Branch and Cut）是开源 MILP 求解器，支持：

- 线性规划（LP）
- 混合整数规划（MIP）
- 分支定界（Branch and Bound）
- 割平面（Cutting Planes）

性能接近商业求解器（CPLEX/Gurobi）的 70-80%，是开源 OR 生态的核心组件。

---

## 通信流程

```
┌─────────────┐     ┌──────────┐     ┌─────────┐     ┌──────────┐     ┌─────────────┐
│  LpProblem  │ ──→ │ write_lp │ ──→ │ .lp 文件 │ ──→ │ subprocess│ ──→ │ .sol 文件   │
│  (建模层)   │     │ (序列化) │     │ (临时)  │     │ (cbc 进程)│     │ (求解结果)  │
└─────────────┘     └──────────┘     └─────────┘     └──────────┘     └─────────────┘
                                                                              │
                                                                              ▼
┌─────────────┐     ┌──────────┐     ┌──────────────────────────────────────────┐
│  varValue   │ ←── │ _backfill│ ←── │ _parse_sol (解析 .sol 文件)              │
│  (回填解值) │     │          │     │                                          │
└─────────────┘     └──────────┘     └──────────────────────────────────────────┘
```

### 步骤详解

1. **序列化**：`write_lp(problem)` 将 `LpProblem` 转为 CPLEX LP 格式文本
2. **写文件**：将 LP 文本写入临时文件 `model.lp`
3. **调用 CBC**：`subprocess.run(["cbc", "model.lp", "-solve", "-solution", "model.sol"])`
4. **读结果**：读取 CBC 生成的 `model.sol` 文件
5. **解析**：从 `.sol` 文本中提取状态码和变量值
6. **回填**：将变量值写入 `LpVariable.varValue`

---

## PULP_CBC_CMD 求解器

### 类定义

```python
class PULP_CBC_CMD(LpSolver):
    name = "PULP_CBC_CMD"

    def __init__(self, path=None, msg=False, timeLimit=None):
        super().__init__()
        self.path = path or shutil.which("cbc")  # 自动查找 cbc 路径
        self.msg = msg                          # 是否显示 CBC 输出
        self.timeLimit = timeLimit              # 求解时间上限
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str \| None` | CBC 可执行文件路径。None 时用 `shutil.which` 自动查找 |
| `msg` | `bool` | 是否显示 CBC 求解器输出 |
| `timeLimit` | `int \| None` | 求解时间上限（秒） |

### 可用性检查

```python
def available(self) -> bool:
    if self.path is None:
        self.path = shutil.which("cbc")
    return self.path is not None and os.path.isfile(self.path)
```

`shutil.which("cbc")` 在 `PATH` 中搜索 `cbc` 可执行文件。

### 求解流程

```python
def actualSolve(self, problem: LpProblem) -> LpStatus:
    if not self.available():
        raise RuntimeError(f"CBC not found at {self.path}")

    # 1. 序列化为 LP 格式
    lp_text = write_lp(problem)

    with tempfile.TemporaryDirectory() as tmpdir:
        lp_path = os.path.join(tmpdir, "model.lp")
        sol_path = os.path.join(tmpdir, "model.sol")

        # 2. 写入临时文件
        with open(lp_path, "w") as f:
            f.write(lp_text)

        # 3. 调用 CBC
        cmd = [self.path, lp_path, "-solve", "-solution", sol_path]
        if self.timeLimit:
            cmd.extend(["-sec", str(self.timeLimit)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=...)

        # 4. 读取结果
        with open(sol_path, "r") as f:
            sol_text = f.read()

        # 5. 解析 + 回填
        status, values = self._parse_sol(sol_text, problem)
        self._backfill(problem, status, values)
        return status
```

**临时目录**：`tempfile.TemporaryDirectory()` 确保临时文件用完后自动清理。

**超时**：`subprocess.run(timeout=...)` 防止 CBC 无限运行。

---

## .sol 文件解析

### 文件格式

CBC 的 `.sol` 文件含多段解（初始解 + 最优解），每段以状态行开头：

```
Optimal - objective value 180.00000000
      0 x                     20                       0
      1 y                     60                       0
```

- 第一行：状态（Optimal/Infeasible/Unbounded）+ 目标值
- 后续行：`序号 变量名 值 对偶值`

### 解析实现

```python
_STATUS_PATTERNS = {
    LpStatus.OPTIMAL: re.compile(r"optimal", re.IGNORECASE),
    LpStatus.INFEASIBLE: re.compile(r"infeasible", re.IGNORECASE),
    LpStatus.UNBOUNDED: re.compile(r"unbounded", re.IGNORECASE),
}

def _parse_sol(self, sol_text: str, problem: LpProblem) -> tuple[LpStatus, dict]:
    lines = sol_text.strip().split("\n")
    status = LpStatus.UNDEFINED
    values: dict[str, float] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 匹配状态行
        matched_status = False
        for code, pattern in _STATUS_PATTERNS.items():
            if pattern.search(line):
                status = code
                matched_status = True
                values = {}  # 重置，取最后一段
                break
        if matched_status:
            continue

        # 匹配变量值行
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            var_name = parts[1]
            try:
                var_value = float(parts[2])
                values[var_name] = var_value
            except ValueError:
                pass

    return status, values
```

**取最后一段**：遇到新的状态行时重置 `values`，确保取最优解而非初始解。

### 回填

```python
def _backfill(self, problem: LpProblem, status: LpStatus, values: dict) -> None:
    for var in problem.variables():
        if status == LpStatus.OPTIMAL and var.name in values:
            var.varValue = values[var.name]
        else:
            var.varValue = None
```

按变量名匹配，将解值写入 `varValue`。不可行/无界时设为 None。

---

## 整数规划支持

CBC 支持整数规划（分支定界），这是 `SimplexCore` 不具备的：

```python
x = mp.LpVariable("x", lowBound=0, cat=mp.LpInteger)
y = mp.LpVariable("y", lowBound=0, cat=mp.LpInteger)

prob = mp.LpProblem("mip", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80

prob.solve(solver=mp.solvers.PULP_CBC_CMD())
# x = 40, y = 40 (整数解)
```

### 变量类别

| 类别 | LP 文件段 | 求解算法 |
|------|---------|---------|
| `LpContinuous` | 无（默认连续） | 单纯形法 |
| `LpInteger` | `General` | 分支定界 |
| `LpBinary` | `Binary` | 分支定界 + 0/1 截断 |

`write_lp` 自动将整数变量放入 `General` 段，二元变量放入 `Binary` 段。

---

## 完整示例

### 连续 LP

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("lp", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

prob.solve(solver=PULP_CBC_CMD())
print(f"status: {prob.status_msg}")  # Optimal
print(f"x = {x.varValue}, y = {y.varValue}")  # x = 20, y = 60
```

### 整数规划

```python
x = mp.LpVariable("x", lowBound=0, cat=mp.LpInteger)
y = mp.LpVariable("y", lowBound=0, cat=mp.LpInteger)

prob = mp.LpProblem("mip", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80

prob.solve(solver=PULP_CBC_CMD())
print(f"x = {x.varValue}, y = {y.varValue}")  # 整数解
```

### 二元变量

```python
# 选址问题：从 5 个候选位置选 3 个
z = mp.LpVariable.dicts("z", range(5), cat=mp.LpBinary)

prob = mp.LpProblem("facility", mp.LpMaximize)
prob += mp.lpSum(profit[i] * z[i] for i in range(5))
prob += mp.lpSum(z[i] for i in range(5)) == 3  # 恰好选 3 个

prob.solve(solver=PULP_CBC_CMD())
```

---

## CBC 求解器完整通信流程图解

### 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              minipulp 进程                                  │
│                                                                             │
│  ┌─────────────┐                                                           │
│  │  LpProblem  │                                                           │
│  │  - objective│                                                           │
│  │  - constraints                                                          │
│  │  - variables│                                                           │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │  write_lp   │  序列化为 CPLEX LP 格式文本                                │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │ model.lp    │  临时文件                                                  │
│  │ (LP 格式)   │                                                           │
│  └──────┬──────┘                                                           │
│         │                                                                   │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │
          ▼  subprocess.run(["cbc", "model.lp", "-solve", "-solution", "model.sol"])
┌─────────────────────────────────────────────────────────────────────────────┐
│                              cbc 子进程                                     │
│                                                                             │
│  1. 读取 model.lp                                                           │
│  2. 解析 LP 格式                                                             │
│  3. 预处理（Presolve）                                                       │
│  4. 分支定界 / 单纯形法                                                      │
│  5. 写入 model.sol                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              minipulp 进程                                  │
│                                                                             │
│  ┌─────────────┐                                                           │
│  │ model.sol   │  CBC 输出文件                                              │
│  │ (解格式)    │                                                           │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │ _parse_sol  │  解析 .sol 文本，提取状态和变量值                           │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │ _backfill   │  将值写入 LpVariable.varValue                              │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │  LpProblem  │  status 更新，变量有解值                                    │
│  │  .status    │                                                           │
│  └─────────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 各阶段详解

#### 阶段 1：序列化

```python
lp_text = write_lp(problem)
```

将 `LpProblem` 对象转为 CPLEX LP 格式文本字符串。这是纯内存操作，不涉及 I/O。

#### 阶段 2：写入临时文件

```python
with tempfile.TemporaryDirectory() as tmpdir:
    lp_path = os.path.join(tmpdir, "model.lp")
    with open(lp_path, "w") as f:
        f.write(lp_text)
```

`tempfile.TemporaryDirectory()` 创建临时目录，`with` 块结束后自动删除。

#### 阶段 3：调用 CBC

```python
cmd = [self.path, lp_path, "-solve", "-solution", sol_path]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=...)
```

- `self.path`：CBC 可执行文件路径
- `lp_path`：输入 LP 文件
- `-solve`：指示 CBC 求解
- `-solution sol_path`：指示 CBC 将解写入 `sol_path`
- `capture_output=True`：捕获 stdout/stderr
- `timeout`：防止 CBC 无限运行

#### 阶段 4：读取结果

```python
with open(sol_path, "r") as f:
    sol_text = f.read()
```

读取 CBC 生成的 `.sol` 文件。

#### 阶段 5：解析

```python
status, values = self._parse_sol(sol_text, problem)
```

从 `.sol` 文本中提取：
- `status`：`LpStatus.OPTIMAL` / `INFEASIBLE` / `UNBOUNDED`
- `values`：`{var_name: var_value}` 字典

#### 阶段 6：回填

```python
self._backfill(problem, status, values)
```

将 `values` 写入 `LpVariable.varValue`，更新 `problem.status`。

### 错误处理流程

```python
def actualSolve(self, problem):
    if not self.available():
        raise RuntimeError(f"CBC not found at {self.path}")

    try:
        # ... 求解流程 ...
        result = subprocess.run(cmd, ..., timeout=...)
    except subprocess.TimeoutExpired:
        problem.status = LpStatus.NOT_SOLVED
        return LpStatus.NOT_SOLVED
    except FileNotFoundError:
        raise RuntimeError("CBC 可执行文件不存在")

    if not os.path.exists(sol_path):
        raise RuntimeError("CBC 未生成解文件")

    # ... 解析 ...
```

---

## .sol 文件格式详细说明

### 文件结构

CBC 的 `.sol` 文件是文本格式，包含一段或多段解：

```
Optimal - objective value 180.00000000
      0 x                     20                       0
      1 y                     60                       0
End of values
```

### 各行含义

#### 状态行

```
Optimal - objective value 180.00000000
```

- `Optimal`：求解状态
- `- objective value 180.00000000`：目标函数值

可能的状态：

| 状态字符串 | 含义 | 对应 `LpStatus` |
|-----------|------|----------------|
| `Optimal` | 找到最优解 | `OPTIMAL` |
| `Infeasible` | 问题不可行 | `INFEASIBLE` |
| `Unbounded` | 问题无界 | `UNBOUNDED` |
| `Optimal - Integer` | 整数最优解 | `OPTIMAL` |

#### 变量值行

```
      0 x                     20                       0
```

格式：`序号 变量名 值 对偶值`

- `0`：变量序号（从 0 开始）
- `x`：变量名
- `20`：变量值（主解）
- `0`：对偶值（影子价格，整数变量为 0）

#### 多段解

对于整数规划，`.sol` 文件可能包含多段：

```
Optimal - objective value 180.00000000
      0 x                     20                       0
      1 y                     60                       0
Optimal - objective value 180.00000000
      0 x                     20                       0
      1 y                     60                       0
```

`_parse_sol` 遇到新的状态行时重置 `values`，取最后一段（通常是最优解）。

### 完整示例

#### 连续 LP 的 .sol 文件

```
Optimal - objective value 180.00000000
      0 x                     20                       0.6
      1 y                     60                       0.4
End of values
```

- 目标值：180
- `x = 20`，对偶值 0.6
- `y = 60`，对偶值 0.4

#### 整数规划的 .sol 文件

```
Optimal - objective value 180.00000000
      0 x                     20                       0
      1 y                     60                       0
End of values
```

整数变量的对偶值为 0（整数变量没有影子价格）。

#### 不可行问题的 .sol 文件

```
Infeasible - objective value -1e+100
      0 x                     0                       0
      1 y                     0                       0
End of values
```

状态为 `Infeasible`，变量值无意义（通常为 0）。

### 与 LP 文件的对应

```
LP 文件：                        .sol 文件：
\ Project name: demo            Optimal - objective value 180
Maximize                              0 x                     20    0.6
  obj: 3 x + 2 y                      1 y                     60    0.4
Subject To
  c_0: 2 x + 1 y <= 100
  c_1: 1 x + 1 y <= 80
Bounds
  x >= 0
  y >= 0
End
```

变量名在 LP 和 .sol 文件中一致，这是 `_backfill` 能按名匹配的基础。

---

## _parse_sol 逐行讲解

### 函数签名

```python
def _parse_sol(self, sol_text: str, problem: LpProblem) -> tuple[LpStatus, dict]:
```

输入：`.sol` 文件文本和问题对象。输出：状态码和 `{var_name: value}` 字典。

### 状态模式定义

```python
_STATUS_PATTERNS = {
    LpStatus.OPTIMAL: re.compile(r"optimal", re.IGNORECASE),
    LpStatus.INFEASIBLE: re.compile(r"infeasible", re.IGNORECASE),
    LpStatus.UNBOUNDED: re.compile(r"unbounded", re.IGNORECASE),
}
```

用正则表达式匹配状态字符串，`re.IGNORECASE` 使匹配不区分大小写。

### 初始化

```python
lines = sol_text.strip().split("\n")
status = LpStatus.UNDEFINED
values: dict[str, float] = {}
```

- `lines`：按行分割文本
- `status`：初始为 `UNDEFINED`
- `values`：空字典

### 逐行处理

```python
for line in lines:
    line = line.strip()
    if not line:
        continue
```

跳过空行。

#### 状态行匹配

```python
    matched_status = False
    for code, pattern in _STATUS_PATTERNS.items():
        if pattern.search(line):
            status = code
            matched_status = True
            values = {}  # 重置，取最后一段
            break
    if matched_status:
        continue
```

- 遍历状态模式，检查当前行是否匹配
- 匹配则更新 `status`，重置 `values`（取最后一段解）
- 跳过后续处理

#### 变量值行匹配

```python
    parts = line.split()
    if len(parts) >= 3 and parts[0].isdigit():
        var_name = parts[1]
        try:
            var_value = float(parts[2])
            values[var_name] = var_value
        except ValueError:
            pass
```

- `parts = line.split()`：按空白分割
- `len(parts) >= 3`：至少有 序号、变量名、值 三部分
- `parts[0].isdigit()`：第一部分是数字（序号）
- `var_name = parts[1]`：变量名
- `var_value = float(parts[2])`：变量值
- `try/except`：跳过无法解析的行

### 完整逐行示例

输入 `.sol` 文本：

```
Optimal - objective value 180.00000000
      0 x                     20                       0
      1 y                     60                       0
```

处理过程：

```
行 1: "Optimal - objective value 180.00000000"
  - 匹配 "optimal"（不区分大小写）
  - status = LpStatus.OPTIMAL
  - values = {}（重置）
  - continue

行 2: "0 x 20 0"
  - 不匹配状态模式
  - parts = ["0", "x", "20", "0"]
  - len(parts) = 4 >= 3 ✓
  - parts[0] = "0".isdigit() = True ✓
  - var_name = "x", var_value = 20.0
  - values = {"x": 20.0}

行 3: "1 y 60 0"
  - 不匹配状态模式
  - parts = ["1", "y", "60", "0"]
  - var_name = "y", var_value = 60.0
  - values = {"x": 20.0, "y": 60.0}

返回 (LpStatus.OPTIMAL, {"x": 20.0, "y": 60.0})
```

### 多段解的处理

```
Optimal - objective value 100
      0 x                     10                       0
Optimal - objective value 180
      0 x                     20                       0
      1 y                     60                       0
```

处理过程：

```
行 1: "Optimal - objective value 100"
  - status = OPTIMAL, values = {}

行 2: "0 x 10 0"
  - values = {"x": 10.0}

行 3: "Optimal - objective value 180"
  - status = OPTIMAL, values = {}（重置！）

行 4: "0 x 20 0"
  - values = {"x": 20.0}

行 5: "1 y 60 0"
  - values = {"x": 20.0, "y": 60.0}

返回 (OPTIMAL, {"x": 20.0, "y": 60.0})  ← 取最后一段
```

---

## 整数规划支持详解

### 整数变量的 LP 文件表示

```python
x = mp.LpVariable("x", lowBound=0, cat=mp.LpInteger)
y = mp.LpVariable("y", lowBound=0, cat=mp.LpInteger)

prob = mp.LpProblem("mip", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80

print(mp.write_lp(prob))
```

输出：

```
\ Project name: mip
Maximize
  obj: 3 x + 2 y
Subject To
  c_0: 2 x + 1 y <= 100
  c_1: 1 x + 1 y <= 80
Bounds
  x >= 0
  y >= 0
General
  x
  y
End
```

`General` 段声明 `x` 和 `y` 是整数变量。CBC 读取此后，用分支定界求解。

### 二元变量的 LP 文件表示

```python
b = mp.LpVariable("b", cat=mp.LpBinary)
```

输出：

```
Bounds
  0 <= b <= 1
Binary
  b
End
```

`Binary` 段声明 `b` 是 0/1 变量。CBC 自动添加 `0 <= b <= 1` 界约束。

### 连续 LP vs 整数 LP 的求解差异

```python
# 连续 LP
x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)
prob = mp.LpProblem("lp", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob.solve(solver=PULP_CBC_CMD())
# x = 20, y = 60, obj = 180（连续最优）

# 整数 LP
x = mp.LpVariable("x", lowBound=0, cat=mp.LpInteger)
y = mp.LpVariable("y", lowBound=0, cat=mp.LpInteger)
prob = mp.LpProblem("mip", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob.solve(solver=PULP_CBC_CMD())
# x = 20, y = 60, obj = 180（恰好整数，与连续解相同）
```

如果连续解恰好是整数，整数解相同。否则整数解是连续解的"向下取整"近似（但可能更复杂）。

### 整数松弛

整数规划的求解策略是**松弛**：先去掉整数约束，求解连续 LP，再分支。

```python
# 原整数问题
max 3x + 2y
s.t. 2x + y <= 100
     x + y <= 80
     x, y >= 0 且整数

# 松弛（去掉整数约束）
max 3x + 2y
s.t. 2x + y <= 100
     x + y <= 80
     x, y >= 0
```

松弛 LP 的最优解是整数规划的解的上界（最大化问题）。

---

## 分支定界算法简介

### 基本思想

分支定界（Branch and Bound, B&B）是求解整数规划的经典算法：

1. **松弛**：去掉整数约束，求解连续 LP
2. **分支**：如果连续解非整数，分支为两个子问题
3. **定界**：用子问题的解值界定原问题
4. **剪枝**：丢弃不可能改进的子问题

### 分支示例

```
原问题：max 3x + 2y, s.t. 2x+y<=100, x+y<=80, x,y 整数

松弛解：x=20, y=60, obj=180（恰好整数，完成！）
```

如果松弛解是 `x=20.5, y=59.5`：

```
分支 1：x <= 20
  松弛解：x=20, y=60, obj=180

分支 2：x >= 21
  松弛解：x=21, y=58, obj=179

最优：分支 1 的解，obj=180
```

### 分支树

```
                    原问题
                   /        \
              x <= 20        x >= 21
              /    \          /    \
          x<=19  x=20     x=21   x>=22
           ...   ...      ...    ...
```

每个节点是一个松弛 LP，叶子节点是整数解或被剪枝。

### 剪枝条件

1. **整数解**：找到整数解，更新最优解
2. **界剪枝**：子问题的上界 < 当前最优解，丢弃
3. **不可行**：子问题不可行，丢弃

### CBC 的增强

CBC 在纯 B&B 基础上增加了**割平面**（Cutting Planes）：

- Gomory 割
- MIR 割
- 流覆盖割

割平面在分支前添加有效不等式，收紧松弛，减少分支次数。这就是"Branch and Cut"。

---

## 与 SimplexCore/SimplexCpp 对比

### 功能对比

| 特性 | SimplexCore | SimplexCpp | PULP_CBC_CMD |
|------|------------|-----------|--------------|
| 算法 | 两阶段单纯形 | C++ 两阶段单纯形 | 分支定界 + 割平面 |
| 连续 LP | ✓ | ✓ | ✓ |
| 整数规划 | ✗ | ✗ | ✓ |
| 二元变量 | ✗ | ✗ | ✓ |
| 不可行检测 | ✓ | ✓ | ✓ |
| 无界检测 | ✓ | ✓ | ✓ |
| 对偶值 | ✗ | ✗ | ✓ |
| 预处理 | ✗ | ✗ | ✓ |
| 时间限制 | ✗ | ✗ | ✓ |

### 性能对比

| 求解器 | 100 变量 | 1000 变量 | 10000 变量 |
|-------|---------|----------|-----------|
| SimplexCore | ~1s | ~100s | 超时 |
| SimplexCpp | ~0.05s | ~2s | ~60s |
| PULP_CBC_CMD | ~0.1s | ~0.5s | ~5s |

（近似值，实际取决于问题结构）

### 依赖对比

| 求解器 | 依赖 | 安装 |
|-------|------|------|
| SimplexCore | 无 | 内置 |
| SimplexCpp | C++ 编译器 | 需编译扩展 |
| PULP_CBC_CMD | CBC 可执行文件 | 需安装 CBC |

### 使用场景

```python
# 教学/学习：SimplexCore
prob.solve(solver=mp.solvers.SimplexCore())

# 中规模连续 LP：SimplexCpp
prob.solve(solver=mp.solvers.SimplexCpp())

# 整数规划/大规模：PULP_CBC_CMD
prob.solve(solver=mp.solvers.PULP_CBC_CMD())

# 默认（自动选择）
prob.solve()
```

### 内部实现差异

#### SimplexCore

```python
# 直接操作矩阵，Python 实现
class SimplexCore:
    def solve(self, problem):
        # 1. 提取矩阵 A, b, c
        # 2. 两阶段单纯形法
        # 3. 直接写入 varValue
```

无文件 I/O，直接内存操作。但 Python 循环慢。

#### PULP_CBC_CMD

```python
# 文件中转，调用外部进程
class PULP_CBC_CMD:
    def actualSolve(self, problem):
        # 1. write_lp → 文本
        # 2. 写入 .lp 文件
        # 3. subprocess 调 cbc
        # 4. 读取 .sol 文件
        # 5. 解析 + 回填
```

有文件 I/O 和进程创建开销，但 CBC 本身是高度优化的 C++ 代码。

---

## 背包问题示例

### 问题描述

有 N 个物品，每个有重量和价值。背包容量有限，选择物品最大化总价值，不超容量。

### 0-1 背包

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 数据
items = ["物品1", "物品2", "物品3", "物品4", "物品5"]
weight = {"物品1": 2, "物品2": 3, "物品3": 4, "物品4": 5, "物品5": 6}
value = {"物品1": 3, "物品2": 4, "物品3": 5, "物品4": 6, "物品5": 7}
capacity = 10

# 变量：是否选择物品 i
x = mp.LpVariable.dicts("x", items, cat=mp.LpBinary)

# 问题
prob = mp.LpProblem("knapsack", mp.LpMaximize)
prob += mp.lpSum(value[i] * x[i] for i in items)
prob += mp.lpSum(weight[i] * x[i] for i in items) <= capacity

# 求解
prob.solve(solver=PULP_CBC_CMD())
print(f"最大价值: {prob.objective.value()}")
for i in items:
    if x[i].varValue > 0.5:
        print(f"  选择 {i}: 重量 {weight[i]}, 价值 {value[i]}")
```

### 有界背包

每个物品有数量上限：

```python
items = ["物品1", "物品2", "物品3"]
weight = {"物品1": 2, "物品2": 3, "物品3": 4}
value = {"物品1": 3, "物品2": 4, "物品3": 5}
max_count = {"物品1": 3, "物品2": 2, "物品3": 5}
capacity = 15

# 变量：物品 i 的数量（整数）
x = {}
for i in items:
    x[i] = mp.LpVariable(f"x_{i}", lowBound=0, upBound=max_count[i], cat=mp.LpInteger)

prob = mp.LpProblem("bounded_knapsack", mp.LpMaximize)
prob += mp.lpSum(value[i] * x[i] for i in items)
prob += mp.lpSum(weight[i] * x[i] for i in items) <= capacity

prob.solve(solver=PULP_CBC_CMD())
```

### 多维背包

多个容量约束（如重量和体积）：

```python
items = ["物品1", "物品2", "物品3", "物品4"]
weight = {"物品1": 2, "物品2": 3, "物品3": 4, "物品4": 5}
volume = {"物品1": 3, "物品2": 2, "物品3": 1, "物品4": 4}
value = {"物品1": 5, "物品2": 4, "物品3": 3, "物品4": 6}
weight_cap = 10
volume_cap = 12

x = mp.LpVariable.dicts("x", items, cat=mp.LpBinary)

prob = mp.LpProblem("multi_knapsack", mp.LpMaximize)
prob += mp.lpSum(value[i] * x[i] for i in items)
prob += mp.lpSum(weight[i] * x[i] for i in items) <= weight_cap
prob += mp.lpSum(volume[i] * x[i] for i in items) <= volume_cap

prob.solve(solver=PULP_CBC_CMD())
```

---

## 设施数量问题示例

### 问题描述

决定在哪些候选位置开设设施，满足所有客户需求，最小化开设成本。

### 数据

```python
facilities = ["F1", "F2", "F3"]
customers = ["C1", "C2", "C3", "C4"]

open_cost = {"F1": 100, "F2": 150, "F3": 120}
serve_cost = {
    ("F1", "C1"): 10, ("F1", "C2"): 20, ("F1", "C3"): 30, ("F1", "C4"): 40,
    ("F2", "C1"): 25, ("F2", "C2"): 15, ("F2", "C3"): 20, ("F2", "C4"): 30,
    ("F3", "C1"): 35, ("F3", "C2"): 25, ("F3", "C3"): 15, ("F3", "C4"): 20,
}
capacity = {"F1": 2, "F2": 3, "F3": 2}
demand = {"C1": 1, "C2": 1, "C3": 1, "C4": 1}
```

### 数学模型

$$
\begin{aligned}
\min \quad & \sum_f o_f y_f + \sum_{f,c} s_{fc} x_{fc} \\
\text{s.t.} \quad & \sum_f x_{fc} = d_c \quad \forall c \\
& \sum_c x_{fc} \leq cap_f y_f \quad \forall f \\
& x_{fc} \geq 0, y_f \in \{0, 1\}
\end{aligned}
$$

### 代码

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 数据（如上）

# 变量
y = mp.LpVariable.dicts("y", facilities, cat=mp.LpBinary)  # 是否开设
x = mp.LpVariable.matrix("x", facilities, customers, lowBound=0)  # 服务量

# 问题
prob = mp.LpProblem("facility", mp.LpMinimize)
prob += mp.lpSum(open_cost[f] * y[f] for f in facilities) + \
        mp.lpSum(serve_cost[(f, c)] * x[f][c] for f in facilities for c in customers)

# 需求约束
for c in customers:
    prob += mp.lpSum(x[f][c] for f in facilities) == demand[c]

# 容量约束
for f in facilities:
    prob += mp.lpSum(x[f][c] for c in customers) <= capacity[f] * y[f]

# 求解
prob.solve(solver=PULP_CBC_CMD())
print(f"总成本: {prob.objective.value()}")
print("开设设施:")
for f in facilities:
    if y[f].varValue > 0.5:
        print(f"  {f} (开设成本 {open_cost[f]})")
```

---

## 旅行商问题示例

### 问题描述

访问所有城市恰好一次并返回起点，最小化总距离。

### 数据

```python
import math

cities = ["北京", "上海", "广州", "深圳"]
coords = {
    "北京": (39.9, 116.4),
    "上海": (31.2, 121.5),
    "广州": (23.1, 113.3),
    "深圳": (22.5, 114.0),
}

def distance(c1, c2):
    lat1, lon1 = coords[c1]
    lat2, lon2 = coords[c2]
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2) * 111  # 近似公里
```

### 数学模型（MTZ 约束）

$$
\begin{aligned}
\min \quad & \sum_{i \neq j} d_{ij} x_{ij} \\
\text{s.t.} \quad & \sum_j x_{ij} = 1 \quad \forall i \quad \text{(出度)} \\
& \sum_i x_{ij} = 1 \quad \forall j \quad \text{(入度)} \\
& u_i - u_j + n x_{ij} \leq n - 1 \quad \text{(消除子回路)} \\
& x_{ij} \in \{0, 1\}
\end{aligned}
$$

### 代码

```python
import minipulp as mp
from minipulp.solvers import PULP_CBC_CMD

# 数据（如上）
n = len(cities)

# 变量
x = {}
for i in cities:
    for j in cities:
        if i != j:
            x[(i, j)] = mp.LpVariable(f"x_{i}_{j}", cat=mp.LpBinary)

u = mp.LpVariable.dicts("u", cities, lowBound=0, upBound=n-1, cat=mp.LpInteger)

# 问题
prob = mp.LpProblem("tsp", mp.LpMinimize)
prob += mp.lpSum(distance(i, j) * x[(i, j)] for i in cities for j in cities if i != j)

# 出度约束
for i in cities:
    prob += mp.lpSum(x[(i, j)] for j in cities if i != j) == 1

# 入度约束
for j in cities:
    prob += mp.lpSum(x[(i, j)] for i in cities if i != j) == 1

# MTZ 消除子回路约束
for i in cities[1:]:  # 跳过起点
    for j in cities[1:]:
        if i != j:
            prob += u[i] - u[j] + n * x[(i, j)] <= n - 1

# 求解
prob.solve(solver=PULP_CBC_CMD())
print(f"最短距离: {prob.objective.value():.1f} 公里")
print("路径:")
for i in cities:
    for j in cities:
        if i != j and x[(i, j)].varValue > 0.5:
            print(f"  {i} → {j}")
```

---

## 求解器选择指南

### 决策树

```
是否整数规划？
├── 是 → PULP_CBC_CMD
└── 否（连续 LP）
    ├── 教学目的 → SimplexCore
    ├── 中规模 → SimplexCpp
    └── 大规模 → PULP_CBC_CMD
```

### 详细选择标准

| 场景 | 推荐求解器 | 原因 |
|------|----------|------|
| 学习单纯形法 | SimplexCore | 透明可跟踪 |
| 小规模连续 LP（<100 变量） | SimplexCore | 无需编译/安装 |
| 中规模连续 LP（100-1000） | SimplexCpp | 性能好，无外部依赖 |
| 大规模连续 LP（>1000） | PULP_CBC_CMD | CBC 优化程度高 |
| 整数规划 | PULP_CBC_CMD | 唯一支持 |
| 二元变量 | PULP_CBC_CMD | 唯一支持 |
| 需要对偶值 | PULP_CBC_CMD | Simplex 系列不提供 |
| 需要时间限制 | PULP_CBC_CMD | 唯一支持 |

### 性能基准

```python
import time
from minipulp.solvers import SimplexCore, SimplexCpp, PULP_CBC_CMD

# 创建测试问题
prob = create_test_problem(n_vars=500)

for solver_cls in [SimplexCore, SimplexCpp, PULP_CBC_CMD]:
    solver = solver_cls()
    if not solver.available():
        continue
    t0 = time.perf_counter()
    prob.solve(solver=solver)
    t = time.perf_counter() - t0
    print(f"{solver_cls.__name__}: {t:.3f}s, obj={prob.objective.value():.2f}")
```

---

## 时间限制和日志输出

### 时间限制

```python
from minipulp.solvers import PULP_CBC_CMD

# 设置 60 秒时间限制
solver = PULP_CBC_CMD(timeLimit=60)
prob.solve(solver=solver)

if prob.status == mp.LpStatus.NOT_SOLVED:
    print("求解超时")
```

CBC 的 `-sec` 参数控制求解时间：

```python
cmd = [self.path, lp_path, "-solve", "-solution", sol_path]
if self.timeLimit:
    cmd.extend(["-sec", str(self.timeLimit)])
```

### 日志输出

```python
# 静默（默认）
solver = PULP_CBC_CMD(msg=False)

# 显示 CBC 输出
solver = PULP_CBC_CMD(msg=True)
prob.solve(solver=solver)
# CBC 会打印求解进度：
# "Continuous solution value of -180.0"
# "Branch and Cut..."
# "Optimal solution found"
```

`msg=True` 时，`subprocess.run` 不捕获 stdout，让 CBC 直接输出到终端：

```python
if self.msg:
    result = subprocess.run(cmd, text=True, timeout=...)
else:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=...)
```

### 调试技巧

```python
# 1. 查看生成的 LP 文件
lp_text = mp.write_lp(prob)
print(lp_text)

# 2. 显示 CBC 日志
prob.solve(solver=PULP_CBC_CMD(msg=True))

# 3. 手动运行 CBC
# 将 LP 文件保存到磁盘
with open("model.lp", "w") as f:
    f.write(mp.write_lp(prob))
# 然后命令行运行：cbc model.lp -solve -solution model.sol
# 检查 model.sol 文件
```

---

## 测试

```bash
uv run pytest tests/solvers/test_cbc_cmd.py -v
```

8 个测试覆盖：连续 LP 求解、整数规划、二元变量、不可行检测、CBC 可用性检查。

### 测试示例

```python
def test_continuous_lp():
    x = LpVariable("x", lowBound=0)
    y = LpVariable("y", lowBound=0)
    prob = LpProblem("test", LpSense.MAXIMIZE)
    prob += 3 * x + 2 * y
    prob += 2 * x + y <= 100
    prob += x + y <= 80
    prob.solve(solver=PULP_CBC_CMD())
    assert prob.status == LpStatus.OPTIMAL
    assert abs(x.varValue - 20) < 1e-6
    assert abs(y.varValue - 60) < 1e-6

def test_integer_program():
    x = LpVariable("x", lowBound=0, cat=LpInteger)
    y = LpVariable("y", lowBound=0, cat=LpInteger)
    prob = LpProblem("test", LpSense.MAXIMIZE)
    prob += 3 * x + 2 * y
    prob += 2 * x + y <= 100
    prob += x + y <= 80
    prob.solve(solver=PULP_CBC_CMD())
    assert prob.status == LpStatus.OPTIMAL
    assert x.varValue == int(x.varValue)  # 整数解
    assert y.varValue == int(y.varValue)

def test_infeasible():
    x = LpVariable("x", lowBound=0)
    prob = LpProblem("test", LpSense.MAXIMIZE)
    prob += x
    prob += x <= 10
    prob += x >= 20  # 不可行
    prob.solve(solver=PULP_CBC_CMD())
    assert prob.status == LpStatus.INFEASIBLE
```

---

## 求解器对比

| 求解器 | 算法 | 整数规划 | 依赖 | 性能 |
|-------|------|---------|------|------|
| `SimplexCore` | 两阶段单纯形法 | 不支持 | 零依赖 | 慢（教学用） |
| `SimplexCpp` | C++ 两阶段单纯形法 | 不支持 | 需编译 | 10-50x 加速 |
| `PULP_CBC_CMD` | 分支定界 + 割平面 | 支持 | 需安装 CBC | 工业级 |

**选择建议**：

- 教学/学习 → `SimplexCore`（透明可跟踪）
- 中规模连续 LP → `SimplexCpp`（性能好）
- 整数规划/大规模 → `PULP_CBC_CMD`（工业级）

---

## 总结

Phase 4 的 CBC 求解器对接是 minipulp 连接工业级求解能力的关键，其设计要点：

1. **文件中转范式**：通过 LP/SOL 文件与 CBC 通信，解耦建模与求解
2. **临时文件管理**：`TemporaryDirectory` 自动清理
3. **状态解析**：正则匹配 `.sol` 文件中的状态行
4. **整数规划支持**：`General`/`Binary` 段，分支定界
5. **参数控制**：时间限制、日志输出
6. **错误处理**：可用性检查、超时、文件缺失

这套设计让 minipulp 既能用教学求解器（SimplexCore）透明演示算法，又能用工业求解器（CBC）求解实际问题，是教学与实用的完美平衡。
