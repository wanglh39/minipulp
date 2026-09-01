"""CBC 命令行求解器对接 — 工业级通信范式（L1）。

本模块展示建模库与工业求解器的标准通信范式：

    LpProblem → write_lp → .lp 文件 → subprocess 调 cbc → .sol 文件 → 解析 → 回填

这一"文件中转"范式是 OR 生态的主流：建模库不嵌入求解器代码，
而是通过标准文件格式（LP/MPS）与求解器进程通信。好处是解耦——
换求解器只需换命令行，不改建模代码。

CBC（Coin-or Branch and Cut）是开源 MILP 求解器，支持整数规划。
详见 https://github.com/coin-or/Cbc
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from ..constants import LpStatus
from ..problem import LpProblem
from ..lp_io import write_lp
from .base import LpSolver

_STATUS_PATTERNS = {
    LpStatus.OPTIMAL: re.compile(r"optimal", re.IGNORECASE),
    LpStatus.INFEASIBLE: re.compile(r"infeasible", re.IGNORECASE),
    LpStatus.UNBOUNDED: re.compile(r"unbounded", re.IGNORECASE),
}


class PULP_CBC_CMD(LpSolver):
    """CBC 命令行求解器。

    通信流程：
    1. 用 ``write_lp`` 将问题序列化为 CPLEX LP 格式文件。
    2. 通过 ``subprocess`` 调用 ``cbc model.lp -solve -solution model.sol``。
    3. 解析 ``.sol`` 文件，提取状态与变量值。
    4. 回填到 ``LpVariable.varValue``。

    Parameters
    ----------
    path : str | None
        CBC 可执行文件路径。None 时用 ``shutil.which`` 自动查找。
    msg : bool, default False
        是否显示 CBC 求解器输出。
    timeLimit : int | None
        求解时间上限（秒）。

    Examples
    --------
    >>> import minipulp as mp
    >>> from minipulp.solvers import PULP_CBC_CMD
    >>> prob = mp.LpProblem("demo", mp.LpMaximize)
    >>> # ... 建模 ...
    >>> prob.solve(solver=PULP_CBC_CMD())
    """

    name = "PULP_CBC_CMD"

    def __init__(
        self,
        path: str | None = None,
        msg: bool = False,
        timeLimit: int | None = None,
    ) -> None:
        super().__init__()
        self.path = path or shutil.which("cbc")
        self.msg = msg
        self.timeLimit = timeLimit

    def available(self) -> bool:
        """CBC 可执行文件是否存在。"""
        if self.path is None:
            self.path = shutil.which("cbc")
        return self.path is not None and os.path.isfile(self.path)

    def actualSolve(self, problem: LpProblem) -> LpStatus:
        if not self.available():
            raise RuntimeError(f"CBC not found at {self.path}")

        lp_text = write_lp(problem)

        with tempfile.TemporaryDirectory() as tmpdir:
            lp_path = os.path.join(tmpdir, "model.lp")
            sol_path = os.path.join(tmpdir, "model.sol")

            with open(lp_path, "w", encoding="ascii") as f:
                f.write(lp_text)

            cmd = [self.path, lp_path, "-solve", "-solution", sol_path]
            if self.timeLimit:
                cmd.extend(["-sec", str(self.timeLimit)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeLimit + 60 if self.timeLimit else 300,
            )
            if self.msg:
                print(result.stdout)

            if not os.path.isfile(sol_path):
                raise RuntimeError(
                    f"CBC 未生成 solution 文件。stderr: {result.stderr}"
                )

            with open(sol_path, "r", encoding="ascii") as f:
                sol_text = f.read()

            status, values = self._parse_sol(sol_text, problem)
            self._backfill(problem, status, values)
            return status

    def _parse_sol(self, sol_text: str, problem: LpProblem) -> tuple[LpStatus, dict]:
        """解析 CBC .sol 文件。

        文件含多段解（初始解 + 最优解），取最后一段。
        每段以状态行开头，后跟变量值行::

            Optimal - objective value 180.00000000
                  0 x                     20                       0
                  1 y                     60                       0
        """
        lines = sol_text.strip().split("\n")

        status = LpStatus.UNDEFINED
        values: dict[str, float] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            matched_status = False
            for code, pattern in _STATUS_PATTERNS.items():
                if pattern.search(line):
                    status = code
                    matched_status = True
                    values = {}
                    break
            if matched_status:
                continue

            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit():
                var_name = parts[1]
                try:
                    var_value = float(parts[2])
                    values[var_name] = var_value
                except ValueError:
                    pass

        return status, values

    def _backfill(self, problem: LpProblem, status: LpStatus, values: dict) -> None:
        """将解值写回 LpVariable.varValue。"""
        for var in problem.variables():
            if status == LpStatus.OPTIMAL and var.name in values:
                var.varValue = values[var.name]
            else:
                var.varValue = None