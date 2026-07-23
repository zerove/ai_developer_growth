#!/usr/bin/env python3
"""
jcode Skill Runner - 共享模块

提供所有 skill 脚本共用的工具函数:
- run_command(): 执行外部命令并返回结果
- print_result(): 格式化输出检查结果
- get_project_root(): 获取项目根目录
"""

import subprocess
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录 (始终为 .jcode/scripts/ 的上级的上级)"""
    return Path(__file__).parent.parent.parent


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """运行命令并返回 (exit_code, combined_output)"""
    if cwd is None:
        cwd = get_project_root()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout + result.stderr


def print_check(name: str, passed: bool, output: str = "") -> None:
    """格式化输出检查结果"""
    icon = "✅" if passed else "❌"
    print(f"{icon} {name}")
    if output and not passed:
        for line in output.strip().split("\n")[:20]:
            print(f"  {line}")


def print_section(title: str) -> None:
    """打印分隔线和标题"""
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")
