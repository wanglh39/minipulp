# LP 文件格式规范

> 建模层与求解层的通信协议：CPLEX LP 格式。

---

## 为什么需要文件格式

建模库（minipulp）和求解器（CBC、GLPK）是独立程序，需要通过文件交换问题描述。LP 格式是 CPLEX 定义的人类可读格式，是 OR 生态最通用的"语言"。

```
minipulp ──write_lp──→ model.lp ──cbc──→ model.sol ──parse──→ 回填
```

---

## 格式结构

```
\ Problem name: demo          ← 注释行（\ 开头）
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

---

## 各段详解

### 目标段

```
Maximize
  obj: 3 x + 2 y
```

或 `Minimize`。`obj:` 是目标行名（可任意）。系数 1 可省略：`x` 等价于 `1 x`。

### 约束段

```
Subject To
  c_0: 2 x + 1 y <= 100
  c_1: x - y >= 2
  c_2: x + y = 10
```

约束名后跟冒号。方向符 `<=`、`>=`、`=`。右端项是常数。

### Bounds 段

```
Bounds
  x >= 0              ← 只有下界
  y <= 10             ← 只有上界
  0 <= z <= 5         ← 双界
  w free              ← 无界（自由变量）
End
```

**省略 Bounds 段时，所有变量默认 `>= 0`。**

### General / Binary 段

```
General
  z1 z2 z3            ← 整数变量

Binary
  b1 b2               ← 0/1 变量
```

---

## 归一化约定

minipulp 内部把约束存为 `lhs (<=|==|>=) 0` 的齐次形式。导出 LP 时把常数项移回右边：

内部：`LpAffineExpression({x: 3, y: 2}, const=-100), sense=LE`
即 `3x + 2y - 100 <= 0`

导出：`3 x + 2 y <= 100`（rhs = -const = 100）

---

## minipulp 的实现

```python
def write_lp(problem):
    lines = [f"\\ Problem name: {problem.name}"]
    lines.append("Maximize" if problem.sense == MAXIMIZE else "Minimize")
    lines.append(f"  obj: {_format_terms(problem.objective.terms)}")
    if problem.constraints:
        lines.append("Subject To")
        for name, con in problem.constraints.items():
            rhs = -con.constant  # 常数项移到右边
            lines.append(f"  {name}: {_format_terms(con.terms)} {op} {rhs}")
    # ... Bounds, General, Binary ...
    lines.append("End")
    return "\n".join(lines)
```

---

## 完整示例

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

输出：

```
\ Problem name: demo
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