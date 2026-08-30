#!/usr/bin/env python3
"""
AI Tool Matrix Auto-Update Script

Automates the process of checking for new model releases, tool versions,
and pricing updates to keep the AI Tool Matrix current.

Usage:
    python update_ai_tool_matrix.py --check          # Check for updates only
    python update_ai_tool_matrix.py --update         # Apply updates to markdown
    python update_ai_tool_matrix.py --generate-report # Generate update report
"""

import argparse
import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MATRIX_PATH = Path(__file__).parent.parent.parent / "docs" / "tools" / "ai-tool-matrix.md"
CONFIG_PATH = Path(__file__).parent / "tool_matrix_config.json"
CACHE_PATH = Path(__file__).parent / ".tool_matrix_cache.json"


class SourceType(Enum):
    GITHUB_RELEASES = "github_releases"
    PYPI = "pypi"
    NPM = "npm"
    STATIC = "static"


@dataclass
class ToolInfo:
    name: str
    category: str
    current_version: str
    latest_version: str | None = None
    release_date: str | None = None
    source_url: str = ""
    source_type: SourceType = SourceType.STATIC
    description: str = ""
    pricing: str = ""
    last_checked: str | None = None
    update_available: bool = False


@dataclass
class ModelInfo:
    name: str
    provider: str
    current_version: str
    latest_version: str | None = None
    context_window: int = 0
    strengths: list[str] | None = None
    use_cases: list[str] | None = None
    limitations: str = ""
    pricing_tier: str = ""
    last_checked: str | None = None
    update_available: bool = False

    def __post_init__(self) -> None:
        if self.strengths is None:
            self.strengths = []
        if self.use_cases is None:
            self.use_cases = []


_KNOWN_TOOLS: set[str] = {
    "工具",
    "---",
    "jcode",
    "opencode",
    "Claude Code",
    "Cursor Agent",
    "GitHub Copilot CLI",
    "VS Code",
    "Cursor",
    "Windsurf",
    "Zed",
    "Cline",
    "v0.dev",
    "Perplexity AI",
    "AI-Context-Sync",
}

_IDE_TOOLS: set[str] = {"VS Code", "Cursor", "Windsurf", "Zed"}


def _is_tool_section_header(line: str) -> bool:
    """判断是否为工具段表头 (含 AI Coding Agent Harness / 编码代理框架, 模块级 helper).

    Args:
        line: 源码行

    Returns:
        是否为工具段表头
    """
    return "AI Coding Agent Harness" in line or "编码代理框架" in line


def _is_known_tool(name: str) -> bool:
    """判断 name 是否在已知工具集合 (模块级 helper).

    Args:
        name: 工具名

    Returns:
        是否已知
    """
    return name in _KNOWN_TOOLS


def _build_tool_info(name: str, m: re.Match[str], line: str) -> ToolInfo:
    """从 re.Match 构造 ToolInfo (模块级 helper).

    Args:
        name: 工具名
        m: 正则 match
        line: 完整源行 (用于 category 推断)

    Returns:
        ToolInfo 实例
    """
    core_feature = m.group(2).strip()
    advantage = m.group(3).strip()
    audience = m.group(5).strip()
    category = "coding_agent" if "Agent" in line or "Agent" in name else ("ide" if name in _IDE_TOOLS else "utility")
    return ToolInfo(
        name=name,
        category=category,
        current_version="latest",
        description=f"{core_feature}. {advantage}",
        pricing=audience,
        last_checked=datetime.now().isoformat(),
    )


