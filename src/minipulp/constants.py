"""minipulp 常量定义。

本模块定义线性规划建模所需的全部枚举常量。
这些常量是整个库的"词汇表"，所有模块都从这里引用语义。
"""

from enum import IntEnum


class LpSense(IntEnum):
    """目标函数方向（求最大化还是最小化）。"""
    MINIMIZE = 1
    MAXIMIZE = -1


class LpCat(IntEnum):
    """变量类别（连续、整数、二元）。

    求解器根据类别选择不同算法分支：
    - Continuous: 单纯形法 / 内点法
    - Integer:    分支定界 (B&B)
    - Binary:     B&B + 0/1 截断
    """
    CONTINUOUS = 0
    INTEGER = 1
    BINARY = 2


class LpConstraintSense(IntEnum):
    """约束方向。

    约束在内部统一归一化为 ``expr <= 0`` / ``expr >= 0`` / ``expr == 0`` 形式，
    此枚举记录原始方向，用于 LP 文件输出与对偶解符号判断。
    """
    LE = 0   # <=
    EQ = 1   # ==
    GE = 2   # >=


class LpStatus(IntEnum):
    """求解状态码。

    采用与 PuLP 兼容的整数编码，便于状态映射层对接各求解器。
    """
    NOT_SOLVED = 0
    OPTIMAL = 1
    INFEASIBLE = -1
    UNBOUNDED = -2
    UNDEFINED = -3
    INFEASIBLE_OR_UNBOUNDED = -4


LpMinimize = LpSense.MINIMIZE
LpMaximize = LpSense.MAXIMIZE

LpContinuous = LpCat.CONTINUOUS
LpInteger = LpCat.INTEGER
LpBinary = LpCat.BINARY

LpStatusOptimal = LpStatus.OPTIMAL
LpStatusInfeasible = LpStatus.INFEASIBLE
LpStatusUnbounded = LpStatus.UNBOUNDED
LpStatusNotSolved = LpStatus.NOT_SOLVED
LpStatusUndefined = LpStatus.UNDEFINED


LpStatusToMsg = {
    LpStatus.NOT_SOLVED: "Not Solved",
    LpStatus.OPTIMAL: "Optimal",
    LpStatus.INFEASIBLE: "Infeasible",
    LpStatus.UNBOUNDED: "Unbounded",
    LpStatus.UNDEFINED: "Undefined",
    LpStatus.INFEASIBLE_OR_UNBOUNDED: "Infeasible or Unbounded",
}