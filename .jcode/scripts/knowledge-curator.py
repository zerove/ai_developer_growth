#!/usr/bin/env python3
"""
jcode Skill Runner - 知识策展人

用法:
    python .jcode/scripts/knowledge-curator.py scan
    python .jcode/scripts/knowledge-curator.py audit
    python .jcode/scripts/knowledge-curator.py validate case-studies/new-case.md
    python .jcode/scripts/knowledge-curator.py sync
    python .jcode/scripts/knowledge-curator.py update-moc
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str]:
    """运行命令并返回结果"""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)
    return result.returncode, result.stdout + result.stderr


def scan() -> None:
    """扫描所有案例格式完整性"""
    print("🔍 扫描案例格式完整性...")
    code, output = run_command([
        sys.executable, "tools/scripts/validate_case_study.py", "--all", "--strict"
    ])
    print(output)
    sys.exit(code)


def audit() -> None:
    """检查文档断链"""
    print("🔗 检查文档断链...")
    code, output = run_command([
        sys.executable, "tools/scripts/link_auditor.py", ".", "--check-all"
    ])
    print(output)
    sys.exit(code)


def validate(file_path: str) -> None:
    """验证新提交案例"""
    print(f"✅ 验证案例: {file_path}")
    code, output = run_command([
        sys.executable, "tools/scripts/validate_case_study.py", "--path", file_path
    ])
    print(output)
    sys.exit(code)


def sync() -> None:
    """同步工具矩阵"""
    print("🔄 同步工具矩阵...")
    code, output = run_command([
        sys.executable, "tools/scripts/update_ai_tool_matrix.py"
    ])
    print(output)
    sys.exit(code)


def update_moc() -> None:
    """更新知识图谱"""
    print("📊 更新知识图谱...")
    code, output = run_command([
        sys.executable, "tools/scripts/link_auditor.py", ".", "--update-moc"
    ])
    print(output)
    sys.exit(code)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: knowledge-curator.py <action> [args]")
        print("Actions: scan, audit, validate <file>, sync, update-moc")
        sys.exit(1)

    action = sys.argv[1]

    actions = {
        "scan": lambda: scan(),
        "audit": lambda: audit(),
        "validate": lambda: validate(sys.argv[2]) if len(sys.argv) > 2 else print("错误: 需要指定文件路径"),
        "sync": lambda: sync(),
        "update-moc": lambda: update_moc(),
    }

    if action in actions:
        actions[action]()
    else:
        print(f"未知 action: {action}")
        print("可用 actions: " + ", ".join(actions.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()