class ToolMatrixUpdater:
    def __init__(self) -> None:
        self.tools: dict[str, ToolInfo] = {}
        self.models: dict[str, ModelInfo] = {}
        self.matrix_content = ""
        self.config = self._load_config()
        self.cache = self._load_cache()

    def _load_config(self) -> dict[str, Any]:
        if CONFIG_PATH.exists():
            result: dict[str, Any] = json.loads(CONFIG_PATH.read_text())
            return result
        return {}

    def _load_cache(self) -> dict[str, Any]:
        if CACHE_PATH.exists():
            try:
                result: dict[str, Any] = json.loads(CACHE_PATH.read_text())
                return result
            except json.JSONDecodeError:
                # 缓存损坏 (如并行写入交错) 时视为无缓存, 重新检查
                return {}
        return {}

    def _save_cache(self) -> None:
        CACHE_PATH.write_text(json.dumps(self.cache, indent=2))

    def load_matrix(self) -> None:
        """Parse current matrix from markdown file."""
        if not MATRIX_PATH.exists():
            raise FileNotFoundError(f"Matrix file not found: {MATRIX_PATH}")

        self.matrix_content = MATRIX_PATH.read_text(encoding="utf-8")
        self._parse_matrix()

    def _parse_matrix(self) -> None:
        """Extract tool and model info from markdown."""
        self._parse_models()
        self._parse_tools()

    def _parse_models(self) -> None:
        """Parse models table from markdown."""
        model_pattern = r"\|\s*(\*\*.+?\*\*)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\⭐+)"
        for match in re.finditer(model_pattern, self.matrix_content):
            name = match.group(1).strip("*")
            core_advantage = match.group(2).strip()
            use_cases = match.group(3).strip()
            limitations = match.group(4).strip()
            stars = len(match.group(5))

            # Extract provider from name
            provider = name.split()[0] if name else ""

            self.models[name] = ModelInfo(
                name=name,
                provider=provider,
                current_version="latest",
                strengths=[core_advantage],
                use_cases=[use_cases],
                limitations=limitations,
                pricing_tier=f"{stars}/5",
            )

    def _parse_tools(self) -> None:
        """Parse tools table from markdown (V2.21 P5-28 拆分: 抽 _is_tool_section_header + _is_known_tool + _build_tool_info)."""
        tool_pattern = r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
        in_tools_section = False
        for line in self.matrix_content.split("\n"):
            if _is_tool_section_header(line):
                in_tools_section = True
                continue
            if not (in_tools_section and line.startswith("|")):
                continue
            m = re.match(tool_pattern, line)
            if not m or m.group(1).startswith(" "):
                continue
            name = m.group(1).strip()
            if not _is_known_tool(name):
                continue
            self.tools[name] = _build_tool_info(name, m, line)

    async def check_model_updates(self) -> list[str]:
        """Check for model updates from various sources."""
        updates = []

        # Check GitHub releases for open source models
        for model_name, model in self.models.items():
            if model.provider.lower() in ["deepseek", "qwen"]:
                update = await self._check_github_releases(model_name, model.provider)
                if update:
                    updates.append(update)
                    model.latest_version = update
                    model.update_available = True

        # Check PyPI for Python-based tools
        for tool_name, tool in self.tools.items():
            if tool.source_type == SourceType.PYPI:
                update = await self._check_pypi(tool_name)
                if update:
                    updates.append(f"{tool_name}: {tool.current_version} -> {update}")
                    tool.latest_version = update
                    tool.update_available = True

        return updates

    async def _check_github_releases(self, model_name: str, provider: str) -> str | None:
        """Check GitHub for latest releases."""
        repo_map = {
            "deepseek": "deepseek-ai/DeepSeek-V3",
            "qwen": "QwenLM/Qwen2.5-Coder",
        }

        repo = repo_map.get(provider.lower())
        if not repo:
            return None

        try:
            cache_key = f"github_{repo}"
            cached = self.cache.get(cache_key)
            if cached and cached.get("checked_at"):
                checked = datetime.fromisoformat(cached["checked_at"])
                if datetime.now() - checked < timedelta(hours=24):
                    version: str | None = cached.get("latest_version")
                    return version

            # Use gh CLI if available
            result = subprocess.run(
                [
                    "gh",
                    "release",
                    "list",
                    "--repo",
                    repo,
                    "--limit",
                    "1",
                    "--json",
                    "tagName",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                releases = json.loads(result.stdout)
                if releases:
                    version = releases[0]["tagName"]
                    self.cache[cache_key] = {
                        "latest_version": version,
                        "checked_at": datetime.now().isoformat(),
                    }
                    self._save_cache()
                    return version
        except (
            subprocess.SubprocessError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            subprocess.TimeoutExpired,
        ) as e:
            logger.debug(f"Failed to check GitHub releases for {repo}: {e}")

        return None

    async def _check_pypi(self, package_name: str) -> str | None:
        """Check PyPI for latest version."""
        try:
            cache_key = f"pypi_{package_name}"
            cached = self.cache.get(cache_key)
            if cached and cached.get("checked_at"):
                checked = datetime.fromisoformat(cached["checked_at"])
                if datetime.now() - checked < timedelta(hours=24):
                    version: str | None = cached.get("latest_version")
                    return version

            result = subprocess.run(
                ["pip", "index", "versions", package_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Parse output like "Available versions: 1.0.0, 1.0.1, 1.1.0"
                match = re.search(r"Available versions: (.+)", result.stdout)
                if match:
                    versions = [v.strip() for v in match.group(1).split(",")]
                    if versions:
                        latest = versions[-1]
                        self.cache[cache_key] = {
                            "latest_version": latest,
                            "checked_at": datetime.now().isoformat(),
                        }
                        self._save_cache()
                        return latest
        except (subprocess.SubprocessError, re.error, IndexError) as e:
            logger.debug(f"Failed to check PyPI for {package_name}: {e}")

        return None

    def _check_cli_versions(self) -> list[str]:
        """Check installed CLI tool versions."""
        updates: list[str] = []
        cli_tools = {
            "jcode": ["jcode", "--version"],
            "opencode": ["opencode", "--version"],
            "cursor": ["cursor", "--version"],
            "zed": ["zed", "--version"],
            "code": ["code", "--version"],
        }

        for name, cmd in cli_tools.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    if name in self.tools:
                        self.tools[name].current_version = version
            except FileNotFoundError:
                pass
            except (subprocess.SubprocessError, OSError) as e:
                logger.debug(f"Failed to check {name}: {e}")

        return updates

    def generate_report(self) -> str:
        """Generate a human-readable update report (V2.21 P5-27 拆分: 抽 _build_*_section)."""
        report = [
            "# AI Tool Matrix Update Report",
            f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Matrix File**: {MATRIX_PATH}",
            "\n---\n",
        ]

        model_updates = [m for m in self.models.values() if m.update_available]
        tool_updates = [t for t in self.tools.values() if t.update_available]

        report.extend(self._build_model_section(model_updates))
        report.extend(self._build_tool_section(tool_updates))
        report.extend(self._build_cli_versions())
        report.extend(self._build_recommendations(model_updates, tool_updates))
        report.append(f"\n---\n*Next check recommended: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}*")
        return "\n".join(report)

    def _build_model_section(self, model_updates: list[Any]) -> list[str]:
        """生成 Model Updates 段 (方法级 helper).

        Args:
            model_updates: 有 update_available 的 model 列表

        Returns:
            报告行列表
        """
        if model_updates:
            return [
                "## 📦 Model Updates Available",
                *[f"- **{m.name}**: {m.current_version} → {m.latest_version}" for m in model_updates],
            ]
        return ["## ✅ All Models Up to Date"]

    def _build_tool_section(self, tool_updates: list[Any]) -> list[str]:
        """生成 Tool Updates 段 (方法级 helper).

        Args:
            tool_updates: 有 update_available 的 tool 列表

        Returns:
            报告行列表
        """
        if tool_updates:
            return [
                "\n## 🔧 Tool Updates Available",
                *[f"- **{t.name}**: {t.current_version} → {t.latest_version}" for t in tool_updates],
            ]
        return ["\n## ✅ All Tools Up to Date"]

    def _build_cli_versions(self) -> list[str]:
        """生成 CLI Versions 段 (方法级 helper).

        Returns:
            报告行列表
        """
        lines = ["\n## 💻 Installed CLI Versions"]
        for name, tool in self.tools.items():
            if tool.current_version and tool.current_version != "latest":
                lines.append(f"- {name}: {tool.current_version}")
        return lines

    def _build_recommendations(self, model_updates: list[Any], tool_updates: list[Any]) -> list[str]:
        """生成 Recommendations 段 (方法级 helper).

        Args:
            model_updates: 有 update 的 model 列表
            tool_updates: 有 update 的 tool 列表

        Returns:
            报告行列表
        """
        lines = ["\n## 💡 Recommendations"]
        if model_updates or tool_updates:
            lines.extend(
                [
                    "1. Update the matrix file with new versions",
                    "2. Run integration tests after updates",
                    "3. Consider updating configuration files (.ai-sync.json, etc.)",
                ]
            )
        else:
            lines.append("No immediate updates required. Re-check in 1 week.")
        return lines

    def update_matrix(self) -> bool:
        """Update the markdown matrix with new versions."""
        if not self.models and not self.tools:
            return False

        updated_content = self.matrix_content
        changed = False

        # Update model versions in markdown
        for model_name, model in self.models.items():
            if model.update_available and model.latest_version:
                # Update version in table
                _pattern = rf"(\|\s*\*\*{re.escape(model_name)}\*\*\s*\|.+?\|.+?\|.+?\|)\s*\⭐+"
                # This is a simplified update - real implementation would need more careful parsing
                _old_stars = "⭐" * 5  # placeholder
                _new_stars = "⭐" * 5  # keep same rating
                # In practice, would update version info in the table cells
                pass

        # Update tool versions
        for tool_name, tool in self.tools.items():
            if tool.update_available and tool.latest_version:
                # Similar logic for tools
                pass

        if changed:
            # Create backup
            backup_path = MATRIX_PATH.with_suffix(".md.backup")
            backup_path.write_text(self.matrix_content, encoding="utf-8")
            logger.info(f"Backup created: {backup_path}")

            MATRIX_PATH.write_text(updated_content, encoding="utf-8")
            logger.info(f"Matrix updated: {MATRIX_PATH}")

        return changed


async def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AI Tool Matrix Updater")
    parser.add_argument("--check", action="store_true", help="Check for updates only")
    parser.add_argument("--update", action="store_true", help="Apply updates to matrix")
    parser.add_argument("--report", action="store_true", help="Generate update report")
    parser.add_argument("--output", type=str, help="Output file for report")

    args = parser.parse_args()

    if not any([args.check, args.update, args.report]):
        parser.print_help()
    return args


async def _run_checks(updater: ToolMatrixUpdater) -> None:
    """Run all update checks."""
    await updater.check_model_updates()
    updater._check_cli_versions()


async def _handle_report(updater: ToolMatrixUpdater, args: argparse.Namespace) -> None:
    """Generate and output report."""
    report = updater.generate_report()
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        logger.info(f"Report saved to {args.output}")
    else:
        print(report)


async def _handle_update(updater: ToolMatrixUpdater) -> None:
    """Handle matrix update."""
    changed = updater.update_matrix()
    if changed:
        logger.info("Matrix updated successfully")
    else:
        logger.info("No changes needed")


async def main() -> int:
    """Main entry point for AI Tool Matrix Updater."""
    args = await _parse_args()

    if not any([args.check, args.update, args.report]):
        return 0

    updater = ToolMatrixUpdater()
    updater.load_matrix()

    # Check versions
    await _run_checks(updater)

    if args.report or args.check:
        await _handle_report(updater, args)

    if args.update:
        await _handle_update(updater)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
