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
- [测试](#测试)

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

## 测试

```bash
uv run pytest tests/solvers/test_cbc_cmd.py -v
```

8 个测试覆盖：连续 LP 求解、整数规划、二元变量、不可行检测、CBC 可用性检查。

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
