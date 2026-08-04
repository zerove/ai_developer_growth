#!/usr/bin/env python3
"""
Jcode Init - 项目初始化命令

为任何项目生成 jcode 配置和 Agent 定义。
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from hook_system import create_default_config
from project_config import JcodeConfig, init_project


def init_jcode(
    project_name: str,
    project_type: str = "generic",
    language: str = "python",
    framework: str | None = None,
    output_dir: str = ".",
    force: bool = False,
) -> dict:
    """
    初始化 jcode 配置

    Args:
        project_name: 项目名称
        project_type: 项目类型
        language: 编程语言
        framework: 框架
        output_dir: 输出目录
        force: 强制覆盖

    Returns:
        初始化结果
    """
    output_path = Path(output_dir)

    # 检查是否已存在
    jcode_dir = output_path / ".jcode"
    if jcode_dir.exists() and not force:
        return {
            "success": False,
            "error": ".jcode directory already exists. Use --force to overwrite.",
        }

    # 创建目录
    jcode_dir.mkdir(parents=True, exist_ok=True)

    # 初始化项目配置
    config = init_project(project_name, project_type, language, framework, output_dir)

    # 初始化钩子配置
    hook_config = create_default_config(project_type)
    hook_config.save(str(jcode_dir / "hooks.json"))

    # 创建 Agent 定义
    agents_dir = output_path / "agents"
    agents_dir.mkdir(exist_ok=True)

    # 生成通用 Agent 定义
    _create_code_guardian_agent(agents_dir, config)
    _create_doc_curator_agent(agents_dir, config)

    # 创建 AGENTS.md
    _create_agents_md(output_path, config)

    # 创建 GOVERNANCE.md (如果不存在)
    governance_path = output_path / "GOVERNANCE.md"
    if not governance_path.exists():
        _create_governance_md(output_path, config)

    return {
        "success": True,
        "project": project_name,
        "language": language,
        "type": project_type,
        "files_created": [
            "jcode.yaml",
            ".jcode/PROJECT.md",
            ".jcode/hooks.json",
            "agents/code-guardian.md",
            "agents/doc-curator.md",
            "AGENTS.md",
            "GOVERNANCE.md",
        ],
    }


def _create_code_guardian_agent(agents_dir: Path, config: JcodeConfig) -> None:
    """创建 code-guardian Agent 定义"""
    lint_tool = config.project.lint_tool
    test_dir = config.project.tests_dir
    source_dir = config.project.source_dir

    (agents_dir / "code-guardian.md").write_text(
        f"""# Agent: code-guardian

维护代码质量、安全、风格一致性

## 指令

1. **执行代码风格检查**: 运行 `{lint_tool} {source_dir}` 检查代码风格，失败时阻止合并
2. **执行测试套件**: 运行 `pytest {test_dir}` 或相应测试命令，要求覆盖率 ≥ {config.project.min_test_coverage}%
3. **安全扫描**: 运行 `{config.project.security_scanner} {source_dir}` 检查安全漏洞
4. **依赖审计**: 运行 `pip-audit` 或相应工具检查依赖安全

## 工具

- lint
- test
- security
- build

## 约束

- 不能修改生产代码
- 不能跳过测试
- 不能忽略安全警告
""",
        encoding="utf-8",
    )


def _create_doc_curator_agent(agents_dir: Path, config: JcodeConfig) -> None:
    """创建 doc-curator Agent 定义"""
    docs_dir = config.project.docs_dir

    (agents_dir / "doc-curator.md").write_text(
        f"""# Agent: doc-curator

维护文档完整性、链接有效性、结构一致性

## 指令

1. **检查文档链接**: 运行链接检查工具验证 `{docs_dir}/` 目录下的文档链接
2. **验证文档格式**: 检查文档结构和格式是否符合规范
3. **更新索引**: 更新文档索引和目录
4. **同步文档与代码**: 确保文档与代码实现一致

## 工具

- read
- write
- edit
- glob

## 约束

