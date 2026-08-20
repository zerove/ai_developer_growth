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
    """"""
    issues = []

    # 检查必需文件
    for f in REQUIRED_FILES:
        if not (example_dir / f).exists():
            issues.append(f"缺少文件: {f}")

    # 检查必需目录
    for d in REQUIRED_DIRS:
        if not (example_dir / d).is_dir():
            issues.append(f"缺少目录: {d}/")

    # 检查 Python 源文件
    py_files = list(example_dir.rglob("*.py"))
    py_files = [f for f in py_files if "__pycache__" not in str(f)]
    if len(py_files) < MIN_PYTHON_FILES:
        issues.append(
            f"Python 文件不足 (找到 {len(py_files)}, 至少需要 {MIN_PYTHON_FILES})"
        )

    # 检查 pyproject.toml 内容
    pyproject = example_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        if "name" not in content:
            issues.append("pyproject.toml 缺少 name 字段")
        if "version" not in content:
            issues.append("pyproject.toml 缺少 version 字段")

    return issues


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
