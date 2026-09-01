"""求解器抽象基类 — 定义求解器协议。

本模块在 Phase 3/4 完整实现，当前为骨架。
"""

from __future__ import annotations

from ..constants import LpStatus
from ..problem import LpProblem


class LpSolver:
    """求解器抽象基类。

    所有求解器后端继承此类，实现 ``actualSolve(problem)``。
    这一层抽象是"多后端可插拔"设计的核心：
    建模层（LpProblem）只依赖此接口，不关心具体求解器实现。

    子类需实现：
    - ``available()`` : 检查求解器是否可用（如命令行是否存在）。
    - ``actualSolve(problem)`` : 实际求解，回填 varValue 与 status。
    """

    name: str = "base"

    def __init__(self, **options) -> None:
        self.options = options

    def available(self) -> bool:
        """求解器是否可用（命令行存在 / 库已加载）。"""
        raise NotImplementedError

    def actualSolve(self, problem: LpProblem) -> LpStatus:
        """实际求解。子类实现：生成输入 → 调求解器 → 解析输出 → 回填。"""
        raise NotImplementedError

    def solve(self, problem: LpProblem) -> LpStatus:
        """求解入口：检查可用性后委托 actualSolve。"""
        if not self.available():
            raise RuntimeError(f"solver {self.name} is not available")
        return self.actualSolve(problem)