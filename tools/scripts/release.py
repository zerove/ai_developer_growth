#!/usr/bin/env python3
"""
JCode Platform - Release Automation Script

功能:
- 语义化版本管理 (SemVer)
- 自动 CHANGELOG 生成
- 版本标记与 Git 标签
- 发布说明生成
- 集成: Docker 构建、SBOM、Cosign 签名 (后续脚本)

用法:
    python tools/scripts/release.py --version v2.0.0 --changelog
    python tools/scripts/release.py --bump patch --dry-run
    python tools/scripts/release.py --version v2.0.0 --push
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────
# 常量与配置
# ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.parent
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
VERSION_FILE = REPO_ROOT / "VERSION"

# 传统提交类型映射
COMMIT_TYPES = {
    "feat": "✨ 新功能",
    "fix": "🐛 修复",
    "refactor": "♻️ 重构",
    "perf": "⚡ 性能优化",
    "docs": "📝 文档",
    "test": "✅ 测试",
    "build": "🔧 构建",
    "ci": "🤖 CI",
    "chore": "🧹 维护",
    "revert": "⏪ 回滚",
    "security": "🔒 安全",
    "deps": "📦 依赖更新",
}

# 版本类型
VERSION_TYPES = ["major", "minor", "patch"]

# ──────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────


def run_cmd(cmd: list[str], cwd: Path | None = None, capture: bool = True) -> tuple[int, str]:
    """运行命令，返回 (退出码, 输出)"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or REPO_ROOT,
            capture_output=capture,
            text=True,
            check=False,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except Exception as e:
        return 1, str(e)


def get_current_version() -> str:
    """获取当前版本"""
    # 优先读取 VERSION 文件
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    # 回退到 pyproject.toml
    if PYPROJECT_PATH.exists():
        content = PYPROJECT_PATH.read_text()
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    # 回退到 Git 标签
    code, output = run_cmd(["git", "describe", "--tags", "--abbrev=0"])
    if code == 0 and output:
        return output.lstrip("v")
    return "0.0.0"


def parse_version(version: str) -> tuple[int, int, int]:
    """解析版本字符串为元组"""
    version = version.lstrip("v")
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_version(version: str, bump_type: str) -> str:
    """版本号递增"""
    major, minor, patch = parse_version(version)
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"未知版本类型: {bump_type}")
    return f"{major}.{minor}.{patch}"


def get_git_log(since_tag: str | None = None) -> list[dict[str, str]]:
    """获取 Git 提交历史"""
    cmd = ["git", "log", "--pretty=format:%H|%s|%an|%ad", "--date=short"]
    if since_tag:
        cmd.append(f"{since_tag}..HEAD")
    code, output = run_cmd(cmd)
    if code != 0:
        return []

    commits = []
    for line in output.split("\n"):
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append(
                {
                    "hash": parts[0][:8],
                    "subject": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                }
            )
    return commits


def parse_conventional_commit(subject: str) -> tuple[str | None, str]:
    """解析约定式提交"""
    match = re.match(r"^(\w+)(?:\([^)]+\))?!?:\s*(.+)$", subject)
    if match:
        return match.group(1).lower(), match.group(2)
    return None, subject


