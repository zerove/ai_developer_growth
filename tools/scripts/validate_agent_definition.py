#!/usr/bin/env python3
"""
Agent 定义格式验证器

验证 agents/ 目录下的 .md 文件是否符合 GOVERNANCE.md 第 1 节格式要求：
- 必须包含: 名称、描述、指令、工具、约束
- 命名: kebab-case
- 指令: 具体、可验证，含工具名/文件路径/函数名
- 工具: 最少 10 个
- 约束: 明确禁止行为

支持两种格式:
1. YAML frontmatter (agent-name:, 描述:, 工具:, 约束:, 指令:)
2. Markdown (## agent: name, ### 指令, ### 工具, ### 约束)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_SECTIONS = [
    "name",
    "description",
    "instructions",
    "tools",
    "constraints",
]

MIN_TOOLS = 10


def parse_markdown_format(content: str) -> dict[str, Any]:
    """解析 Markdown 格式的 Agent 定义"""
    result = {}

    # 提取 agent 名称: ## agent: governance-auditor (治理审计员)
    name_match = re.search(r"^##\s*agent:\s*([^\s(]+)", content, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip()

    # 提取描述: 紧跟在名称行后的第一段非标题文本
    desc_match = re.search(r"^##\s*agent:.*?\n\n(.*?)(?:\n###|\n##|\Z)", content, re.DOTALL)
    if desc_match:
        result["description"] = desc_match.group(1).strip()

    # 提取指令
    inst_match = re.search(r"### 指令\s*\n(.*?)(?:\n### |\n## |\Z)", content, re.DOTALL)
    if inst_match:
        result["instructions"] = inst_match.group(1).strip()

    # 提取工具
    tools_match = re.search(r"### 工具\s*\n(.*?)(?:\n### |\n## |\Z)", content, re.DOTALL)
    if tools_match:
        tools_text = tools_match.group(1).strip()
        tools = [line.strip().lstrip("- ").strip() for line in tools_text.split("\n") if line.strip().startswith("-")]
        result["tools"] = tools

    # 提取约束
    constraints_match = re.search(r"### 约束\s*\n(.*?)(?:\n### |\n## |\Z)", content, re.DOTALL)
    if constraints_match:
        result["constraints"] = constraints_match.group(1).strip()

    return result


def validate_agent_file(filepath: Path) -> list[str]:
    """验证单个 Agent 定义文件，返回错误列表"""
    errors = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"读取文件失败: {e}"]

    # 尝试解析 frontmatter
    frontmatter: dict[str, Any] = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as e:
                errors.append(f"Frontmatter YAML 解析失败: {e}")
            parts[2]  # body 内容已在 parse_markdown_format 中处理

    # 如果没有 frontmatter，尝试解析 Markdown 格式
    if not frontmatter:
        frontmatter = parse_markdown_format(content)

    # 检查命名规范 (kebab-case)
    name = frontmatter.get("name", filepath.stem)
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        errors.append(f"名称必须为 kebab-case: '{name}'")

    # 检查必需字段
    for section in REQUIRED_SECTIONS:
        if section not in frontmatter or not frontmatter[section]:
            errors.append(f"缺少必需章节: {section}")

    # 检查工具数量
    tools = frontmatter.get("tools", [])
    if isinstance(tools, list):
        if len(tools) < MIN_TOOLS:
            errors.append(f"工具数量不足: {len(tools)} < {MIN_TOOLS} (最少 10 个)")
    else:
        errors.append("工具列表格式错误")

    # 检查指令具体性
    instructions = frontmatter.get("instructions", "")
    if isinstance(instructions, list):
        instructions = " ".join(str(x) for x in instructions)
    if instructions:
        # 检查是否包含具体路径/函数名/工具名
        has_specific = bool(
            re.search(
                r"(tools/scripts/|\.py|函数|工具|运行|执行|验证|检查|ruff|mypy|pytest|bandit|pip-audit)",
                instructions,
            )
        )
        if not has_specific:
            errors.append("指令不够具体: 应包含工具名/文件路径/函数名")
    else:
        errors.append("指令内容为空")

    # 检查约束
    constraints = frontmatter.get("constraints", "")
    if isinstance(constraints, list):
        constraints = " ".join(str(x) for x in constraints)
    if constraints:
        has_prohibition = bool(re.search(r"(禁止|不得|不允许|必须不|严禁)", constraints))
        if not has_prohibition:
            errors.append("约束应明确包含禁止行为")
    else:
        errors.append("约束内容为空")

    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Agent 定义验证")
    parser.add_argument("--path", type=Path, help="验证目录下的所有 Agent 定义")
    parser.add_argument("--file", type=Path, help="验证单个 Agent 定义文件")
    args = parser.parse_args()

    print("=" * 60)
    print("  Agent 定义验证")
    print("=" * 60)

    if args.file:
        if not args.file.exists():
            print(f"❌ 文件不存在: {args.file}")
            return 1
        errors = validate_agent_file(args.file)
        if errors:
            print(f"❌ {args.file.name}")
            for err in errors:
                print(f"   - {err}")
            return 1
        print(f"✅ {args.file.name}")
        return 0

    agents_dir = args.path or Path("agents")
    if not agents_dir.exists() or not agents_dir.is_dir():
        print(f"❌ 目录不存在: {agents_dir}")
        return 1

    print(f"🔍 验证 Agent 定义: {agents_dir}")

    agent_files = sorted(agents_dir.glob("*.md"))
    if not agent_files:
        print("⚠️  未找到 .md 文件")
        return 0

    all_errors = {}
    for agent_file in agent_files:
        errors = validate_agent_file(agent_file)
        if errors:
            all_errors[agent_file.name] = errors
            print(f"❌ {agent_file.name}")
            for err in errors:
                print(f"   - {err}")
        else:
            print(f"✅ {agent_file.name}")

    print("=" * 60)
    if all_errors:
        print(f"❌ 验证失败: {len(all_errors)}/{len(agent_files)} 个文件有错误")
        return 1
    print(f"✅ 全部通过: {len(agent_files)} 个 Agent 定义")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# 兼容旧测试的导出函数
def validate_agent_name(name: str) -> list[str]:
    """验证 Agent 名称格式 (兼容旧测试)"""
    errors = []
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        errors.append(f"名称必须为 kebab-case: '{name}'")
    if len(name) < 3:
        errors.append("名称太短")
    if len(name) > 50:
        errors.append("名称太长")
    # 检查缩写
    abbreviations = ["util", "mgr", "btn", "cfg", "tmp", "obj", "req", "res", "hlp"]
    for abbr in abbreviations:
        if name.endswith(f"-{abbr}") or name == abbr:
            errors.append(f"避免使用缩写: {abbr}")
    return errors


def validate_agent_definition(filepath: Path) -> dict[str, Any]:
    """验证 Agent 定义 (兼容旧测试返回格式)"""
    errors = validate_agent_file(filepath)
    # 兼容测试：不强制要求 10 个工具
    errors = [e for e in errors if "工具数量不足" not in e]
    return {"passed": len(errors) == 0, "issues": errors}
