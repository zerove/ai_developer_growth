"""
Jcode Config - 参数化配置系统

适用于任何项目的配置加载和管理。
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectConfig:
    """项目配置"""
    name: str
    type: str  # library, webapp, api, cli, knowledge-base
    language: str
    framework: Optional[str] = None

    # 目录结构
    source_dir: str = "src"
    tests_dir: str = "tests"
    docs_dir: str = "docs"
    scripts_dir: str = "scripts"

    # 质量门禁
    min_test_coverage: int = 70
    lint_tool: str = "ruff"
    type_checker: Optional[str] = None
    security_scanner: str = "bandit"


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    description: str
    responsibilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)


@dataclass
class JcodeConfig:
    """Jcode 完整配置"""
    project: ProjectConfig
    agents: list[AgentConfig] = field(default_factory=list)
    hooks: dict = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str) -> "JcodeConfig":
        """从文件加载配置"""
        path = Path(config_path)

        if path.suffix == ".yaml" or path.suffix == ".yml":
            return cls._load_yaml(path)
        elif path.suffix == ".json":
            return cls._load_json(path)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")

    @classmethod
    def _load_yaml(cls, path: Path) -> "JcodeConfig":
        """加载 YAML 配置"""
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
        except ImportError:
            # Fallback: 简单解析
            data = cls._parse_yaml_simple(path)

        return cls._from_dict(data)

    @classmethod
    def _load_json(cls, path: Path) -> "JcodeConfig":
        """加载 JSON 配置"""
        with open(path) as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "JcodeConfig":
        """从字典创建配置"""
        project_data = data.get("project", {})
        project = ProjectConfig(
            name=project_data.get("name", "unknown"),
            type=project_data.get("type", "library"),
            language=project_data.get("language", "python"),
            framework=project_data.get("framework"),
            source_dir=project_data.get("directories", {}).get("source", "src"),
            tests_dir=project_data.get("directories", {}).get("tests", "tests"),
            docs_dir=project_data.get("directories", {}).get("docs", "docs"),
            scripts_dir=project_data.get("directories", {}).get("scripts", "scripts"),
            min_test_coverage=project_data.get("quality", {}).get("min_test_coverage", 70),
            lint_tool=project_data.get("quality", {}).get("lint_tool", "ruff"),
            type_checker=project_data.get("quality", {}).get("type_checker"),
            security_scanner=project_data.get("quality", {}).get("security_scanner", "bandit"),
        )

        agents = []
        for agent_name, agent_data in data.get("agents", {}).items():
            if isinstance(agent_data, dict):
                agents.append(AgentConfig(
                    name=agent_name,
                    description=agent_data.get("description", ""),
                    responsibilities=agent_data.get("responsibilities", []),
                    tools=agent_data.get("tools", []),
                    triggers=agent_data.get("triggers", []),
                ))

        return cls(
            project=project,
            agents=agents,
            hooks=data.get("hooks", {}),
        )

    @classmethod
    def _parse_yaml_simple(cls, path: Path) -> dict:
        """简单 YAML 解析 (无依赖)"""
        # 这是一个简化实现，生产环境应使用 PyYAML
        data = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if value:
                            data[key] = value
        return data

    def save(self, config_path: str) -> None:
        """保存配置到文件"""
        path = Path(config_path)
        data = self.to_dict()

        if path.suffix == ".json":
            with open(path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif path.suffix == ".yaml" or path.suffix == ".yml":
            # 简单 YAML 输出
            with open(path, "w") as f:
                f.write("# Jcode Project Configuration\n")
                f.write(f"project:\n")
                f.write(f"  name: \"{self.project.name}\"\n")
                f.write(f"  type: \"{self.project.type}\"\n")
                f.write(f"  language: \"{self.project.language}\"\n")
                if self.project.framework:
                    f.write(f"  framework: \"{self.project.framework}\"\n")
                f.write(f"  directories:\n")
                f.write(f"    source: \"{self.project.source_dir}\"\n")
                f.write(f"    tests: \"{self.project.tests_dir}\"\n")
                f.write(f"    docs: \"{self.project.docs_dir}\"\n")
                f.write(f"  quality:\n")
                f.write(f"    min_test_coverage: {self.project.min_test_coverage}\n")
                f.write(f"    lint_tool: \"{self.project.lint_tool}\"\n")
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "project": {
                "name": self.project.name,
                "type": self.project.type,
                "language": self.project.language,
                "framework": self.project.framework,
                "directories": {
                    "source": self.project.source_dir,
                    "tests": self.project.tests_dir,
                    "docs": self.project.docs_dir,
                    "scripts": self.project.scripts_dir,
                },
                "quality": {
                    "min_test_coverage": self.project.min_test_coverage,
                    "lint_tool": self.project.lint_tool,
                    "type_checker": self.project.type_checker,
                    "security_scanner": self.project.security_scanner,
                },
            },
            "agents": {
                agent.name: {
                    "description": agent.description,
                    "responsibilities": agent.responsibilities,
                    "tools": agent.tools,
                    "triggers": agent.triggers,
                }
                for agent in self.agents
            },
            "hooks": self.hooks,
        }


def init_project(
    project_name: str,
    project_type: str = "library",
    language: str = "python",
    framework: Optional[str] = None,
    output_dir: str = ".",
) -> JcodeConfig:
    """
    初始化项目配置

    Args:
        project_name: 项目名称
        project_type: 项目类型 (library, webapp, api, cli, knowledge-base)
        language: 编程语言
        framework: 框架 (可选)
        output_dir: 输出目录

    Returns:
        JcodeConfig: 项目配置
    """
    # 根据语言选择默认工具
    tool_defaults = {
        "python": {"lint": "ruff", "type": "mypy", "test": "pytest", "security": "bandit"},
        "typescript": {"lint": "eslint", "type": "tsc", "test": "vitest", "security": "semgrep"},
        "rust": {"lint": "clippy", "type": "cargo", "test": "cargo", "security": "cargo-audit"},
        "go": {"lint": "golangci-lint", "type": "go vet", "test": "go test", "security": "gosec"},
    }

    defaults = tool_defaults.get(language, tool_defaults["python"])

    # 创建配置
    config = JcodeConfig(
        project=ProjectConfig(
            name=project_name,
            type=project_type,
            language=language,
            framework=framework,
            lint_tool=defaults["lint"],
            type_checker=defaults.get("type"),
            security_scanner=defaults["security"],
        ),
        agents=[
            AgentConfig(
                name="code-guardian",
                description="维护代码质量、安全、风格一致性",
                responsibilities=["lint检查", "测试运行", "安全扫描"],
                tools=["lint", "test", "security"],
                triggers=["on_commit", "on_pr"],
            ),
            AgentConfig(
                name="doc-curator",
                description="维护文档完整性、链接有效性",
                responsibilities=["链接检查", "格式验证", "索引更新"],
                tools=["read", "write", "edit"],
                triggers=["on_merge", "scheduled"],
            ),
        ],
    )

    # 保存配置
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    config.save(str(output_path / "jcode.yaml"))

    # 创建 .jcode 目录
    jcode_dir = output_path / ".jcode"
    jcode_dir.mkdir(exist_ok=True)

    # 生成 PROJECT.md
    (jcode_dir / "PROJECT.md").write_text(f"""# {project_name} - jcode Configuration

