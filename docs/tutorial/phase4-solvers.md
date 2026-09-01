# Phase 4 — CBC/GLPK 求解器对接

> 工业级通信范式：`LpProblem → .lp 文件 → cbc → .sol 文件 → 回填`。

本篇对应 `src/minipulp/solvers/cbc_cmd.py`。

## CBC 对接

```python
from minipulp.solvers import PULP_CBC_CMD
prob.solve(solver=PULP_CBC_CMD())
```

通信流程：

1. `write_lp` 生成 CPLEX LP 格式文件
2. `subprocess` 调用 `cbc model.lp -solve -solution model.sol`
3. 解析 `.sol` 文件提取状态与变量值
4. 回填到 `LpVariable.varValue`

## 优势

CBC 支持整数规划（分支定界），这是 `SimplexCore` 不具备的：

```python
x = mp.LpVariable("x", cat=mp.LpInteger)  # 整数变量
```

## 测试

```bash
uv run pytest tests/solvers/test_cbc_cmd.py -v
```