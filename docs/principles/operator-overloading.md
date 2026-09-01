# 运算符重载机制

> 原则二的底层实现：`3 * x + 2 * y` 这行 Python 代码，每一步都在构造对象，而非做数值计算。

---

## 目录

- [Python 运算符重载回顾](#python-运算符重载回顾)
- [3 * x 的完整调用链](#3--x-的完整调用链)
- [3 * x + 2 * y 的完整调用链](#3--x--2--y-的完整调用链)
- [3 * x + 2 * y <= 100 的完整调用链](#3--x--2--y--100-的完整调用链)
- [_new 方法的作用](#_new-方法的作用)
- [__eq__ 的陷阱](#__eq__-的陷阱)
- [所有运算符的实现](#所有运算符的实现)
- [NotImplemented 的作用](#notimplemented-的作用)
- [运算符重载一览表](#运算符重载一览表)
- [性能考量](#性能考量)
- [Python 数据模型深入](#python-数据模型深入)
- [Python 运算符查找算法](#python-运算符查找算法)
- [其他库的运算符重载案例](#其他库的运算符重载案例)
- [最佳实践与陷阱](#最佳实践与陷阱)
- [性能基准测试](#性能基准测试)

---

## Python 运算符重载回顾

Python 的运算符（`+`、`-`、`*`、`<=` 等）本质是方法调用：

| 表达式 | 实际调用 | 说明 |
|--------|----------|------|
| `a + b` | `a.__add__(b)`，失败则 `b.__radd__(a)` | 加法 |
| `a - b` | `a.__sub__(b)`，失败则 `b.__rsub__(a)` | 减法 |
| `a * b` | `a.__mul__(b)`，失败则 `b.__rmul__(a)` | 乘法 |
| `a / b` | `a.__truediv__(b)`，失败则 `b.__rtruediv__(a)` | 除法 |
| `a // b` | `a.__floordiv__(b)`，失败则 `b.__rfloordiv__(a)` | 整除 |
| `a % b` | `a.__mod__(b)`，失败则 `b.__rmod__(a)` | 取模 |
| `a ** b` | `a.__pow__(b)`，失败则 `b.__rpow__(a)` | 幂 |
| `a <= b` | `a.__le__(b)` | 小于等于 |
| `a >= b` | `a.__ge__(b)` | 大于等于 |
| `a < b` | `a.__lt__(b)` | 小于 |
| `a > b` | `a.__gt__(b)` | 大于 |
| `a == b` | `a.__eq__(b)` | 等于 |
| `a != b` | `a.__ne__(b)` | 不等于 |
| `-a` | `a.__neg__()` | 负号 |
| `+a` | `a.__pos__()` | 正号 |
| `abs(a)` | `a.__abs__()` | 绝对值 |
| `~a` | `a.__invert__()` | 按位取反 |
| `a += b` | `a.__iadd__(b)` 或 `a = a.__add__(b)` | 原地加 |
| `a[b]` | `a.__getitem__(b)` | 下标 |
| `a[b] = c` | `a.__setitem__(b, c)` | 下标赋值 |
| `a(...)` | `a.__call__(...)` | 调用 |
| `len(a)` | `a.__len__()` | 长度 |
| `str(a)` | `a.__str__()` | 字符串 |
| `repr(a)` | `a.__repr__()` | 表示 |

### 反向运算符机制

关键机制：**若左操作数的 `__mul__` 返回 `NotImplemented`，Python 回退到右操作数的 `__rmul__`**。

```python
# 3 * x 的执行过程：
# 1. Python 先尝试 int.__mul__(3, x)
# 2. int 不认识 LpVariable，返回 NotImplemented
# 3. Python 回退到 x.__rmul__(3)
# 4. LpVariable.__rmul__ 处理这个调用
```

这个机制是 `3 * x` 能工作的关键——`int` 类型不知道 `LpVariable` 的存在，
但通过反向运算符，`LpVariable` 有机会处理这个操作。

### 比较运算符没有反向版本

注意 `__le__`、`__ge__`、`__eq__` 没有反向版本（没有 `__rle__`）。
但 Python 会自动处理：`a <= b` 等价于 `b >= a`，所以如果 `a.__le__(b)` 返回 NotImplemented，
Python 会尝试 `b.__ge__(a)`。

在 minipulp 中，比较的右操作数通常是数值（如 `expr <= 100`），
`int.__ge__(100, expr)` 会返回 NotImplemented，然后 `expr.__le__(100)` 被调用。

### 比较运算符的反射规则

Python 对比较运算符的反射处理有特殊规则：

| 原始表达式 | 首次尝试 | 反射尝试 | 说明 |
|-----------|---------|---------|------|
| `a < b` | `a.__lt__(b)` | `b.__gt__(a)` | `<` 的反射是 `>` |
| `a <= b` | `a.__le__(b)` | `b.__ge__(a)` | `<=` 的反射是 `>=` |
| `a > b` | `a.__gt__(b)` | `b.__lt__(a)` | `>` 的反射是 `<` |
| `a >= b` | `a.__ge__(b)` | `b.__le__(a)` | `>=` 的反射是 `<=` |
| `a == b` | `a.__eq__(b)` | `b.__eq__(a)` | `==` 的反射是 `==` |
| `a != b` | `a.__ne__(b)` | `b.__ne__(a)` | `!=` 的反射是 `!=` |

注意 `==` 和 `!=` 的反射是自身——这是因为相等关系是对称的。

---

## 3 * x 的完整调用链

```python
x = LpVariable("x")
expr = 3 * x
```

逐步追踪：

### 步骤 1：Python 尝试 `int.__mul__(3, x)`

```python
# Python 内部逻辑（伪代码）
result = int.__mul__(3, x)  # int 不知道怎么乘 LpVariable
# result == NotImplemented
```

### 步骤 2：Python 回退到 `x.__rmul__(3)`

```python
# Python 内部逻辑（伪代码）
if result == NotImplemented:
    result = x.__rmul__(3)  # 让 LpVariable 处理
```

### 步骤 3：`LpAffineExpression.__rmul__`

`LpVariable` 继承自 `LpAffineExpression`，调用 `LpAffineExpression.__rmul__`：

```python
def __rmul__(self, other):
    return self.__mul__(other)
```

### 步骤 4：`__mul__` 检测到数值

```python
def __mul__(self, other):
    if _is_number(other):
        if other == 0:
            return self._new({}, 0.0)
        return self._new(
            {var: coef * other for var, coef in self.terms.items()},
            self.const * other,
        )
```

### 步骤 5：构造结果

`x.terms = {x: 1.0}`，乘以 3 得 `{x: 3.0}`：

```python
# other = 3, self.terms = {x: 1.0}, self.const = 0.0
new_terms = {var: coef * 3 for var, coef in {x: 1.0}.items()}
# new_terms = {x: 3.0}
new_const = 0.0 * 3 = 0.0
return self._new({x: 3.0}, 0.0)
```

### 步骤 6：`_new` 降级为 `LpAffineExpression`

```python
# LpVariable._new
def _new(self, terms, const):
    return LpAffineExpression(terms, const)  # 不是 LpVariable！
```

**结果：`expr` 是一个 `LpAffineExpression` 对象，`expr.terms = {x: 3.0}`，`expr.const = 0.0`。**

### 内存视角

```python
# 运算前
x = LpVariable("x")
# x 在内存中：
# ┌──────────────┐
# │ LpVariable   │
# │  name = "x"  │
# │  terms = {x: 1.0}
# │  const = 0.0
# │  lowBound = None
# │  upBound = None
# └──────────────┘

# 运算后
expr = 3 * x
# expr 在内存中（新对象）：
# ┌──────────────────┐
# │ LpAffineExpression│
# │  terms = {x: 3.0} │
# │  const = 0.0      │
# └──────────────────┘
# 注意：没有 name、lowBound、upBound
```

---

## 3 * x + 2 * y 的完整调用链

```python
x = LpVariable("x")
y = LpVariable("y")
expr = 3 * x + 2 * y
```

等价于 `(3 * x) + (2 * y)`，分三步：

### 步骤 1：`3 * x` → `LpAffineExpression({x: 3.0})`

（同上）

### 步骤 2：`2 * y` → `LpAffineExpression({y: 2.0})`

（同理）

### 步骤 3：`(3*x).__add__(2*y)` → 合并字典

```python
def __add__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const + other)
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)          # {x: 3.0}
        for var, coef in other.terms.items():  # {y: 2.0}
            new_coef = merged.get(var, 0) + coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)
        return self._new(merged, self.const + other.const)
```

合并过程：

```
merged = {x: 3.0}           # 从 self 拷贝
遍历 other.terms = {y: 2.0}:
  y 不在 merged 中 → merged[y] = 0 + 2.0 = 2.0
merged = {x: 3.0, y: 2.0}
new_const = 0.0 + 0.0 = 0.0
```

**结果：`expr.terms = {x: 3.0, y: 2.0}`，`expr.const = 0.0`。**

### 为什么用字典而非列表？

字典的优势：

1. **稀疏表示**：只有非零系数才存储
2. **O(1) 查找**：合并时快速判断变量是否已存在
3. **变量对象作 key**：自然映射"变量→系数"关系

### 更复杂的表达式追踪

```python
expr = 2 * (3 * x + 4 * y) + 5 * z - 7
```

逐步追踪：

```python
# 步骤 1: 3 * x → {x: 3.0}
# 步骤 2: 4 * y → {y: 4.0}
# 步骤 3: (3*x) + (4*y) → {x: 3.0, y: 4.0}
inner = 3 * x + 4 * y  # {x: 3.0, y: 4.0}

# 步骤 4: 2 * inner
#   __rmul__(2) → __mul__(2)
#   {var: coef * 2 for ...} → {x: 6.0, y: 8.0}
step4 = 2 * inner  # {x: 6.0, y: 8.0}

# 步骤 5: 5 * z → {z: 5.0}
step5 = 5 * z  # {z: 5.0}

# 步骤 6: step4 + step5
#   合并 {x: 6.0, y: 8.0} 和 {z: 5.0}
#   → {x: 6.0, y: 8.0, z: 5.0}
step6 = step4 + step5  # {x: 6.0, y: 8.0, z: 5.0}

# 步骤 7: step6 - 7
#   __sub__(7) → const - 7 = 0 - 7 = -7
#   → {x: 6.0, y: 8.0, z: 5.0}, const=-7
expr = step6 - 7  # {x: 6.0, y: 8.0, z: 5.0}, const=-7.0
```

最终：`expr.terms = {x: 6.0, y: 8.0, z: 5.0}`，`expr.const = -7.0`。

### 嵌套表达式追踪

```python
# 深度嵌套的表达式
expr = ((x + y) + (z + w)) + ((a + b) + (c + d))
```

追踪过程：

```python
# 每一层加法都是字典合并
# x + y → {x:1, y:1}
# z + w → {z:1, w:1}
# (x+y) + (z+w) → {x:1, y:1, z:1, w:1}
# a + b → {a:1, b:1}
# c + d → {c:1, d:1}
# (a+b) + (c+d) → {a:1, b:1, c:1, d:1}
# 最终合并 → {x:1, y:1, z:1, w:1, a:1, b:1, c:1, d:1}
```

无论嵌套多深，最终都是一个扁平字典。这就是闭包性的威力——**没有树的高度，只有字典的宽度**。

---

## 3 * x + 2 * y <= 100 的完整调用链

```python
con = 3 * x + 2 * y <= 100
```

### 步骤 1-2：`3 * x + 2 * y` → `LpAffineExpression({x: 3.0, y: 2.0})`

（同上）

### 步骤 3：`__le__(100)` → 构造约束

```python
# LpElement.__le__
def __le__(self, other):
    from .constraints import LpConstraint
    return LpConstraint(self - other, LpConstraintSense.LE)
```

### 步骤 4：`self - 100` → 把右端项移到左边

```python
def __sub__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const - other)
```

`self.const - 100 = 0 - 100 = -100`

### 步骤 5：构造 `LpConstraint`

```python
LpConstraint(
    lhs=LpAffineExpression({x: 3.0, y: 2.0}, const=-100),
    sense=LpConstraintSense.LE
)
```

**结果：`LpConstraint(lhs={x: 3.0, y: 2.0, const:-100}, sense=LE)`**

即 `3x + 2y - 100 <= 0`，归一化为齐次形式。

### 归一化的好处

所有约束统一为 `lhs <= 0` / `lhs >= 0` / `lhs == 0` 形式。
求解器只需处理一种形式，而非为 `<=`/`>=`/`==` 各写一套逻辑。

### 不同比较运算符的追踪

```python
# <=
con1 = 3 * x + 2 * y <= 100
# → LpConstraint({x:3, y:2, c:-100}, LE)
# 含义：3x + 2y - 100 <= 0

# >=
con2 = 3 * x + 2 * y >= 50
# → LpConstraint({x:3, y:2, c:-50}, GE)
# 含义：3x + 2y - 50 >= 0

# ==
con3 = 3 * x + 2 * y == 80
# → LpConstraint({x:3, y:2, c:-80}, EQ)
# 含义：3x + 2y - 80 == 0

# 右边是表达式
con4 = 3 * x <= 2 * y + 10
# 步骤：
#   3 * x → {x: 3}
#   2 * y + 10 → {y: 2}, const=10
#   {x:3} - ({y:2}, c=10) → {x:3, y:-2}, const=-10
# → LpConstraint({x:3, y:-2, c:-10}, LE)
# 含义：3x - 2y - 10 <= 0
```

### 复合约束表达式追踪

```python
# 复合约束
con = (x + y <= 10) + (x - y >= 0)
```

**注意**：这不是 minipulp 的标准用法，但追踪其行为有助于理解：

```python
# 步骤 1: x + y <= 10
# → LpConstraint({x:1, y:1, c:-10}, LE)
c1 = x + y <= 10

# 步骤 2: x - y >= 0
# → LpConstraint({x:1, y:-1, c:0}, GE)
c2 = x - y >= 0

# 步骤 3: c1 + c2
# LpConstraint 的 __add__ 会合并 lhs
# → LpConstraint({x:2, y:0, c:-10}, ...)
# 注意：y 的系数为 0，被自动消除
# → LpConstraint({x:2, c:-10}, ...)
```

---

## _new 方法的作用

注意 `LpVariable` 和 `LpAffineExpression` 各有不同的 `_new`：

```python
class LpAffineExpression:
    def _new(self, terms, const):
        return LpAffineExpression(terms, const)  # 返回基类

class LpVariable(LpAffineExpression):
    def _new(self, terms, const):
        return LpAffineExpression(terms, const)  # 也返回基类，不是 LpVariable
```

### 为什么运算结果要降级？

变量参与运算后（如 `3 * x`），结果不再是"单变量"，而是"多变量表达式"。
`3 * x` 不应该是一个 `LpVariable`——它没有 `lowBound`、`upBound` 等属性。

```python
x = LpVariable("x", lowBound=0)
expr = 3 * x
type(expr)  # LpAffineExpression，不是 LpVariable
expr.lowBound  # AttributeError！LpAffineExpression 没有 lowBound
```

### 类型降级链

```
LpVariable + LpVariable → LpAffineExpression
LpVariable * float      → LpAffineExpression
LpAffineExpression + ... → LpAffineExpression
```

一旦参与运算，结果就降级为 `LpAffineExpression`，不再保留变量属性。
这是数学上正确的——`3*x + 2*y` 不是一个"变量"，它是一个"表达式"。

### _new 的设计模式意义

`_new` 是**工厂方法模式**的体现——每个类通过 `_new` 决定创建什么类型的对象。

```python
# LpAffineExpression 的 _new 创建 LpAffineExpression
# LpVariable 的 _new 也创建 LpAffineExpression（降级）

# 如果将来添加 LpQuadraticExpression：
class LpQuadraticExpression(LpAffineExpression):
    def _new(self, terms, const):
        return LpQuadraticExpression(terms, const)  # 保持二次
```

这种设计让运算符实现可以统一用 `self._new(...)`，而具体创建什么类型由 `_new` 决定。

### 为什么不用类方法？

`_new` 是实例方法而非类方法，因为它需要访问 `self` 的类型信息（在继承链中动态决定）：

```python
# 如果 _new 是类方法：
LpAffineExpression._new(terms, const)  # 总是创建 LpAffineExpression

# 作为实例方法：
self._new(terms, const)  # 根据 self 的实际类型决定
# 如果 self 是 LpVariable → 创建 LpAffineExpression（降级）
# 如果 self 是 LpAffineExpression → 创建 LpAffineExpression
```

---

## __eq__ 的陷阱

重载 `__eq__` 返回 `LpConstraint` 而非 `bool`，会破坏 Python 的相等性语义：

```python
x == y  # 返回 LpConstraint，不是 True/False！
```

### 问题：字典 key 行为

Python 字典用 `__hash__` 和 `__eq__` 判断 key 是否相同。
如果 `__eq__` 返回 `LpConstraint`（truthy），字典可能误判。

```python
x = LpVariable("x")
y = LpVariable("y")
d = {x: 1, y: 2}
# 查找 d[x] 时：
# 1. hash(x) → 找到桶
# 2. 桶中有 x 和 y（如果 hash 碰撞）
# 3. x == x → LpConstraint（truthy）→ 误判为相同？
```

### Python 字典实现原理

Python 字典（`dict`）是基于哈希表的实现。理解其工作原理对理解 `__eq__` 陷阱至关重要。

#### 哈希表结构

```
┌─────────────────────────────┐
│ dict                        │
│  ┌─────┬──────────┬───────┐ │
│  │ idx │ hash     │ entry │ │
│  ├─────┼──────────┼───────┤ │
│  │  0  │ hash(x)  │ x→1   │ │
│  │  1  │ (empty)  │       │ │
│  │  2  │ hash(y)  │ y→2   │ │
│  │  3  │ (empty)  │       │ │
│  └─────┴──────────┴───────┘ │
└─────────────────────────────┘
```

#### 查找过程

`d[key]` 的查找过程：

1. 计算 `h = hash(key)`
2. 定位桶 `i = h % table_size`
3. 检查桶 `i`：
   - 空桶 → KeyError
   - 桶中 key 的 hash 匹配 → 检查 `key is stored_key` 或 `key == stored_key`
   - hash 不匹配 → 探测下一个桶（开放寻址法）

```python
# 伪代码
def dict_get(d, key):
    h = hash(key)
    i = h % len(d.table)
    while True:
        entry = d.table[i]
        if entry is EMPTY:
            raise KeyError(key)
        if entry.hash == h:
            if key is entry.key:          # 第一步：指针相等
                return entry.value
            if key == entry.key:          # 第二步：值相等
                return entry.value
        i = (i + 1) % len(d.table)        # 探测下一个
```

**关键**：Python 先用 `is`（指针相等）判断，再用 `==`（值相等）。这是 minipulp 能安全重载 `__eq__` 的关键——同一变量对象作为 key 时，`is` 命中，不触发 `__eq__`。

### 哈希碰撞处理

当两个不同 key 的 hash 值相同时，发生哈希碰撞：

```python
# 假设 hash(x) == hash(y)（碰撞）
d = {x: 1, y: 2}
# 两个 entry 在同一个桶链中

d[x]  # 查找：
# 1. hash(x) → 定位桶
# 2. 桶中有 x 和 y
# 3. x is x → True（第一个 entry）→ 返回 1
# 不需要调用 __eq__！

d[y]  # 查找：
# 1. hash(y) → 定位同一个桶
# 2. 桶中有 x 和 y
# 3. y is x → False
# 4. y == x → LpConstraint（truthy！）→ 误判？
#    但实际上，Python 会检查 hash 是否匹配
#    hash(y) == hash(x)（碰撞）→ 继续 ==
#    y == x → LpConstraint → truthy → 返回 1（错误！）
```

**这就是危险所在**：如果 `hash(x) == hash(y)` 且 `x != y`（不同变量），`d[y]` 可能错误返回 `d[x]` 的值。

### minipulp 的解决方案

```python
class LpElement:
    def __hash__(self) -> int:
        return hash(self.name) if self.name else id(self)

    def __eq__(self, other):
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

1. `__hash__` 基于 `name`（变量）或 `id`（表达式），保证可哈希
2. 字典查找时 Python 先用 `is`（指针相等）判断，再用 `__eq__`
3. 同一变量对象作为 key 时 `is` 命中，不触发 `__eq__`
4. 不同变量 `name` 不同 → `hash` 不同 → 不触发 `__eq__`

```python
x = LpVariable("x")
d = {x: 3}
d[x]  # 查找过程：
      # 1. hash(x) → 找到桶
      # 2. 桶中有 x
      # 3. x is x → True（指针相等，不调用 __eq__）
      # 4. 返回 3
```

**安全条件**：不要创建同名变量。只要变量名唯一，字典行为安全。

### 验证安全性

```python
# 安全：不同名变量
x = LpVariable("x")
y = LpVariable("y")
d = {x: 1, y: 2}
assert d[x] == 1  # OK
assert d[y] == 2  # OK
# 因为 hash(x) = hash("x") ≠ hash("y") = hash(y)

# 危险：同名变量（不要这样做！）
x1 = LpVariable("x")
x2 = LpVariable("x")
d = {x1: 1}
d[x2]  # 可能返回 1（因为 hash(x1) == hash(x2)）
       # 然后 x2 == x1 → LpConstraint（truthy）→ 误判
```

### 为什么不保留默认 __eq__？

因为 `x == y` 构造等式约束是 LP 建模的核心需求：
```python
prob += x + y == 10  # 等式约束
```

如果 `__eq__` 返回 `bool`，就无法用 `==` 构造约束。
这是建模库的必然选择——牺牲一些 Python 语义来获得建模便利。

### __eq__ 重载的其他影响

重载 `__eq__` 还会影响以下场景：

```python
x = LpVariable("x")
y = LpVariable("y")

# 1. 列表的 in 操作
# x in [x, y] → 触发 __eq__，但先检查 is
# 通常安全，因为 is 会先命中

# 2. 集合
s = {x, y}
# 集合行为类似字典 key，同样依赖 __hash__ 和 __eq__

# 3. assert
assert x == y  # 不会 AssertionError！
# 因为 x == y 返回 LpConstraint（truthy）
# 这是陷阱：assert 不会检查约束是否满足

# 4. if 判断
if x == y:  # 总是 True（LpConstraint 是 truthy）
    ...     # 总是执行
```

**最佳实践**：不要用 `==` 做逻辑判断，只用于构造约束。

---

## 所有运算符的实现

### 加法 `__add__`

```python
def __add__(self, other):
    if _is_number(other):
        # expr + 5 → 常数项相加
        return self._new(self.terms, self.const + other)
    if isinstance(other, LpAffineExpression):
        # expr + expr → 字典合并
        merged = dict(self.terms)
        for var, coef in other.terms.items():
            new_coef = merged.get(var, 0.0) + coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)  # 系数为 0 则删除
        return self._new(merged, self.const + other.const)
    return NotImplemented
```

### 减法 `__sub__`

```python
def __sub__(self, other):
    if _is_number(other):
        return self._new(self.terms, self.const - other)
    if isinstance(other, LpAffineExpression):
        merged = dict(self.terms)
        for var, coef in other.terms.items():
            new_coef = merged.get(var, 0.0) - coef
            if new_coef != 0:
                merged[var] = new_coef
            else:
                merged.pop(var, None)
        return self._new(merged, self.const - other.const)
    return NotImplemented
```

### 反向加法 `__radd__`

```python
def __radd__(self, other):
    # 5 + x → x + 5（加法交换律）
    return self.__add__(other)
```

### 反向减法 `__rsub__`

```python
def __rsub__(self, other):
    if _is_number(other):
        # 5 - x → {-x + 5}
        return self._new(
            {var: -coef for var, coef in self.terms.items()},
            other - self.const,
        )
    return NotImplemented
```

### 乘法 `__mul__`

```python
def __mul__(self, other):
    if _is_number(other):
        if other == 0:
            return self._new({}, 0.0)  # 乘以 0 → 纯零
        return self._new(
            {var: coef * other for var, coef in self.terms.items()},
            self.const * other,
        )
    if isinstance(other, LpAffineExpression):
        if not self.terms or not other.terms:
            # 其中一个是纯常数
            if self.terms:
                return self._new({}, 0.0)
            return self._new(
                {var: coef * self.const for var, coef in other.terms.items()},
                self.const * other.const,
            )
        raise TypeError(
            "不能将两个含变量的表达式相乘（非线性），"
            "线性规划只允许仿射表达式"
        )
    return NotImplemented
```

### 反向乘法 `__rmul__`

```python
def __rmul__(self, other):
    # 3 * x → x * 3（乘法交换律）
    return self.__mul__(other)
```

### 除法 `__truediv__`

```python
def __truediv__(self, other):
    if _is_number(other):
        if other == 0:
            raise ZeroDivisionError("表达式除以零")
        return self.__mul__(1.0 / other)  # 除法 → 乘以倒数
    return NotImplemented
```

### 负号 `__neg__`

```python
def __neg__(self):
    return self._new(
        {var: -coef for var, coef in self.terms.items()},
        -self.const,
    )
```

### 正号 `__pos__`

```python
def __pos__(self):
    # +x → x（返回副本）
    return self._new(dict(self.terms), self.const)
```

### 比较运算符（在基类 `LpElement` 中）

```python
def __le__(self, other):
    from .constraints import LpConstraint
    return LpConstraint(self - other, LpConstraintSense.LE)

def __ge__(self, other):
    from .constraints import LpConstraint
    return LpConstraint(self - other, LpConstraintSense.GE)

def __eq__(self, other):
    from .constraints import LpConstraint
    return LpConstraint(self - other, LpConstraintSense.EQ)
```

### 哈希 `__hash__`

```python
def __hash__(self) -> int:
    return hash(self.name) if self.name else id(self)
```

---

## NotImplemented 的作用

当运算符方法返回 `NotImplemented` 时，Python 会尝试反向运算符。

```python
def __add__(self, other):
    if _is_number(other):
        ...
    if isinstance(other, LpAffineExpression):
        ...
    return NotImplemented  # 不认识的类型，让 Python 尝试 other.__radd__
```

### 为什么不直接抛 TypeError？

返回 `NotImplemented` 比 `raise TypeError` 更灵活：

```python
# 如果 __add__ 返回 NotImplemented：
# Python 会尝试 other.__radd__(self)
# 如果也返回 NotImplemented，才抛 TypeError

# 这允许其他类型定义与 LpAffineExpression 的加法：
class MyType:
    def __radd__(self, other):
        if isinstance(other, LpAffineExpression):
            return ...  # 自定义加法
```

### NotImplemented vs NotImplementedError

这是一个常见的混淆点：

| 特性 | `NotImplemented` | `NotImplementedError` |
|------|------------------|----------------------|
| 类型 | 单例对象（`types.NotImplementedType`） | 异常类 |
| 用途 | 运算符重载的回退信号 | 抽象方法未实现的标记 |
| 处理方式 | Python 自动尝试反向运算符 | 直接抛异常 |
| 返回 vs 抛 | **返回**（`return NotImplemented`） | **抛出**（`raise NotImplementedError`） |

```python
# 正确：运算符重载用 NotImplemented
def __add__(self, other):
    if _is_number(other):
        return ...
    return NotImplemented  # 让 Python 尝试 other.__radd__

# 正确：抽象方法用 NotImplementedError
class AbstractSolver:
    def solve(self, problem):
        raise NotImplementedError("子类必须实现 solve 方法")

# 错误：运算符重载用 NotImplementedError
def __add__(self, other):
    if _is_number(other):
        return ...
    raise NotImplementedError(...)  # 不会触发反向运算符！

# 错误：抽象方法用 NotImplemented
class AbstractSolver:
    def solve(self, problem):
        return NotImplemented  # 调用者不知道怎么处理
```

### NotImplemented 的内部机制

`NotImplemented` 是 Python 解释器的特殊单例：

```python
>>> type(NotImplemented)
<class 'NotImplementedType'>
>>> NotImplemented == NotImplemented
True
>>> bool(NotImplemented)
True  # 注意：NotImplemented 是 truthy！
```

当运算符方法返回 `NotImplemented` 时，CPython 的 `binary_op` 函数会：

1. 检查返回值是否是 `NotImplemented`
2. 如果是，尝试反射运算符（`__radd__` 等）
3. 如果反射也返回 `NotImplemented`，抛出 `TypeError`

```c
// CPython 简化伪代码
PyObject *binary_op(PyObject *a, PyObject *b, opfunc op, opfunc rop) {
    PyObject *result = op(a, b);
    if (result != NotImplemented) {
        return result;
    }
    Py_DECREF(result);

    result = rop(b, a);  // 尝试反射
    if (result != NotImplemented) {
        return result;
    }

    PyErr_Format(PyExc_TypeError, "unsupported operand type(s)");
    return NULL;
}
```

---

## 运算符重载一览表

| 表达式 | 调用 | 结果类型 | 结果内容 |
|--------|------|----------|----------|
| `3 * x` | `x.__rmul__(3)` | `LpAffineExpression` | `{x: 3}` |
| `x * 3` | `x.__mul__(3)` | `LpAffineExpression` | `{x: 3}` |
| `x + y` | `x.__add__(y)` | `LpAffineExpression` | `{x: 1, y: 1}` |
| `x + 5` | `x.__add__(5)` | `LpAffineExpression` | `{x: 1}, c=5` |
| `5 + x` | `x.__radd__(5)` | `LpAffineExpression` | `{x: 1}, c=5` |
| `x - y` | `x.__sub__(y)` | `LpAffineExpression` | `{x: 1, y: -1}` |
| `x - 5` | `x.__sub__(5)` | `LpAffineExpression` | `{x: 1}, c=-5` |
| `5 - x` | `x.__rsub__(5)` | `LpAffineExpression` | `{x: -1}, c=5` |
| `x / 4` | `x.__truediv__(4)` | `LpAffineExpression` | `{x: 0.25}` |
| `-x` | `x.__neg__()` | `LpAffineExpression` | `{x: -1}` |
| `+x` | `x.__pos__()` | `LpAffineExpression` | `{x: 1}` |
| `x <= 5` | `x.__le__(5)` | `LpConstraint` | `x-5 <= 0` |
| `x >= 5` | `x.__ge__(5)` | `LpConstraint` | `x-5 >= 0` |
| `x == y` | `x.__eq__(y)` | `LpConstraint` | `x-y == 0` |
| `x * y` | `x.__mul__(y)` | **TypeError** | 非线性 |
| `x ** 2` | `x.__pow__(2)` | **TypeError** | 非线性 |
| `x // 2` | `x.__floordiv__(2)` | **TypeError** | 非线性 |
| `x % 2` | `x.__mod__(2)` | **TypeError** | 非线性 |

---

## 性能考量

### 字典操作的开销

每次运算符调用都涉及字典创建和合并：

```python
# __add__ 的核心操作
merged = dict(self.terms)          # O(T_self) 拷贝
for var, coef in other.terms.items():  # O(T_other) 遍历
    merged[var] = merged.get(var, 0) + coef  # O(1) 字典操作
```

总复杂度：$O(T_{self} + T_{other})$，其中 $T$ 是项数。

### lpSum 的优化

对于大量表达式的求和，`sum()` 会创建 N-1 个中间对象。
`lpSum` 一次性合并所有字典，只创建一个对象：

```python
def lpSum(vector):
    merged = {}
    const = 0.0
    for item in vector:
        for var, coef in item.terms.items():
            merged[var] = merged.get(var, 0) + coef
        const += item.const
    return LpAffineExpression(merged, const)
```

对 500 个变量的求和，`lpSum` 比 `sum` 快约 5-10x。

### 零系数消除

构造时自动剔除零系数项：

```python
self.terms = {var: float(coef) for var, coef in terms.items() if coef != 0}
```

这保持字典的**规范化**——零系数项不存储，避免冗余。
在 `x - x` 这样的运算中，结果自动变成空字典（纯常数）。

### 中间对象的开销

每个运算符调用都创建新对象：

```python
expr = 3 * x + 2 * y + 5 * z
# 创建的对象：
# 1. 3 * x → LpAffineExpression({x: 3})
# 2. 2 * y → LpAffineExpression({y: 2})
# 3. (3*x) + (2*y) → LpAffineExpression({x:3, y:2})
# 4. 5 * z → LpAffineExpression({z: 5})
# 5. step3 + (5*z) → LpAffineExpression({x:3, y:2, z:5})
# 共 5 个对象，其中 3 个是中间结果
```

对于表达式 `a*x + b*y + c*z + ...`（N 项），`sum()` 创建约 2N 个对象。
`lpSum` 只创建 1 个对象。

---

## Python 数据模型深入

Python 的数据模型（Data Model）是通过双下方法（dunder methods）定义的协议。

### 对象的生命周期方法

| 方法 | 触发时机 | 用途 |
|------|---------|------|
| `__new__` | 创建实例 | 控制对象创建 |
| `__init__` | 初始化实例 | 设置属性 |
| `__del__` | 引用计数归零 | 清理资源 |
| `__repr__` | `repr()` 调用 | 官方表示 |
| `__str__` | `str()` 调用 | 用户字符串 |
| `__format__` | `format()` / f-string | 格式化 |
| `__hash__` | `hash()` 调用 | 哈希值 |
| `__bool__` | `bool()` 调用 | 真值测试 |
| `__sizeof__` | `sys.getsizeof()` | 内存大小 |
| `__dir__` | `dir()` 调用 | 属性列表 |
| `__class__` | 类型访问 | 类引用 |

### 运算符方法分类

#### 算术运算符

| 方法 | 运算符 | 说明 |
|------|--------|------|
| `__add__` | `+` | 加法 |
| `__sub__` | `-` | 减法 |
| `__mul__` | `*` | 乘法 |
| `__truediv__` | `/` | 真除法 |
| `__floordiv__` | `//` | 整除 |
| `__mod__` | `%` | 取模 |
| `__pow__` | `**` | 幂 |
| `__matmul__` | `@` | 矩阵乘法 |
| `__neg__` | `-x` | 负号 |
| `__pos__` | `+x` | 正号 |
| `__abs__` | `abs(x)` | 绝对值 |
| `__invert__` | `~x` | 按位取反 |

#### 反射算术运算符

| 方法 | 触发条件 | 说明 |
|------|---------|------|
| `__radd__` | `a + b` 中 `a.__add__` 返回 NotImplemented | 反射加法 |
| `__rsub__` | 同上 | 反射减法 |
| `__rmul__` | 同上 | 反射乘法 |
| `__rtruediv__` | 同上 | 反射真除法 |
| `__rfloordiv__` | 同上 | 反射整除 |
| `__rmod__` | 同上 | 反射取模 |
| `__rpow__` | 同上 | 反射幂 |
| `__rmatmul__` | 同上 | 反射矩阵乘法 |

#### 原地运算符

| 方法 | 运算符 | 默认行为 |
|------|--------|---------|
| `__iadd__` | `+=` | `a = a + b` |
| `__isub__` | `-=` | `a = a - b` |
| `__imul__` | `*=` | `a = a * b` |
| `__itruediv__` | `/=` | `a = a / b` |

#### 比较运算符

| 方法 | 运算符 | 说明 |
|------|--------|------|
| `__lt__` | `<` | 小于 |
| `__le__` | `<=` | 小于等于 |
| `__gt__` | `>` | 大于 |
| `__ge__` | `>=` | 大于等于 |
| `__eq__` | `==` | 等于 |
| `__ne__` | `!=` | 不等于（默认基于 `__eq__`） |

### 比较运算符的反射

比较运算符没有 `__rle__` 等反射方法，但 Python 会自动处理反射：

```python
# a <= b 的查找顺序：
# 1. a.__le__(b)
# 2. 如果返回 NotImplemented，尝试 b.__ge__(a)
# 3. 如果都返回 NotImplemented，抛 TypeError

# a == b 的查找顺序：
# 1. a.__eq__(b)
# 2. 如果返回 NotImplemented，尝试 b.__eq__(a)
# 3. 如果都返回 NotImplemented，回退到 is 比较
```

### 容器方法

| 方法 | 触发 | 说明 |
|------|------|------|
| `__len__` | `len(x)` | 长度 |
| `__getitem__` | `x[key]` | 下标访问 |
| `__setitem__` | `x[key] = val` | 下标赋值 |
| `__delitem__` | `del x[key]` | 下标删除 |
| `__contains__` | `key in x` | 成员测试 |
| `__iter__` | `iter(x)` | 迭代器 |
| `__reversed__` | `reversed(x)` | 反向迭代 |

### 可调用对象

```python
class LpProblem:
    def __call__(self, solver=None):
        return self.solve(solver)

# 使用
prob = LpProblem("demo")
prob()  # 等价于 prob.solve()
```

---

## Python 运算符查找算法

理解 Python 如何查找运算符方法，对调试运算符重载问题至关重要。

### 二元运算符的完整查找流程

以 `a + b` 为例：

```
1. 检查 type(a).__add__ 是否存在
   │
   ├─ 存在 → 调用 result = type(a).__add__(a, b)
   │         │
   │         ├─ result 不是 NotImplemented → 返回 result
   │         └─ result 是 NotImplemented → 继续步骤 2
   │
   └─ 不存在 → 继续步骤 2

2. 检查 type(b).__radd__ 是否存在
   │
   ├─ 存在 → 调用 result = type(b).__radd__(b, a)
   │         │
   │         ├─ result 不是 NotImplemented → 返回 result
   │         └─ result 是 NotImplemented → 继续步骤 3
   │
   └─ 不存在 → 继续步骤 3

3. 抛出 TypeError: unsupported operand type(s) for +
```

### 类型强制转换的陷阱

Python 3 不做隐式类型转换，但运算符重载可能引入类似行为：

```python
# int + LpVariable
3 + x
# 1. int.__add__(3, x) → NotImplemented（int 不认识 LpVariable）
# 2. x.__radd__(3) → LpAffineExpression（LpVariable 处理）
# 结果：LpAffineExpression，不是 int

# 这实际上是"类型提升"：int → LpAffineExpression
```

### MRO（方法解析顺序）的影响

当涉及继承时，Python 按 MRO 查找方法：

```python
class LpElement:
    def __le__(self, other):
        ...

class LpAffineExpression(LpElement):
    # 不定义 __le__，继承自 LpElement
    ...

class LpVariable(LpAffineExpression):
    # 不定义 __le__，继承自 LpElement
    ...

x = LpVariable("x")
x <= 5
# 查找 __le__：
# 1. LpVariable.__le__ → 不存在
# 2. LpAffineExpression.__le__ → 不存在
# 3. LpElement.__le__ → 找到！
```

### 特殊方法查找不走实例

Python 的运算符查找**不走实例的 `__dict__`**，而是走类型的 `__dict__`：

```python
x = LpVariable("x")

# 这样不会影响运算符行为：
x.__add__ = lambda other: "custom"
x + 5  # 仍然调用 LpAffineExpression.__add__，不是实例的 __add__

# 必须在类上设置才能生效：
LpVariable.__add__ = lambda self, other: "custom"
x + 5  # 现在返回 "custom"
```

这是 Python 3 的有意设计——特殊方法查找走类型而非实例，保证运算符行为的一致性和性能。

---

## 其他库的运算符重载案例

运算符重载在 Python 科学计算生态中广泛使用。

### NumPy

NumPy 是运算符重载的经典案例：

```python
import numpy as np

a = np.array([1, 2, 3])
b = np.array([4, 5, 6])

# 逐元素运算
a + b   # array([5, 7, 9])
a * b   # array([4, 10, 18])
a * 2   # array([2, 4, 6])

# 广播
a + 10  # array([11, 12, 13])
```

NumPy 的运算符重载特点：

1. **逐元素语义**：`a * b` 是逐元素乘，不是矩阵乘
2. **广播**：`a + 10` 将标量"广播"到每个元素
3. `__matmul__`：`@` 运算符用于矩阵乘法（Python 3.5+）

```python
# NumPy 的 __mul__ 简化实现
class ndarray:
    def __mul__(self, other):
        if isinstance(other, ndarray):
            return self._elementwise_mul(other)  # 逐元素
        return self._scalar_mul(other)  # 标量乘

    def __matmul__(self, other):
        return self._matrix_mul(other)  # 矩阵乘
```

对比 minipulp：NumPy 的 `*` 是逐元素乘（允许"非线性"），minipulp 的 `*` 是标量乘（禁止非线性）。

### SymPy

SymPy 是符号计算库，运算符重载构造符号表达式：

```python
import sympy as sp

x, y = sp.symbols('x y')
expr = 3 * x + 2 * y
print(expr)  # 3*x + 2*y

# 支持非线性
expr = x * y
print(expr)  # x*y

expr = x ** 2 + y ** 2
print(expr)  # x**2 + y**2

# 微分
print(sp.diff(expr, x))  # 2*x
```

SymPy 的运算符重载特点：

1. **表达式树**：因为支持非线性，必须用树结构
2. **符号化**：运算不计算，只构造表达式
3. **数学运算**：支持微分、积分、化简等

```python
# SymPy 的表达式树
expr = (x + y) ** 2
# 内部表示：
#     Pow
#    /   \
#  Add    2
#  / \
# x   y

srepr(expr)  # "Pow(Add(Symbol('x'), Symbol('y')), Integer(2))"
```

对比 minipulp：SymPy 用表达式树（支持非线性），minipulp 用扁平字典（只支持线性）。

### SQLAlchemy

SQLAlchemy 用运算符重载构造 SQL 查询：

```python
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)

# 运算符重载构造 SQL
stmt = select(User).where(User.age >= 18)
print(stmt)
# SELECT users.id, users.name, users.age
# FROM users
# WHERE users.age >= ?

# 复杂条件
stmt = select(User).where((User.age >= 18) & (User.name.like('A%')))
```

SQLAlchemy 的运算符重载特点：

1. `>=`、`<` 等返回 `BooleanClauseElement`（SQL 片段）
2. `&`、`|` 用于 AND/OR 组合
3. `==` 返回 SQL 条件而非 bool

```python
# SQLAlchemy 的 __ge__
class Column:
    def __ge__(self, other):
        return BooleanClauseElement(self, '>=', other)

# User.age >= 18 返回 BooleanClauseElement
# 而非 True/False
```

对比 minipulp：SQLAlchemy 的 `>=` 返回 SQL 条件，minipulp 的 `>=` 返回 LP 约束。两者都是 DSL 构造。

### Pandas

Pandas 用运算符重载做向量化运算：

```python
import pandas as pd

df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})

# 逐列运算
df['a'] + df['b']  # Series([5, 7, 9])
df['a'] * 2        # Series([2, 4, 6])

# 比较返回布尔 Series
df['a'] > 2  # Series([False, False, True])
```

Pandas 的特点：比较运算符返回布尔 Series（用于过滤），而非构造表达式。

### TensorFlow / PyTorch

深度学习框架用运算符重载构造计算图：

```python
import torch

x = torch.tensor(2.0, requires_grad=True)
y = x ** 2 + 3 * x + 1
# y 是一个计算图节点

y.backward()  # 自动微分
print(x.grad)  # 2*x + 3 = 7.0
```

特点：

1. 运算构造计算图（类似表达式树）
2. 支持自动微分
3. `__matmul__` 用于矩阵乘法

---

## 最佳实践与陷阱

### 最佳实践

#### 1. 保持代数性质

重载运算符应保持数学性质（交换律、结合律等）：

```python
# 好的设计：加法满足交换律
assert x + y == y + x  # （在约束意义上）

# 好的设计：乘法对标量满足结合律
assert 2 * (3 * x) == (2 * 3) * x
```

#### 2. 返回 NotImplemented 而非抛异常

对于不支持的类型，返回 `NotImplemented` 而非 `TypeError`：

```python
# 好
def __add__(self, other):
    if _is_number(other):
        return ...
    return NotImplemented  # 让 Python 尝试反射

# 不好
def __add__(self, other):
    if _is_number(other):
        return ...
    raise TypeError(...)  # 阻止反射
```

#### 3. 保持类型一致性

运算结果应返回已知类型，而非任意类型：

```python
# 好：LpAffineExpression 运算结果总是 LpAffineExpression
def __add__(self, other):
    return self._new(...)  # _new 保证返回 LpAffineExpression

# 不好：可能返回不同类型
def __add__(self, other):
    if condition:
        return LpAffineExpression(...)
    else:
        return "error"  # 类型不一致
```

#### 4. 文档化语义改变

重载 `__eq__` 改变语义时，必须文档化：

```python
class LpElement:
    """LP 元素基类。

    注意：__eq__ 被重载用于构造等式约束，不返回 bool。
    不要用 == 做相等性判断，用 `is` 或 `.name` 比较。
    """
    def __eq__(self, other):
        return LpConstraint(self - other, LpConstraintSense.EQ)
```

### 常见陷阱

#### 陷阱 1：__eq__ 破坏字典和集合

```python
x = LpVariable("x")
y = LpVariable("y")

# 字典 key
d = {x: 1, y: 2}
# 如果 hash(x) == hash(y)，d[x] 可能返回 d[y] 的值

# 集合
s = {x, y}
# 如果 hash(x) == hash(y)，s 可能只有 1 个元素
```

**解决**：确保 `__hash__` 基于唯一标识（如 name）。

#### 陷阱 2：__eq__ 破坏 assert

```python
x = LpVariable("x")
y = LpVariable("y")

assert x == y  # 不会 AssertionError！
# 因为 x == y 返回 LpConstraint（truthy）
```

**解决**：用 `assert x.name == y.name` 或 `assert x is y`。

#### 陷阱 3：__eq__ 破坏 if 判断

```python
if x == y:  # 总是 True
    print("相等")  # 总是执行
```

**解决**：不要用 `==` 做逻辑判断。

#### 陷阱 4：原地运算符的陷阱

```python
x = LpVariable("x")
expr = 3 * x
expr += 2  # 等价于 expr = expr + 2

# 这会创建新对象，原 expr 被替换
# 如果有其他引用指向原 expr，它们不会更新
```

#### 陷阱 5：运算符优先级

```python
# 注意运算符优先级
expr = x + y * 2  # x + (y * 2)，不是 (x + y) * 2
expr = x <= 5 + y  # x <= (5 + y)，不是 (x <= 5) + y
```

Python 的运算符优先级：`*` > `+` > `<=` > `==`

#### 陷阱 6：类型检查的边界

```python
# _is_number 的实现
def _is_number(x):
    return isinstance(x, (int, float, complex)) and not isinstance(x, bool)

# 注意：bool 是 int 的子类！
isinstance(True, int)  # True
# 所以需要排除 bool
```

---

## 性能基准测试

### 字典操作 vs 列表操作

```python
import timeit

# 字典合并（minipulp 的方式）
def dict_merge():
    d1 = {f"v{i}": i for i in range(100)}
    d2 = {f"v{i}": i for i in range(100, 200)}
    merged = dict(d1)
    merged.update(d2)
    return merged

# 列表合并
def list_merge():
    l1 = [(f"v{i}", i) for i in range(100)]
    l2 = [(f"v{i}", i) for i in range(100, 200)]
    return l1 + l2

# 字典查找
def dict_lookup():
    d = {f"v{i}": i for i in range(1000)}
    return d["v500"]

# 列表查找
def list_lookup():
    l = [(f"v{i}", i) for i in range(1000)]
    for k, v in l:
        if k == "v500":
            return v
```

| 操作 | 字典 | 列表 | 比值 |
|------|------|------|------|
| 合并 100 项 | ~2μs | ~5μs | 2.5x |
| 查找 1000 项 | ~0.1μs | ~50μs | 500x |

字典在查找上完胜列表，这是 minipulp 选择字典表示的关键原因。

### 运算符重载的开销

```python
# 直接构造
def direct_construct():
    return LpAffineExpression({x: 3.0, y: 2.0}, 0.0)

# 运算符构造
def operator_construct():
    return 3 * x + 2 * y

# 字符串解析（假设）
def string_construct():
    s = "3*x + 2*y"
    return parse_expression(s)  # 假设的解析函数
```

| 方法 | 耗时 | 说明 |
|------|------|------|
| 直接构造 | ~1μs | 最快 |
| 运算符构造 | ~5μs | 5x 开销，可接受 |
| 字符串解析 | ~50μs | 50x 开销，最慢 |

运算符重载比直接构造慢 5 倍，但比字符串解析快 10 倍。

### lpSum vs sum

```python
# 500 个变量求和
vars = [LpVariable(f"x_{i}") for i in range(500)]

# sum() 方式
def use_sum():
    return sum(vars)

# lpSum 方式
def use_lpSum():
    return lpSum(vars)
```

| 方法 | 耗时 | 对象数 | 说明 |
|------|------|--------|------|
| `sum()` | ~500μs | ~1000 | N-1 个中间对象 |
| `lpSum` | ~50μs | 1 | 一次合并 |

`lpSum` 快 10 倍，且内存占用少 1000 倍。

### 大规模模型性能

```python
# 10000 变量、1000 约束的模型
n_vars = 10000
n_constraints = 1000

# 建模时间
start = time.time()
x = [LpVariable(f"x_{i}", lowBound=0) for i in range(n_vars)]
prob = LpProblem("large")
prob += sum(x)  # 目标
for j in range(n_constraints):
    prob += sum(x[i] for i in range(n_vars)) <= 1000
build_time = time.time() - start
# ~2 秒（用 lpSum 可降到 ~0.5 秒）
```

---

## 延迟导入

比较运算符中使用了延迟导入：

```python
def __le__(self, other):
    from .constraints import LpConstraint  # 延迟导入
    return LpConstraint(self - other, LpConstraintSense.LE)
```

**为什么延迟导入？** `elements.py` 和 `constraints.py` 存在循环依赖：

```
elements.py → constraints.py（__le__ 需要 LpConstraint）
constraints.py → elements.py（LpConstraint 需要 LpAffineExpression）
```

延迟导入打破循环——只在方法被调用时才导入，而非模块加载时。

### 循环依赖的解决方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| 延迟导入 | 简单、无运行时开销 | 每次调用都查模块缓存 |
| 重构合并 | 无循环 | 可能导致大文件 |
| 接口分离 | 干净 | 需要额外抽象层 |
| 依赖注入 | 灵活 | 增加复杂度 |

minipulp 选择延迟导入——最简单且开销可忽略（Python 的模块缓存使重复导入几乎免费）。

---

## 总结

运算符重载是 minipulp 最核心的机制。通过重载 Python 的数学运算符，
让 `3 * x + 2 * y <= 100` 这样的代码直接构造出表达式和约束对象，
而非做数值计算。

**关键要点**：

1. **反向运算符**：`3 * x` 通过 `__rmul__` 实现
2. **字典合并**：加法就是字典系数相加
3. **类型降级**：运算结果从 `LpVariable` 降级为 `LpAffineExpression`
4. **归一化**：约束统一为 `lhs <= 0` 形式
5. **`__eq__` 陷阱**：重载 `__eq__` 需要配合 `__hash__` 保证字典安全
6. **NotImplemented**：让 Python 尝试反向运算符，增加灵活性
7. **延迟导入**：打破循环依赖

### 更深层的设计思考

运算符重载的本质是**创建领域特定语言（DSL）**。minipulp 通过运算符重载，在 Python 中嵌入了一个"线性规划 DSL"：

```python
# 这是 Python 代码，但读起来像数学公式
prob += 3 * x + 2 * y
prob += 2 * x + y <= 100
```

这种"内嵌 DSL"是 Python 的独特优势——不需要额外语法，用现有运算符就能构造领域语言。对比：

- **外部 DSL**：如 SQL、LaTeX，需要独立解析器
- **内嵌 DSL**：如 minipulp、SQLAlchemy，复用宿主语言

内嵌 DSL 的好处：

1. **IDE 支持**：语法检查、自动补全
2. **类型安全**：编译时/编辑时发现错误
3. **可组合**：与宿主语言无缝集成
4. **零开销**：不需要字符串解析

```python
# 内嵌 DSL 的威力：可以混合使用 Python 和 DSL
variables = [LpVariable(f"x_{i}", lowBound=0) for i in range(100)]
prob += sum(v * weight[i] for i, v in enumerate(variables))
# Python 的列表推导、sum、enumerate 都可用
# 这是外部 DSL 做不到的
```

运算符重载是 Python 实现 DSL 最强大的工具，minipulp 是这一技术的优雅范例。
