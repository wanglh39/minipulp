"""编译 C++ 单纯形法核心为 Python 扩展模块。

用 CMake + pybind11 编译，教学透明——学生能看到完整构建流程。

编译产物：
    _native.pyd (Windows) / _native.so (Linux/macOS)

用法：
    uv run python src/minipulp/core/build.py
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sysconfig
from pathlib import Path

import pybind11


def get_ext_suffix() -> str:
    return sysconfig.get_config_var("EXT_SUFFIX") or (
        ".pyd" if platform.system() == "Windows" else ".so"
    )


def build() -> Path:
    here = Path(__file__).parent
    src = here / "simplex_core.cpp"
    if not src.exists():
        raise FileNotFoundError(f"C++ source not found: {src}")

    ext_suffix = get_ext_suffix()
    output = here / f"_native{ext_suffix}"

    build_dir = here / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    cmake_dir = pybind11.get_cmake_dir()

    configure_cmd = [
        "cmake",
        "-S", str(here),
        "-B", str(build_dir),
        f"-Dpybind11_DIR={cmake_dir}",
        "-G", "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles",
    ]

    print("CMake configure:")
    print("  " + " ".join(configure_cmd))
    print()

    result = subprocess.run(configure_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise RuntimeError(f"CMake configure failed (exit {result.returncode})")

    build_cmd = ["cmake", "--build", str(build_dir), "--config", "Release"]

    print("CMake build:")
    print("  " + " ".join(build_cmd))
    print()

    result = subprocess.run(build_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise RuntimeError(f"CMake build failed (exit {result.returncode})")

    if not output.exists():
        candidates = list(here.glob("_native*"))
        raise RuntimeError(f"Expected {output}, found {candidates}")

    if platform.system() == "Windows":
        for dll in ("libgcc_s_seh-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll"):
            src_dll = Path("C:/mingw64/bin") / dll
            if src_dll.exists():
                shutil.copy2(src_dll, here / dll)
                print(f"Copied: {dll}")

    print(f"Built: {output} ({output.stat().st_size} bytes)")
    return output


if __name__ == "__main__":
    build()
