# minipulp — 从零实现 PuLP

> 一个教学项目，从零复刻 [PuLP](https://github.com/coin-or/pulp) 线性规划建模库的核心设计，理解其设计哲学与底层原理。

---

## 为什么有这个项目？

PuLP 是 Python 生态最流行的线性规划建模库之一，但它的源码对初学者并不友好——大量历史包袱、防御性代码、多求解器适配逻辑交织在一起，让人难以抓住主线。

本项目不追求功能完整复刻，而是**聚焦核心设计哲学**，用最透明的代码讲清楚四件事：

1. **建模与求解分离** — `LpProblem` 只描述问题，`LpSolver` 只求解问题，二者通过 LP 文件格式通信。
2. **代数表达式即代码** — 运算符重载让 `3*x + 2*y <= 10` 直接构建表达式对象，而非字符串解析。
3. **仿射表达式的闭包性** — 变量、常数、表达式的线性运算结果仍是仿射表达式，用 `{var: coef}` 字典即可完整表示。
4. **多后端可插拔** — 求解器是一组同接口子类，换求解器只换 `solve(solver=...)` 一个参数。

## 30 秒上手

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y          # 目标函数
prob += 2 * x + y <= 100       # 约束 1
prob += x + y <= 80            # 约束 2
prob += x <= 40                # 约束 3

prob.solve()
print(prob.status, prob.objective.value())  # Optimal 200.0
```

## 阅读路线

=== "我是初学者"

    按顺序读教程，每篇都包含「原理 → 代码 → 测试 → 运行」完整闭环：

    1. [Phase 1 - 表达式系统](tutorial/phase1-expressions.md) — 运算符重载如何把代数式变成对象
    2. [Phase 2 - 约束与问题](tutorial/phase2-problem.md) — 问题容器与 LP 文件格式
    3. [Phase 3 - C++ 单纯形法核心](tutorial/phase3-simplex-core.md) — Python 建模层 / C++ 计算层分工
    4. [Phase 4 - CBC/GLPK 对接](tutorial/phase4-solvers.md) — 工业级求解器通信范式

=== "我想理解设计"

    先读设计哲学，再按需深入：

    - [四大设计原则](principles/philosophy.md)
    - [运算符重载机制](principles/operator-overloading.md)
    - [仿射表达式闭包性](principles/affine-closure.md)
    - [LP 文件格式规范](principles/lp-format.md)
    - [单纯形法推导](principles/simplex.md)

=== "我要查 API"

    - [API 参考](api/minipulp.md)

## 求解器后端

| 求解器 | 类型 | 教学要点 |
|--------|------|----------|
| `SimplexCore` | C++ + pybind11 | 透明单纯形法，讲清主元/转轴/基变量，Python/C++ 分工 |
| `PULP_CBC_CMD` | 命令行对接 | 工业级通信范式：生成 .lp → 调 cbc → 解析 .sol |
| `GLPK_CMD` | 命令行对接 | 展示多后端可插拔设计 |

## 项目结构

```
src/minipulp/            核心实现
  constants.py           常量与枚举（词汇表）
  elements.py            变量与表达式（代数层）
  constraints.py         约束
  problem.py             问题容器（建模层）
  lp_io.py               LP/MPS 文件读写（中间表示）
  solvers/               求解器后端（求解层）
  core/                  C++ 单纯形法核心 + pybind11
tests/                   镜像目录结构测试
docs/                    本文档站
examples/                经典 LP 问题示例
```

## License

MIT