- 不能删除文档
- 不能修改文档结构
- 必须保持向后兼容
""",
        encoding="utf-8",
    )


def _create_agents_md(output_path: Path, config: JcodeConfig) -> None:
    """创建 AGENTS.md"""
    (output_path / "AGENTS.md").write_text(
        """# Agent 定义索引

本项目中的所有 agent 定义，按职责分类索引。

---

## Agent 目录总览

| Agent | 中文名称 | 职责 | 状态 | 定义位置 |
|-------|----------|------|------|----------|
| `code-guardian` | 代码守护者 | 维护代码质量、安全、风格一致性 | ✅ 已定义 | `agents/code-guardian.md` |
| `doc-curator` | 文档策展人 | 维护文档完整性、链接有效性 | ✅ 已定义 | `agents/doc-curator.md` |

---

## 质量门禁

本项目遵循 4 道质量门禁:

1. **Gate 1**: Prompt 设计审查 (人工)
2. **Gate 2**: 实现代码审查 (Linter + 类型检查 + 人工)
3. **Gate 3**: 自动化审计 (CI/CD)
4. **Gate 4**: 资产更新 (更新 AGENTS.md、CONTEXT.md、ADR.md)

---

## 创建 Agent 检查清单

新增 agent 时必须完成:

- [ ] **命名**: kebab-case，如 `feature-builder`
- [ ] **描述**: 一句话，明确职责和作用域
- [ ] **指令**: 具体、可验证，含工具名/文件路径/函数名
- [ ] **工具**: 最小权限原则，不超过 10 个
- [ ] **约束**: 明确禁止行为

---

*本索引随 Agent 新增/修改时更新。*
""",
        encoding="utf-8",
    )


def _create_governance_md(output_path: Path, config: JcodeConfig) -> None:
    """创建 GOVERNANCE.md"""
    (output_path / "GOVERNANCE.md").write_text(
        f"""# 项目治理标准

> 适用于 {config.project.name} 的通用治理标准。

---

## 1. Agent 定义格式

所有 agent 定义必须包含以下字段:

```yaml
agent-name: kebab-case 命名
描述: 一句话核心职责
工具: 最小权限列表
约束: 明确的禁止行为
指令: 具体、可验证的操作步骤
```

## 2. 开发流程 (5 步闭环)

```
需求分析 → Prompt 设计 → 实现编码 → 自动化审计 → 资产更新
```

## 3. 质量门禁 (4 道门禁)

| 门禁 | 检查内容 | 通过标准 |
|------|----------|----------|
| Gate 1 | Prompt 设计 | 人工审查通过 |
| Gate 2 | 代码质量 | Lint + 类型检查通过 |
| Gate 3 | 自动化审计 | CI/CD 流水线通过 |
| Gate 4 | 资产更新 | 文档同步完成 |

## 4. 代码风格

- **语言**: {config.project.language}
- **Lint 工具**: {config.project.lint_tool}
- **类型检查**: {config.project.type_checker or "N/A"}
- **测试覆盖率**: ≥ {config.project.min_test_coverage}%

---

*本标准随项目演进更新。*
""",
        encoding="utf-8",
    )


def main():
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Jcode Init - 项目初始化")
    parser.add_argument("name", help="项目名称")
    parser.add_argument("--type", default="generic", help="项目类型 (generic, library, webapp, api, cli)")
    parser.add_argument("--language", default="python", help="编程语言")
    parser.add_argument("--framework", help="框架")
    parser.add_argument("--output", default=".", help="输出目录")
    parser.add_argument("--force", action="store_true", help="强制覆盖")

    args = parser.parse_args()

    result = init_jcode(
        project_name=args.name,
        project_type=args.type,
        language=args.language,
        framework=args.framework,
        output_dir=args.output,
        force=args.force,
    )

    if result["success"]:
        print(f"✅ Project '{args.name}' initialized successfully!")
        print("\nFiles created:")
        for f in result["files_created"]:
            print(f"  - {f}")
        print("\nNext steps:")
        print("  1. Review AGENTS.md and customize agent definitions")
        print("  2. Run your first audit: python .jcode/scripts/governance-auditor.py full")
        print("  3. Check hooks: cat .jcode/hooks.json")
    else:
        print(f"❌ Initialization failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
