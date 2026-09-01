"""求解器后端 — 多后端可插拔设计。

每个求解器继承 LpSolver，实现 actualSolve()。
换求解器只需换 ``prob.solve(solver=...)`` 参数。

可用求解器：
- SimplexCore   : 纯 Python 两阶段单纯形法（L0 教学求解器）
- SimplexCpp    : C++ 两阶段单纯形法（L1，pybind11 绑定）
- PULP_CBC_CMD  : CBC 命令行对接（L1 工业级通信范式）
"""

from .base import LpSolver
from .simplex_py import SimplexCore
from .simplex_cpp import SimplexCpp
from .cbc_cmd import PULP_CBC_CMD

__all__ = ["LpSolver", "SimplexCore", "SimplexCpp", "PULP_CBC_CMD"]
