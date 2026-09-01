# Phase 3 — 单纯形法核心

> 两阶段单纯形法的两层实现：纯 Python（L0 教学透明）+ C++/pybind11（L1 性能加速）。

## Phase 3a — 纯 Python 单纯形法

对应 `src/minipulp/solvers/simplex_py.py`。

### 算法

详见 [单纯形法推导](../principles/simplex.md)。

### 使用

```python
from minipulp.solvers import SimplexCore
prob.solve(solver=SimplexCore())
```

### 测试

```bash
uv run pytest tests/solvers/test_simplex_py.py -v
```

---

## Phase 3b — C++ 核心 + pybind11 绑定

对应：

- `src/minipulp/core/simplex_core.cpp` — C++ 两阶段单纯形法 + pybind11 绑定
- `src/minipulp/core/CMakeLists.txt` — CMake 构建配置
- `src/minipulp/core/build.py` — 编译脚本（CMake + pybind11）
- `src/minipulp/solvers/simplex_cpp.py` — Python 求解器包装层

### 设计意图

展示"建模层 Python（灵活、可读）/ 计算层 C++（性能、数值稳定）"的分工范式。

C++ 的算法逻辑与 `simplex_py.py` **完全一致**，便于对照阅读。
两者共享提取（`_extract`）和回填（`_backfill`）逻辑，仅核心计算层不同：

```
LpProblem ──→ _extract ──→ [cost, A, b, senses] ──→ solve_simplex ──→ solution ──→ _backfill ──→ varValue
                                  │                                        │
                          SimplexCore (Python)                    SimplexCpp (C++)
                          simplex_py.py                           simplex_cpp.py + _native.pyd
```

### 编译

```bash
# 需要 g++ 和 CMake 在 PATH 中
uv run python src/minipulp/core/build.py
```

编译产物 `_native.cp3XY-win_amd64.pyd`（Windows）或 `_native.so`（Linux）放在
`src/minipulp/core/` 目录下，随包一起分发。

CMakeLists.txt 使用 pybind11 提供的 `pybind11_add_module` 宏自动处理链接：

```cmake
cmake_minimum_required(VERSION 3.15)
project(minipulp_core LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(_native simplex_core.cpp)
```

### 使用

```python
from minipulp.solvers import SimplexCpp
prob.solve(solver=SimplexCpp())
```

若 C++ 扩展已编译，`prob.solve()` 默认使用 `SimplexCpp`；否则回退到 `SimplexCore`。

### 测试

```bash
uv run pytest tests/solvers/test_simplex_cpp.py -v
```

测试包含 C++ 与纯 Python 结果一致性验证（`TestCppPyConsistency`）。

### 性能对比

C++ 核心比纯 Python 快 10-50x（取决于问题规模），适合中等规模 LP（变量数 < 1000）。
大规模问题请用 CBC/GLPK 等工业级求解器。
