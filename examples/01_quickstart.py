"""快速上手示例：经典生产计划问题。

    max  3x + 2y
    s.t. 2x + y <= 100
         x + y <= 80
         x    <= 40
         x, y >= 0

最优解：x=20, y=60, obj=180
"""
import minipulp as mp
from minipulp import write_lp
from minipulp.solvers import SimplexCore

x = mp.LpVariable("x", lowBound=0)
y = mp.LpVariable("y", lowBound=0)

prob = mp.LpProblem("production_plan", mp.LpMaximize)
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
prob += x + y <= 80
prob += x <= 40

print("=" * 50)
print("问题建模完成")
print(f"  变量数: {prob.numVariables()}")
print(f"  约束数: {prob.numConstraints()}")
print()

print("=" * 50)
print("LP 文件格式输出")
print("=" * 50)
print(write_lp(prob))
print()

print("=" * 50)
print("求解（SimplexCore 纯 Python 单纯形法）")
print("=" * 50)
status = prob.solve(solver=SimplexCore())
print(f"  状态: {prob.status_msg}")
print(f"  x = {x.varValue}")
print(f"  y = {y.varValue}")
print(f"  目标值 = {prob.objective.value()}")
