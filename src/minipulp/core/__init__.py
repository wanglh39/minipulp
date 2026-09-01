"""C++ 单纯形法核心 + pybind11 绑定。

本目录在 Phase 3 实现教学用单纯形法求解器：
- ``simplex_core.cpp`` : C++ 实现两阶段单纯形法，代码透明。
- ``binding.cpp``      : pybind11 绑定层。
- ``_native``          : 编译产物（.pyd/.so），由 setup 或 CMake 生成。

设计意图：讲清"建模层用 Python（灵活、可读）、计算层用 C++（性能、数值稳定）"
的分工范式，详见 docs/tutorial/phase3-simplex-core.md。
"""