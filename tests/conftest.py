"""pytest 共享夹具。

测试目录镜像 src/minipulp 结构（见 tests/solvers/、tests/core/）。
"""
import pytest


@pytest.fixture
def make_variable():
    """工厂夹具：构造命名变量。"""
    from minipulp import LpVariable
    counter = [0]

    def _factory(name=None, **kwargs):
        if name is None:
            counter[0] += 1
            name = f"x{counter[0]}"
        return LpVariable(name, **kwargs)

    return _factory