def group_commits_by_type(
    commits: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """按提交类型分组"""
    groups: dict[str, list[dict[str, str]]] = {k: [] for k in COMMIT_TYPES}
    groups["其他"] = []

    for commit in commits:
        ctype, desc = parse_conventional_commit(commit["subject"])
        if ctype and ctype in COMMIT_TYPES:
            commit["type"] = ctype
            commit["description"] = desc
            groups[ctype].append(commit)
        else:
            commit["type"] = "其他"
            commit["description"] = commit["subject"]
            groups["其他"].append(commit)

    # 移除空分组
    return {k: v for k, v in groups.items() if v}


def generate_changelog_entry(version: str, commits: list[dict[str, str]]) -> str:
    """生成 CHANGELOG 条目"""
    groups = group_commits_by_type(commits)
    date = datetime.now().strftime("%Y-%m-%d")

    lines = [f"## [{version}] - {date}", ""]

    for ctype, items in groups.items():
        label = COMMIT_TYPES.get(ctype, ctype)
        lines.append(f"### {label}")
        for item in items:
            lines.append(
                f"- {item['description']} ([{item['hash']}](https://github.com/{{repo}}/commit/{item['hash']}))"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def update_changelog(version: str, entry: str) -> None:
    """更新 CHANGELOG.md"""
    if CHANGELOG_PATH.exists():
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
    else:
        content = "# 更新日志\n\n本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 和 [约定式提交](https://www.conventionalcommits.org/zh-hans/v1.0.0/)。\n\n"

    # 在第一个版本条目前插入
    lines = content.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_idx = i
            break
    else:
        insert_idx = len(lines)

    lines.insert(insert_idx, entry.rstrip())
    CHANGELOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_version_files(version: str) -> None:
    """更新版本文件"""
    # VERSION 文件
    VERSION_FILE.write_text(f"{version}\n")

    # pyproject.toml
    if PYPROJECT_PATH.exists():
        content = PYPROJECT_PATH.read_text()
        content = re.sub(r'version\s*=\s*"[^"]+"', f'version = "{version}"', content)
        PYPROJECT_PATH.write_text(content)


def create_git_tag(version: str, message: str = "") -> tuple[int, str]:
    """创建 Git 标签"""
    tag = f"v{version}"
    if not message:
        message = f"Release {tag}"
    code, output = run_cmd(["git", "tag", "-a", tag, "-m", message])
    return code, output


def push_git_tag(tag: str) -> tuple[int, str]:
    """推送 Git 标签"""
    return run_cmd(["git", "push", "origin", tag])


def get_last_tag() -> str | None:
    """获取最近的版本标签"""
    code, output = run_cmd(["git", "describe", "--tags", "--abbrev=0", "--match=v*"])
    if code == 0 and output:
        return output
    return None


# ──────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────


def cmd_version(args: argparse.Namespace) -> int:
    """显示当前版本"""
    print(get_current_version())
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    """版本递增"""
    current = get_current_version()
    new_version = bump_version(current, args.type)
    print(f"当前版本: {current}")
    print(f"新版本: {new_version}")

    if args.dry_run:
        print("🔍 试运行模式，不写入文件")
        return 0

    # 获取最后标签后的提交
    last_tag = get_last_tag()
    commits = get_git_log(last_tag)

    # 生成 CHANGELOG
    entry = generate_changelog_entry(new_version, commits)
    update_changelog(new_version, entry)

    # 更新版本文件
    update_version_files(new_version)

    # Git 提交
    run_cmd(["git", "add", "CHANGELOG.md", "pyproject.toml", "VERSION"])
    commit_msg = f"chore: release v{new_version}"
    run_cmd(["git", "commit", "-m", commit_msg])

    # 创建标签
    create_git_tag(new_version)

    print(f"✅ 版本已更新至 v{new_version}")
    if not args.no_push:
        run_cmd(["git", "push"])
        push_git_tag(f"v{new_version}")
        print("✅ 已推送到远程")

    return 0


def cmd_changelog(args: argparse.Namespace) -> int:
    """生成/更新 CHANGELOG"""
    version = args.version or get_current_version()
    last_tag = get_last_tag()
    commits = get_git_log(last_tag)
    entry = generate_changelog_entry(version, commits)

    if args.dry_run:
        print(entry)
        return 0

    update_changelog(version, entry)
    print(f"✅ CHANGELOG 已更新 (版本: {version})")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """验证版本一致性"""
    version = get_current_version()
    print(f"当前版本: {version}")

    # 检查 pyproject.toml
    if PYPROJECT_PATH.exists():
        content = PYPROJECT_PATH.read_text()
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if match and match.group(1) != version:
            print(f"❌ pyproject.toml 版本不一致: {match.group(1)} != {version}")
            return 1

    # 检查 VERSION 文件
    if VERSION_FILE.exists():
        file_version = VERSION_FILE.read_text().strip()
        if file_version != version:
            print(f"❌ VERSION 文件不一致: {file_version} != {version}")
            return 1

    # 检查 Git 标签
    last_tag = get_last_tag()
    if last_tag and last_tag.lstrip("v") != version:
        print(f"⚠️  最新标签 ({last_tag}) 与当前版本 ({version}) 不一致")

    print("✅ 版本一致性验证通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="release",
        description="JCode Platform Release Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python release.py --version v2.0.0 --changelog
  python release.py --bump patch
  python release.py --bump minor --dry-run
  python release.py --verify
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # version
    subparsers.add_parser("version", help="显示当前版本")

    # bump
    bump_parser = subparsers.add_parser("bump", help="版本递增")
    bump_parser.add_argument("type", choices=VERSION_TYPES, help="版本类型")
    bump_parser.add_argument("--dry-run", action="store_true", help="试运行")
    bump_parser.add_argument("--no-push", action="store_true", help="不推送到远程")

    # changelog
    cl_parser = subparsers.add_parser("changelog", help="生成/更新 CHANGELOG")
    cl_parser.add_argument("--version", help="指定版本")
    cl_parser.add_argument("--dry-run", action="store_true", help="仅打印不写入")

    # verify
    subparsers.add_parser("verify", help="验证版本一致性")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    handlers = {
        "version": cmd_version,
        "bump": cmd_bump,
        "changelog": cmd_changelog,
        "verify": cmd_verify,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
