#!/usr/bin/env python3
"""
jcode Skill Runner - 知识策展人

用法:
    python .jcode/scripts/knowledge-curator.py scan
    python .jcode/scripts/knowledge-curator.py audit
    python .jcode/scripts/knowledge-curator.py validate docs/case-studies/new-case.md
    python .jcode/scripts/knowledge-curator.py sync
    python .jcode/scripts/knowledge-curator.py update-moc  # 尚未实现
"""

import sys

from _common import print_check, print_section, run_command


def scan() -> int:
    """扫描所有案例格式完整性"""
    print_section("案例格式扫描")
    code, output = run_command([sys.executable, "tools/scripts/validate_case_study.py", "--all", "--strict"])
    print_check("案例扫描", code == 0, output)
    if code != 0:
        print(output)
    return code


def audit() -> int:
    """检查文档断链"""
    print_section("文档断链检查")
    code, output = run_command([sys.executable, "tools/scripts/link_auditor.py", ".", "--check-all"])
    print_check("链接检查", code == 0, output)
    if code != 0:
        print(output)
    return code


def validate(file_path: str) -> int:
    """"""
    print_section(f"案例验证: {file_path}")
    code, output = run_command([sys.executable, "tools/scripts/validate_case_study.py", "--path", file_path])
    print_check("案例验证", code == 0, output)
    if code != 0:
        print(output)
    return code


def sync() -> int:
    """同步工具矩阵"""
    print_section("工具矩阵同步")
    code, output = run_command([sys.executable, "tools/scripts/update_ai_tool_matrix.py"])
    print_check("工具矩阵", code == 0, output)
    if code != 0:
        print(output)
    return code


def update_moc() -> int:
    """更新知识图谱（尚未实现）.

    历史实现调用 `link_auditor.py --update-moc`（该参数不存在），必然失败。
    保留显式非零退出，避免调用方误以为能力可用。
    """
    print("❌ update-moc 尚未实现：MOC 更新需要独立脚本")
    return 1


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: knowledge-curator.py <action> [args]")
        print("Actions: scan, audit, validate <file>, sync, update-moc（尚未实现）")
        sys.exit(1)

    action = sys.argv[1]

    action_map = {
        "scan": scan,
        "audit": audit,
        "validate": lambda: validate(sys.argv[2]) if len(sys.argv) > 2 else (print("错误: 需要指定文件路径") or 1),
        "sync": sync,
        "update-moc": update_moc,
    }

    if action in action_map:
        sys.exit(action_map[action]())
    else:
        print(f"❌ 未知 action: {action}")
        print(f"可用 actions: {', '.join(action_map.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
