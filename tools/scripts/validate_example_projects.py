#!/usr/bin/env python3
"""
Example 项目标准化验证

检查每个 example 项目是否符合标准结构:
- pyproject.toml
- README.md
- tests/ 目录
- 至少一个 Python 源文件
"""

import sys
from pathlib import Path

REQUIRED_FILES = ["pyproject.toml", "README.md"]
REQUIRED_DIRS = ["tests"]
MIN_PYTHON_FILES = 1


def validate_example(example_dir: Path) -> list[str]:
    """验证 example 项目标准化.

        V2.21 P5-7 拆分: 抽 4 helper:
    - _check_required_files/dirs: 必填文件/目录守卫
    - _check_python_files: Python 文件数守卫
    - _check_pyproject: pyproject.toml 必填字段守卫
        主函数仅 4 委托.
    """
    issues: list[str] = []
    _check_required_files(example_dir, issues)
    _check_required_dirs(example_dir, issues)
    _check_python_files(example_dir, issues)
    _check_pyproject(example_dir, issues)
    return issues


def _check_required_files(example_dir: Path, issues: list[str]) -> None:
    """检查必需文件存在性 (模块级 helper)."""
    for f in REQUIRED_FILES:
        if not (example_dir / f).exists():
            issues.append(f"缺少文件: {f}")


def _check_required_dirs(example_dir: Path, issues: list[str]) -> None:
    """检查必需目录存在性 (模块级 helper)."""
    for d in REQUIRED_DIRS:
        if not (example_dir / d).is_dir():
            issues.append(f"缺少目录: {d}/")


def _check_python_files(example_dir: Path, issues: list[str]) -> None:
    """检查 Python 源文件数 (≥ MIN_PYTHON_FILES, 排除 __pycache__, 模块级 helper)."""
    py_files = [f for f in example_dir.rglob("*.py") if "__pycache__" not in str(f)]
    if len(py_files) < MIN_PYTHON_FILES:
        issues.append(f"Python 文件不足 (找到 {len(py_files)}, 至少需要 {MIN_PYTHON_FILES})")


def _check_pyproject(example_dir: Path, issues: list[str]) -> None:
    """检查 pyproject.toml 必填字段 (name/version, 模块级 helper)."""
    pyproject = example_dir / "pyproject.toml"
    if not pyproject.exists():
        return
    content = pyproject.read_text()
    if "name" not in content:
        issues.append("pyproject.toml 缺少 name 字段")
    if "version" not in content:
        issues.append("pyproject.toml 缺少 version 字段")


def main() -> None:
    """主函数"""
    examples_dir = Path("examples")
    if not examples_dir.exists():
        print("❌ examples/ 目录不存在")
        sys.exit(1)

    print("=" * 60)
    print("  Example 项目标准化验证")
    print("=" * 60)

    passed = 0
    failed = 0
    total_issues = 0

    for example_dir in sorted(examples_dir.iterdir()):
        if not example_dir.is_dir():
            continue

        issues = validate_example(example_dir)

        if issues:
            print(f"❌ {example_dir.name}")
            for issue in issues:
                print(f"   - {issue}")
            failed += 1
            total_issues += len(issues)
        else:
            print(f"✅ {example_dir.name}")
            passed += 1

    print("\n" + "=" * 60)
    print(f"  结果: {passed} 通过, {failed} 失败, {total_issues} 个问题")
    print("=" * 60)

    if failed > 0:
        print("\n建议: 为缺少 pyproject.toml 的项目创建标准配置")
        print("参考: examples/ai-navigation/pyproject.toml")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
