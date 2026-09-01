# Phase 2 — 约束与问题

> `LpProblem` 容器与 LP 文件格式导出。

本篇对应 `src/minipulp/problem.py` 和 `src/minipulp/lp_io.py`。

## `+=` 语法糖

```python
prob += 3 * x + 2 * y          # 表达式 → 设置目标
prob += 2 * x + y <= 100       # 约束 → 添加约束
```

详见 [LP 文件格式](../principles/lp-format.md)。

## 测试

```bash
uv run pytest tests/test_problem.py tests/test_lp_io.py -v
```