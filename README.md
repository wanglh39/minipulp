# minipulp — 从零实现 PuLP

> 一个教学项目，从零复刻 [PuLP](https://github.com/coin-or/pulp) 线性规划建模库的核心设计，理解其设计哲学与底层原理。

## 为什么有这个项目？

PuLP 是 Python 生态最流行的线性规划建模库之一，但它的源码对初学者并不友好。本项目不追求功能完整复刻，而是**聚焦核心设计哲学**，用最透明的代码讲清楚四件事：

1. **建模与求解分离** — `LpProblem` 描述问题，`LpSolver` 求解问题，二者通过 LP 文件格式通信。
2. **代数表达式即代码** — 运算符重载让 `3*x + 2*y <= 10` 直接构建表达式对象。
3. **仿射表达式的闭包性** — 变量、常数、表达式的线性运算结果仍是仿射表达式，用 `{var: coef}` 字典即可表示。
4. **多后端可插拔** — 求解器是一组同接口子类，换求解器只换一个参数。

## 快速开始

```bash
pip install -e ".[test]"
pytest
```

```python
import minipulp as mp

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("demo", mp.LpMaximize)
prob += 3 * x + 2 * y          # 目标函数
prob += 2 * x + y <= 100       # 约束 1
prob += x + y <= 80            # 约束 2
prob += x <= 40                # 约束 3

prob.solve()                   # 默认求解器
print(prob.status, prob.objective.value())  # Optimal 200.0
```

## 求解器后端

| 求解器 | 类型 | 说明 |
|--------|------|------|
| `SimplexCore` | C++ + pybind11 | 教学用单纯形法，代码透明，讲清主元/转轴/基变量 |
| `PULP_CBC_CMD` | 命令行对接 | 工业级通信范式，生成 .lp → 调 cbc → 解析 .sol |
| `GLPK_CMD` | 命令行对接 | 展示多后端可插拔设计 |

## 文档

完整教程与原理讲解：[GitHub Pages 站点](https://your-username.github.io/minipulp/)

## 项目结构

```
src/minipulp/        核心实现
  elements.py        变量与表达式（运算符重载）
  constraints.py     约束
  problem.py         问题容器
  lp_io.py           LP 文件读写
  solvers/           求解器后端
  core/              C++ 单纯形法核心 + pybind11 绑定
tests/               镜像目录结构测试
docs/                MkDocs Material 文档
examples/            经典 LP 问题示例
```

## License

MIT