#!/usr/bin/env python3
"""jcode Governance Installer — 部署 ai-dev-framework 到 jcode 全局目录。

用法:
    python scripts/install-governance.py          # 安装到 ~/.jcode/governance/
    python scripts/install-governance.py --path .  # 仅初始化当前项目

效果:
    - 安装后任何项目可通过 /governance 使用 26 种语言规则
    - 自动配置 pre-commit 钩子
    - 设置 mode_decision.conf
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ── 路径 ─────────────────────────────────────────────
THIS_DIR = Path(__file__).parent
PROJECT_ROOT = THIS_DIR.parent
AI_DEV_FRAMEWORK = PROJECT_ROOT / "ai-dev-framework"
TOOLS_SCRIPTS = PROJECT_ROOT / "tools" / "scripts"
JCODE_GOVERNANCE = Path.home() / ".jcode" / "governance"


def install_global() -> bool:
    """Install governance framework to ~/.jcode/governance/."""
    print("📦 安装 ADG Governance 到 ~/.jcode/governance/...")

    # 创建目录
    JCODE_GOVERNANCE.mkdir(parents=True, exist_ok=True)

    # 复制 ai-dev-framework
    target = JCODE_GOVERNANCE / "ai-dev-framework"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(AI_DEV_FRAMEWORK, target, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    print(f"  ✅ ai-dev-framework → {target}")

    # 创建 adg 包装脚本
    adg_wrapper = JCODE_GOVERNANCE / "adg"
    adg_wrapper.write_text(f"""#!/bin/bash
# ADG Governance CLI — 由 install-governance.py 生成
PYTHONPATH="{TOOLS_SCRIPTS.parent}:$PYTHONPATH" python3 -m tools.scripts.adg_cli "$@"
""")
    adg_wrapper.chmod(0o755)
    print(f"  ✅ adg CLI → {adg_wrapper}")

    # 创建 mode_decision.conf
    mode_conf = JCODE_GOVERNANCE / "mode_decision.conf"
    mode_conf.write_text("mode=quality\ngovernance_level=high\naudit_enabled=true\n")
    print(f"  ✅ mode_decision.conf → {mode_conf}")

    # 建议加入 PATH
    print(f"\n💡 将以下内容加入你的 shell 配置 (~/.bashrc / ~/.zshrc):")
    print(f'    export PATH="$HOME/.jcode/governance:$PATH"')
    print(f'    export JCODE_GOVERNANCE_DIR="$HOME/.jcode/governance/ai-dev-framework"')
    return True


def init_project() -> bool:
    """Initialize current project with governance hooks."""
    print("📋 初始化项目治理配置...")

    # .jcode/config.yml
    jcode_dir = PROJECT_ROOT / ".jcode"
    jcode_dir.mkdir(parents=True, exist_ok=True)

    config_yml = jcode_dir / "config.yml"
    if not config_yml.exists():
        config_yml.write_text("""# ADG Governance — 项目配置
language: zh-CN

# 代码注释规则
code_comments:
  language: zh-CN
  style: "注释使用中文，变量名和函数名保持英文"

commit_messages:
  language: zh-CN
  format: "type(scope): 中文描述"
  types:
    - feat
    - fix
    - refactor
    - docs
    - test
    - chore
""")
        print(f"  ✅ .jcode/config.yml")

    # mode_decision.conf
    mode_conf = jcode_dir / "mode_decision.conf"
    mode_conf.write_text("mode=quality\ngovernance_level=high\naudit_enabled=true\n")
    print(f"  ✅ .jcode/mode_decision.conf")

    # .jcode/hooks.json
    hooks_json = jcode_dir / "hooks.json"
    if not hooks_json.exists():
        hooks_json.write_text("""{
  "version": "1.1",
  "hooks": {
    "on_commit": [
      {
        "name": "lint-check",
        "skill": "governance-auditor",
        "action": "lint",
        "description": "提交时检查代码风格",
        "enabled": true
      },
      {
        "name": "governance-docs-check",
        "skill": "governance-docs-validator",
        "action": "validate",
        "description": "提交时验证治理文档",
        "condition": "files_contain('docs/')",
        "enabled": true
      }
    ],
    "on_pr": [
      {
        "name": "full-audit",
        "skill": "governance-auditor",
        "action": "full",
        "description": "PR 时运行完整审计",
        "enabled": true
      }
    ]
  }
}
""")
        print(f"  ✅ .jcode/hooks.json")

    # .pre-commit-config.yaml (append to existing or create)
    pre_commit = PROJECT_ROOT / ".pre-commit-config.yaml"
    if not pre_commit.exists():
        pre_commit.write_text("""repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: adg-governance
        name: ADG Governance Check
        entry: adg check .
        language: system
        files: '\\\\.(py|js|ts|rs|go|java|kt|cs)$'
        stages: [pre-commit]
""")
        print(f"  ✅ .pre-commit-config.yaml")

    print(f"\n✅ 项目初始化完成！")
    print(f"后续步骤:")
    print(f"  1. pip install pre-commit && pre-commit install")
    print(f"  2. adg check .")
    print(f"  3. git add . && git commit")
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="jcode Governance Installer")
    parser.add_argument("--path", help="仅初始化指定项目（不安装全局）")
    parser.add_argument("--global-only", action="store_true", help="仅安装全局，不初始化项目")

    args = parser.parse_args()

    if args.path:
        return 0 if init_project() else 1

    if args.global_only:
        return 0 if install_global() else 1

    # Default: both
    install_global()
    print()
    init_project()
    return 0


if __name__ == "__main__":
    sys.exit(main())
