# Phase 1 — 表达式系统

> 运算符重载如何把 `3*x + 2*y` 变成 `LpAffineExpression({x: 3, y: 2})`。

本篇对应 `src/minipulp/elements.py`，是整个库的代数核心。

## 核心类

```
LpElement ──> LpAffineExpression ──> LpVariable
```

- `LpElement`：基类，定义运算符协议
- `LpAffineExpression`：`{var: coef}` 字典 + 常数项，实现所有运算符
- `LpVariable`：继承表达式，是单变量表达式 `{self: 1}`

## 运算符重载

详见 [运算符重载机制](../principles/operator-overloading.md)。

## 测试

```bash
uv run pytest tests/test_elements.py -v
```

43 个测试覆盖：变量构造、标量乘法、加减除、复合表达式、约束构造、lpSum、value 求值。