## Project Info
- **Name**: {project_name}
- **Type**: {project_type}
- **Language**: {language}
- **Framework**: {framework or 'N/A'}

## Agent Skills

本项目注册了以下 agent skills:

| Skill | Description |
|-------|-------------|
| code-guardian | 维护代码质量、安全、风格一致性 |
| doc-curator | 维护文档完整性、链接有效性 |

## Quick Commands

```bash
# Lint check
{defaults['lint']} {config.project.source_dir}

# Run tests
{defaults['test']} {config.project.tests_dir}

# Security scan
{defaults['security']} {config.project.source_dir}
```
""", encoding="utf-8")

    return config


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python project_config.py <command> [args]")
        print("Commands:")
        print("  init <name> [type] [language] [framework]")
        print("  load <config_path>")
        print("  validate <config_path>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        name = sys.argv[2] if len(sys.argv) > 2 else "my-project"
        project_type = sys.argv[3] if len(sys.argv) > 3 else "library"
        language = sys.argv[4] if len(sys.argv) > 4 else "python"
        framework = sys.argv[5] if len(sys.argv) > 5 else None

        config = init_project(name, project_type, language, framework)
        print(f"✅ Project '{name}' initialized")
        print(f"   Config: jcode.yaml")
        print(f"   Language: {language}")
        print(f"   Type: {project_type}")

    elif command == "load":
        config_path = sys.argv[2] if len(sys.argv) > 2 else "jcode.yaml"
        config = JcodeConfig.load(config_path)
        print(f"✅ Config loaded: {config.project.name}")
        print(f"   Language: {config.project.language}")
        print(f"   Agents: {len(config.agents)}")

    elif command == "validate":
        config_path = sys.argv[2] if len(sys.argv) > 2 else "jcode.yaml"
        try:
            config = JcodeConfig.load(config_path)
            print(f"✅ Config is valid")
            print(f"   Project: {config.project.name}")
            print(f"   Language: {config.project.language}")
        except Exception as e:
            print(f"❌ Config validation failed: {e}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
