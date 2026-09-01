# Phase 3 — 纯 Python 单纯形法核心

> `SimplexCore`：两阶段单纯形法，代码透明，零依赖。

本篇对应 `src/minipulp/solvers/simplex_py.py`。

## 算法

详见 [单纯形法推导](../principles/simplex.md)。

## 使用

```python
from minipulp.solvers import SimplexCore
prob.solve(solver=SimplexCore())
```

## 测试

```bash
uv run pytest tests/solvers/test_simplex_py.py -v
```

!!! note "C++ 核心 + pybind11"
    L2 进阶求解器（C++ 实现单纯形法核心 + pybind11 绑定）待网络恢复后补充，
    用于展示 Python 建模层 / C++ 计算层分工范式。