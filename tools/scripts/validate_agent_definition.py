#!/usr/bin/env python3
"""
Agent 定义验证脚本

验证 Agent 定义文件是否符合 GOVERNANCE.md 规范。
支持两种格式:
1. YAML frontmatter (agent-name:, 描述:, 工具:, 约束:, 指令:)
2. Markdown (## agent: name, ### 指令, ### 工具, ### 约束)

检查项:
1. 命名规范 (kebab-case)
2. 必需字段 (描述、工具、约束、指令)
3. 工具权限最小化
4. 约束完整性
"""
import re
import sys
from pathlib import Path
from typing import TypedDict


class AgentValidationResult(TypedDict):
    file: str
    errors: list[str]
    warnings: list[str]
    passed: bool


def validate_agent_name(name: str) -> list[str]:
    """验证 Agent 名称是否符合命名规范"""
    errors = []

    # 检查 kebab-case
    if not re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name):
        errors.append(f"名称 '{name}' 不符合 kebab-case 规范")

    # 检查长度
    if len(name) < 3:
        errors.append(f"名称 '{name}' 太短 (至少 3 个字符)")
    if len(name) > 50:
        errors.append(f"名称 '{name}' 太长 (最多 50 个字符)")

    # 检查禁止的缩写
    abbreviations = ["hlp", "util", "mgr", "btn", "img", "txt"]
    for abbr in abbreviations:
        if abbr in name:
            errors.append(f"名称 '{name}' 包含缩写 '{abbr}'，请使用完整单词")

    return errors


def validate_agent_definition(filepath: Path) -> AgentValidationResult:
    """验证单个 Agent 定义文件"""
    result: AgentValidationResult = {
        "file": str(filepath),
        "errors": [],
        "warnings": [],
        "passed": True,
    }

    if not filepath.exists():
        result["errors"].append(f"文件不存在: {filepath}")
        result["passed"] = False
        return result

    content = filepath.read_text(encoding="utf-8")

    # 检测格式 (YAML frontmatter 或 Markdown)
    has_yaml = "agent-name:" in content and "描述:" in content
    has_md = bool(re.search(r"## agent:", content))

    if not has_yaml and not has_md:
        result["errors"].append("缺少必需的 frontmatter 或 Markdown 格式")
        result["passed"] = False
        return result

    # 2. 提取并验证名称
    name_match = re.search(r"agent-name:\s*(.+)", content) or \
                 re.search(r"## agent:\s*(\S+)", content)
    if name_match:
        name = name_match.group(1).strip()
        # 去掉括号内的中文名 (如 "knowledge-curator (知识策展人)")
        name = re.sub(r"\s*\(.*?\)\s*$", "", name)
        name_errors = validate_agent_name(name)
        result["errors"].extend(name_errors)
    else:
        result["errors"].append("无法提取 Agent 名称")

    # 3. 检查描述质量
    desc_match = re.search(r"描述:\s*(.+)", content) or \
                 re.search(r"## agent:\s*\S+\s*\((.+?)\)", content)
    if desc_match:
        desc = desc_match.group(1).strip()
        if len(desc) < 10:
            result["warnings"].append("描述太短，建议至少 10 个字符")
        if len(desc) > 100:
            result["warnings"].append("描述太长，建议不超过 100 个字符")
    else:
        result["warnings"].append("未找到描述字段")

    # 4. 检查工具权限
    tools_section = re.search(r"工具:(.+?)(?=\n约束:|$)", content, re.DOTALL) or \
                    re.search(r"### 工具\n(.+?)(?=\n###|$)", content, re.DOTALL)
    if tools_section:
        tools_text = tools_section.group(1)
        dangerous_tools = ["shell", "exec", "eval", "system"]
        for tool in dangerous_tools:
            if tool in tools_text.lower():
                result["warnings"].append(
                    f"工具 '{tool}' 可能存在安全风险，确认是否需要"
                )
    else:
        result["warnings"].append("未找到工具定义")

    # 5. 检查约束完整性
    constraints_section = re.search(r"约束:(.+?)(?=\n指令:|$)", content, re.DOTALL) or \
                          re.search(r"### 约束\n(.+?)(?=\n###|$)", content, re.DOTALL)
    if constraints_section:
        constraints_text = constraints_section.group(1)
        if len(constraints_text.strip()) < 20:
            result["warnings"].append("")
    else:
        result["warnings"].append("未找到约束定义")

    instructions_section = re.search(r"指令:(.+)", content, re.DOTALL) or \
                           re.search(r"### 指令\n(.+)", content, re.DOTALL)
    if instructions_section:
        instructions_text = instructions_section.group(1)
        if not re.search(r"(tools/|scripts/|\.py|\.sh|\.js)", instructions_text):
            result["warnings"].append("")
    else:
        result["warnings"].append("未找到指令定义")

    result["passed"] = len(result["errors"]) == 0
    return result


def validate_all_agents(agents_dir: Path = Path("agents")) -> list[AgentValidationResult]:
    """验证所有 Agent 定义文件"""
    results: list[AgentValidationResult] = []

    if not agents_dir.exists():
        print(f"❌ Agent 目录不存在: {agents_dir}")
        return results

    for filepath in sorted(agents_dir.glob("*.md")):
        result = validate_agent_definition(filepath)
        results.append(result)

        status = "✅" if result["passed"] else "❌"
        print(f"{status} {filepath.name}")

        for error in result["errors"]:
            print(f"   ❌ {error}")
        for warning in result["warnings"]:
            print(f"   ⚠️  {warning}")

    return results


def main() -> None:
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="验证 Agent 定义文件")
    parser.add_argument(
        "--path", type=Path, default=Path("agents"), help="Agent 目录路径"
    )
    parser.add_argument("--file", type=Path, help="验证单个文件")
    args = parser.parse_args()

    print("=" * 60)
    print("  Agent 定义验证")
    print("=" * 60)

    if args.file:
        result = validate_agent_definition(args.file)
        results = [result]
        status = "✅" if result["passed"] else "❌"
        print(f"{status} {args.file.name}")
        for error in result["errors"]:
            print(f"   ❌ {error}")
        for warning in result["warnings"]:
            print(f"   ⚠️  {warning}")
    else:
        results = validate_all_agents(args.path)

    # 汇总
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])

    print("\n" + "=" * 60)
    print(f"  结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
