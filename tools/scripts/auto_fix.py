"""
Auto-fix 编排器

核心功能:
- 安全自动修复 (仅格式化、导入排序、无副作用重构)
- 半自动修复 (提供 diff、需人工确认)
- 批量 PR 生成 (按规则/目录分组)
- 修复后回归测试触发
- 修复策略配置
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


from tools.scripts.rules_engine.models import CheckResult, Issue  # noqa: E402
from tools.scripts.rules_engine.regex_cache import guard_pattern  # noqa: E402

logger = logging.getLogger(__name__)


class FixStrategy(str, Enum):
    """修复策略"""

    AUTO = "auto"  # 完全自动应用
    INTERACTIVE = "interactive"  # 交互式确认
    DRY_RUN = "dry_run"  # 仅预览
    BATCH_PR = "batch_pr"  # 生成批量 PR


class FixSafetyLevel(str, Enum):
    """修复安全级别"""

    SAFE = "safe"  # 无副作用: 格式化、导入排序、空行调整
    LOW_RISK = "low_risk"  # 低风险: 未使用导入移除、类型注解添加
    MEDIUM_RISK = "medium_risk"  # 中风险: 重命名、重构、逻辑等价变换
    HIGH_RISK = "high_risk"  # 高风险: 逻辑修复、算法变更


@dataclass
class FixAction:
    """单个修复动作"""

    rule_id: str
    file: str
    line: int
    column: int
    original: str
    replacement: str
    safety_level: FixSafetyLevel = FixSafetyLevel.SAFE
    description: str = ""
    confidence: float = 1.0  # 0-1
    errors: list[str] = field(default_factory=list)


@dataclass
class FixResult:
    """修复结果"""

    file: str
    applied: list[FixAction] = field(default_factory=list)
    skipped: list[FixAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    diff: str = ""


@dataclass
class FixPlan:
    """修复计划"""

    actions: list[FixAction] = field(default_factory=list)
    strategy: FixStrategy = FixStrategy.AUTO
    safety_level: FixSafetyLevel = FixSafetyLevel.SAFE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def filter_by_safety(self, max_level: FixSafetyLevel) -> FixPlan:
        """按安全级别过滤"""
        level_order = {
            FixSafetyLevel.SAFE: 0,
            FixSafetyLevel.LOW_RISK: 1,
            FixSafetyLevel.MEDIUM_RISK: 2,
            FixSafetyLevel.HIGH_RISK: 3,
        }
        max_order = level_order[max_level]
        filtered = [a for a in self.actions if level_order.get(a.safety_level, 99) <= max_order]
        return FixPlan(
            actions=filtered,
            strategy=self.strategy,
            safety_level=max_level,
            metadata=self.metadata,
        )

    def group_by_file(self) -> dict[str, list[FixAction]]:
        """按文件分组"""
        groups: dict[str, list[FixAction]] = {}
        for action in self.actions:
            groups.setdefault(action.file, []).append(action)
        return groups

    def group_by_rule(self) -> dict[str, list[FixAction]]:
        """按规则分组"""
        groups: dict[str, list[FixAction]] = {}
        for action in self.actions:
            groups.setdefault(action.rule_id, []).append(action)
        return groups


class AutoFixOrchestrator:
    """自动修复编排器"""

    def __init__(
        self,
        strategy: FixStrategy = FixStrategy.AUTO,
        safety_level: FixSafetyLevel = FixSafetyLevel.SAFE,
        max_fixes_per_file: int = 50,
        backup: bool = True,
        run_tests_after: bool = False,
        test_command: str | None = None,
    ):
        self.strategy = strategy
        self.safety_level = safety_level
        self.max_fixes_per_file = max_fixes_per_file
        self.backup = backup
        self.run_tests_after = run_tests_after
        self.test_command = test_command or "pytest -x -q"
        self.fix_providers: dict[str, FixProvider] = {}

    def register_provider(self, provider: FixProvider) -> None:
        """注册修复提供者"""
        self.fix_providers[provider.name] = provider

    def create_plan(
        self,
        results: list[CheckResult],
        config: dict[str, Any] | None = None,
    ) -> FixPlan:
        """从检查结果创建修复计划"""
        all_actions = []

        for result in results:
            for issue in result.issues:
                # 尝试所有提供者
                for provider in self.fix_providers.values():
                    actions = provider.generate_fixes(issue, result.file, config)
                    all_actions.extend(actions)

        # 过滤安全级别
        plan = FixPlan(
            actions=all_actions,
            strategy=self.strategy,
            safety_level=self.safety_level,
        ).filter_by_safety(self.safety_level)

        # 限制每文件修复数
        grouped = plan.group_by_file()
        limited_actions = []
        for file_actions in grouped.values():
            limited_actions.extend(file_actions[: self.max_fixes_per_file])

        return FixPlan(
            actions=limited_actions,
            strategy=self.strategy,
            safety_level=self.safety_level,
            metadata={"total_actions": len(all_actions), "limited": len(limited_actions)},
        )

    def execute_plan(self, plan: FixPlan, project_root: Path) -> list[FixResult]:
        """执行修复计划"""
        results = []

        if self.strategy == FixStrategy.DRY_RUN:
            # 仅预览
            for file_path, actions in plan.group_by_file().items():
                # 找到第一个 action 的 provider 来生成预览
                first_action = actions[0]
                provider = self._find_provider_for_action(first_action)
                if provider:
                    diff = provider._generate_diff(
                        (project_root / file_path).read_text() if (project_root / file_path).exists() else "",
                        "",  # 占位符
                        file_path,
                    )
                else:
                    diff = self._generate_diff(project_root / file_path, actions)
                results.append(
                    FixResult(
                        file=file_path,
                        applied=[],
                        skipped=actions,
                        diff=diff,
                    )
                )
            return results

        if self.strategy == FixStrategy.INTERACTIVE:
            # 交互式确认
            return self._execute_interactive(plan, project_root)

        if self.strategy == FixStrategy.BATCH_PR:
            # 批量 PR 模式
            return self._execute_batch_pr(plan, project_root)

        # 自动模式
        return self._execute_auto(plan, project_root)

    def _find_provider_for_action(self, action: FixAction) -> FixProvider | None:
        """根据 action 找到对应的 provider"""
        for provider in self.fix_providers.values():
            # 简单匹配：检查 provider 是否能处理这个 rule_id
            test_issue = Issue(
                rule_id=action.rule_id,
                severity="error",
                category="style",
                file=action.file,
                line=action.line,
                message="",
                column=action.column,
            )
            fixes = provider.generate_fixes(test_issue, action.file, None)
            if fixes:
                return provider
        return None

    def _resolve_file_path(self, file_path: str, project_root: Path) -> Path | None:
        """解析相对/绝对路径; 文件不存在返回 None。"""
        fp = Path(file_path)
        full_path = fp if fp.is_absolute() else project_root / fp
        return full_path if full_path.exists() else None

    def _group_actions_by_provider(self, actions: list[FixAction]) -> dict[FixProvider | None, list[FixAction]]:
        """按 provider 分组修复动作; 无 provider 归入 None 组 (默认行替换)。"""
        grouped: dict[FixProvider | None, list[FixAction]] = {}
        for action in actions:
            provider = self._find_provider_for_action(action)
            grouped.setdefault(provider, []).append(action)
        return grouped

    def _apply_line_replacements(
        self,
        full_path: Path,
        file_path: str,
        actions: list[FixAction],
        applied: list[FixAction],
        skipped: list[FixAction],
    ) -> str:
        """默认修复方式: 逐行替换 (倒序避免行号偏移), 返回 diff。"""
        content = full_path.read_text()
        lines = content.splitlines(keepends=True)
        for action in sorted(actions, key=lambda a: a.line, reverse=True):
            if not 0 < action.line <= len(lines):
                skipped.append(action)
                action.errors.append(f"Line out of range: {action.line}")
                continue
            line_idx = action.line - 1
            if lines[line_idx].rstrip("\n\r") == action.original.rstrip("\n\r"):
                lines[line_idx] = action.replacement + ("\n" if action.original.endswith("\n") else "")
                applied.append(action)
            else:
                skipped.append(action)
                action.errors.append(f"Line content mismatch at {file_path}:{action.line}")
        new_content = "".join(lines)
        full_path.write_text(new_content)
        if applied:
            return self._generate_diff_from_content(content, new_content, file_path)
        return ""

    def _apply_via_provider(
        self,
        provider: FixProvider,
        full_path: Path,
        file_path: str,
        actions: list[FixAction],
        applied: list[FixAction],
        skipped: list[FixAction],
        errors: list[str],
        project_root: Path,
    ) -> str:
        """provider 方式修复, 返回 diff。"""
        if self.backup:
            backup_path = full_path.with_suffix(full_path.suffix + ".bak")
            backup_path.write_text(full_path.read_text())
        result = provider.apply_fixes(file_path, actions, project_root)
        applied.extend(result.applied)
        skipped.extend(result.skipped)
        errors.extend(result.errors)
        return result.diff or ""

    def _process_single_file(self, file_path: str, actions: list[FixAction], project_root: Path) -> FixResult:
        """处理单个文件的全部修复动作。"""
        full_path = self._resolve_file_path(file_path, project_root)
        if full_path is None:
            return FixResult(file=file_path, errors=[f"File not found: {file_path}"])

        applied: list[FixAction] = []
        skipped: list[FixAction] = []
        errors: list[str] = []
        diff = ""

        for provider, provider_actions in self._group_actions_by_provider(actions).items():
            if provider is None:
                diff = self._apply_line_replacements(full_path, file_path, provider_actions, applied, skipped) or diff
            else:
                d = self._apply_via_provider(
                    provider, full_path, file_path, provider_actions, applied, skipped, errors, project_root
                )
                diff = d or diff

        return FixResult(file=file_path, applied=applied, skipped=skipped, errors=errors, diff=diff)

    def _execute_auto(self, plan: FixPlan, project_root: Path) -> list[FixResult]:
        """自动执行修复 - 按 provider 分组执行"""
        results = [
            self._process_single_file(file_path, actions, project_root)
            for file_path, actions in plan.group_by_file().items()
        ]

        # 运行测试
        if self.run_tests_after and results:
            self._run_regression_tests(project_root)

        return results

    def _execute_interactive(self, plan: FixPlan, project_root: Path) -> list[FixResult]:
        """交互式执行"""
        results = []
        grouped = plan.group_by_file()

        print(f"\n📋 发现 {len(plan.actions)} 个可修复问题，分布在 {len(grouped)} 个文件中")
        print("安全级别:", self.safety_level.value)
        print()

        for file_path, actions in grouped.items():
            full_path = project_root / file_path
            if not full_path.exists():
                continue

            diff = self._generate_diff(full_path, actions)
            print(f"\n📄 {file_path} ({len(actions)} fixes):")
            print(diff[:500] + ("..." if len(diff) > 500 else ""))

            # 实际应用中这里应该等待用户输入
            # 简化版：自动应用安全级别内的
            if self.safety_level in (FixSafetyLevel.SAFE, FixSafetyLevel.LOW_RISK):
                print("  -> 自动应用 (安全级别)")
                auto_results = self._execute_auto(
                    FixPlan(actions=actions, strategy=FixStrategy.AUTO, safety_level=self.safety_level), project_root
                )
                results.extend(auto_results)
            else:
                print("  -> 跳过 (需人工确认)")
                results.append(FixResult(file=file_path, skipped=actions, diff=diff))

        return results

    def _execute_batch_pr(self, plan: FixPlan, project_root: Path) -> list[FixResult]:
        """批量 PR 模式：按规则/目录分组生成 PR"""
        results = []
        grouped_by_rule = plan.group_by_rule()

        for rule_id, actions in grouped_by_rule.items():
            # 每个规则生成一个 PR 分支
            branch_name = f"fix/{rule_id.lower().replace(':', '-')}-{datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y%m%d-%H%M%S')}"

            # 这里应该调用 git 创建分支、应用修复、提交、推送
            # 简化版：只记录计划
            print(f"📦 规则 {rule_id}: 将生成 PR 分支 {branch_name} ({len(actions)} 个修复)")

            for action in actions:
                results.append(
                    FixResult(
                        file=action.file,
                        applied=[action],
                        diff=f"# Planned for PR: {branch_name}\n{action.original} -> {action.replacement}",
                    )
                )

        return results

    def _generate_diff(self, file_path: Path, actions: list[FixAction]) -> str:
        """生成文件修复 diff"""
        if not file_path.exists():
            return f"# File not found: {file_path}"

        content = file_path.read_text()
        lines = content.splitlines(keepends=True)

        for action in sorted(actions, key=lambda a: a.line, reverse=True):
            if 0 < action.line <= len(lines):
                line_idx = action.line - 1
                lines[line_idx] = action.replacement + ("\n" if action.original.endswith("\n") else "")

        new_content = "".join(lines)
        return self._generate_diff_from_content(content, new_content, file_path.name)

    def _generate_diff_from_content(self, original: str, modified: str, file_name: str) -> str:
        """生成 unified diff"""
        import difflib

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
        )
        return "".join(diff)

    def _run_regression_tests(self, project_root: Path) -> None:
        """运行回归测试"""
        try:
            result = subprocess.run(
                self.test_command.split(),
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.warning(f"Regression tests failed: {result.stdout}")
            else:
                logger.info("✅ Regression tests passed")
        except subprocess.TimeoutExpired:
            logger.warning("Regression tests timed out")
        except Exception as e:
            logger.warning(f"Regression tests error: {e}")


class FixProvider:
    """修复提供者基类"""

    def __init__(self, name: str, safety_level: FixSafetyLevel = FixSafetyLevel.SAFE):
        self.name = name
        self.safety_level = safety_level
        self.use_external_tool = False  # 是否需要调用外部工具
        self.tool_command: list[str] | None = None  # 工具命令

    def generate_fixes(
        self,
        issue: Issue,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> list[FixAction]:
        """生成修复动作 (子类实现)"""
        raise NotImplementedError

    def apply_fixes(self, file_path: str, actions: list[FixAction], project_root: Path) -> FixResult:
        """应用修复 (默认实现：直接替换行内容)"""
        full_path = project_root / file_path
        if not full_path.exists():
            return FixResult(file=file_path, errors=[f"File not found: {file_path}"])

        content = full_path.read_text()
        lines = content.splitlines(keepends=True)
        applied = []
        skipped = []

        for action in sorted(actions, key=lambda a: a.line, reverse=True):
            if 0 < action.line <= len(lines):
                line_idx = action.line - 1
                if lines[line_idx].rstrip("\n\r") == action.original.rstrip("\n\r"):
                    lines[line_idx] = action.replacement + ("\n" if action.original.endswith("\n") else "")
                    applied.append(action)
                else:
                    skipped.append(action)
            else:
                skipped.append(action)

        new_content = "".join(lines)
        diff = self._generate_diff(content, new_content, file_path)
        full_path.write_text(new_content)

        return FixResult(
            file=file_path,
            applied=applied,
            skipped=skipped,
            diff=diff,
        )

    def _generate_diff(self, original: str, modified: str, file_name: str) -> str:
        import difflib

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
        )
        return "".join(diff)


class RegexFixProvider(FixProvider):
    """基于 fix_replacement 正则的通用修复提供者"""

    def __init__(
        self,
        name: str,
        safety_level: FixSafetyLevel = FixSafetyLevel.SAFE,
        rules: dict[str, dict[str, Any]] | None = None,
    ):
        super().__init__(name, safety_level)
        # FIX_RULES: rule_id -> {pattern, replacement, language}
        # P1-2 重构: 支持批量文件级 re.subn
        self.rules: dict[str, dict[str, Any]] = rules or {}

    # ── I-01 契约收敛 ─────────────────────────────────────────
    #
    # 历史行为把 ``issue.rule_id`` 当正则用 —— rule_id 是**标识符**而非 pattern,
    # 于是"检测用的正则"与"修复用的正则"根本不是一回事, 修复可能落到行内
    # 与问题无关的位置 (旧实现还会把整行所有匹配一并改写)。
    #
    # 收敛后的契约:
    #   1. pattern 优先取注册规则自身的 pattern (与文件级 apply_rules 同源);
    #   2. 规则 pattern 按 ``issue.column`` 精确锚定到上报的那一处命中;
    #   3. 只替换这一处匹配 —— 不再对整行所有匹配做替换;
    #   4. 零长匹配不替换 (替换空区间等于在行首凭空插入内容)。
    #
    # 向后兼容: 未注册该 rule_id 时回退到"rule_id 当 pattern"的历史行为,
    # 且回退路径不做列锚定 (rule_id 与上报列之间没有可验证的对应关系)。

    def _resolve_pattern(self, rule_id: str) -> tuple[str, bool]:
        """解析定位待修复片段所用的正则 pattern。

        Returns:
            (pattern, 是否来自注册规则)。来自注册规则时 pattern 是规则检测
            所用的那个正则, 可与 issue.column 对齐; 否则为历史回退路径。
        """
        info = self.rules.get(rule_id)
        if isinstance(info, dict):
            pattern = info.get("pattern")
            if isinstance(pattern, str) and pattern:
                return pattern, True
        return rule_id.replace(":", r"\:"), False

    @staticmethod
    def _select_match(compiled: re.Pattern[str], line: str, column: int) -> re.Match[str] | None:
        """选出待替换的匹配。

        - ``column > 0``（规则检测给出的 1-based 命中列）→ 只接受恰好命中该列
          的匹配, 保证"替换的就是上报的那一处"; 找不到则放弃修复。
        - ``column <= 0``（列信息不可用）→ 取第一个匹配。
        - 零长匹配一律跳过: 替换空区间等于凭空插入内容。
        """
        if column > 0:
            for candidate in compiled.finditer(line):
                if candidate.start() + 1 == column and candidate.end() > candidate.start():
                    return candidate
            return None
        first = compiled.search(line)
        if first is None or first.end() == first.start():
            return None
        return first

    def _resolve_match(self, issue: Issue, line: str) -> re.Match[str] | None:
        """解析 pattern 并选出待替换的匹配; pattern 不可信或无效时返回 None。"""
        pattern, from_rule = self._resolve_pattern(issue.rule_id)

        # pattern 与 fix_replacement 均来自规则配置 (PR 场景由外部贡献者控制),
        # 而 line 是被修复的源码行 —— 三者都不可信。且此处结果会**写回文件**,
        # 挂死代价高于只读检查。
        context = f"auto_fix/rule_pattern#{issue.rule_id}" if from_rule else "auto_fix/rule_id"
        if guard_pattern(pattern, context):
            return None
        try:
            compiled = re.compile(pattern)
        except re.error:
            logger.warning(f"Regex fix failed for {issue.rule_id}: invalid regex pattern")
            return None
        return self._select_match(compiled, line, issue.column if from_rule else 0)

    def _build_action(self, issue: Issue, file_path: str, original_line: str, fixed_line: str) -> FixAction:
        """构造本次修复对应的 FixAction。"""
        return FixAction(
            rule_id=issue.rule_id,
            file=file_path,
            line=issue.line,
            column=issue.column,
            original=original_line.rstrip("\n\r"),
            replacement=fixed_line.rstrip("\n\r"),
            safety_level=self.safety_level,
            description=issue.fix_hint or f"Auto-fix for {issue.rule_id}",
            confidence=0.8,
        )

    def generate_fixes(
        self,
        issue: Issue,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> list[FixAction]:
        if not issue.fix_replacement:
            return []

        # 读取文件获取原始行内容
        try:
            full_path = Path(file_path)
            if not full_path.exists():
                return []

            lines = full_path.read_text().splitlines(keepends=True)
            if not (0 < issue.line <= len(lines)):
                return []
            original_line = lines[issue.line - 1]

            match = self._resolve_match(issue, original_line)
            if match is None:
                return []
            try:
                replacement_text = match.expand(issue.fix_replacement)
            except re.error:
                logger.warning(f"Regex fix failed for {issue.rule_id}: invalid replacement template")
                return []

            fixed_line = original_line[: match.start()] + replacement_text + original_line[match.end() :]
            if fixed_line == original_line:
                return []
            return [self._build_action(issue, file_path, original_line, fixed_line)]
        except Exception as e:
            logger.warning(f"Regex fix failed for {issue.rule_id}: {e}")

        return []

    def apply_rules(self, file_path: str) -> list[FixAction]:
        """P1-2 重构入口 (V2.21 P5-16 拆分: 抽 _apply_single_rule + _write_if_changed).

        对文件全文应用 self.rules 的 re.subn, 返回 FixAction 列表.
        """

        try:
            full_path = Path(file_path)
            if not full_path.exists():
                return []

            content = full_path.read_text(encoding="utf-8")
            actions, content = self._apply_all_rules(content, file_path)
            self._write_if_changed(full_path, content, bool(actions))
        except Exception as e:  # noqa: BLE001 - 单文件正则修复失败不能中断整批，交由调用方看空结果
            logger.warning(f"Regex apply_rules failed for {file_path}: {e}")
            return []
        return actions

    def _apply_all_rules(self, content: str, file_path: str) -> tuple[list[FixAction], str]:
        """遍历 self.rules, 对 content 应用每条 re.subn 规则.

        Args:
            content: 文件原始内容
            file_path: 文件路径 (FixAction 记录用)

        Returns:
            (actions, new_content) 元组
        """
        import re

        actions: list[FixAction] = []
        for rule_id, info in self.rules.items():
            pattern = info.get("pattern")
            replacement = info.get("replacement")
            if not pattern or replacement is None:
                continue
            if guard_pattern(pattern, f"auto_fix/apply_rules/{rule_id}"):
                continue
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0 and new_content != content:
                actions.append(
                    FixAction(
                        rule_id=rule_id,
                        file=file_path,
                        line=1,
                        column=1,
                        original=content[:120] + "..." if len(content) > 120 else content,
                        replacement=new_content[:120] + "..." if len(new_content) > 120 else new_content,
                        safety_level=self.safety_level,
                        description=f"Regex fix {rule_id} applied {count} times",
                        confidence=0.9,
                    )
                )
                content = new_content
        return actions, content

    def _write_if_changed(self, full_path: Path, content: str, changed: bool) -> None:
        """如果有 fix action, 写回文件 (模块级 helper).

        Args:
            full_path: 文件完整路径
            content: 替换后内容
            changed: 是否有变化 (actions 非空)
        """
        if changed:
            full_path.write_text(content, encoding="utf-8")


class ToolBasedFixProvider(FixProvider):
    """基于外部工具的修复提供者 (ruff, isort, autoflake 等)"""

    def __init__(self, name: str, safety_level: FixSafetyLevel, tool_command: list[str]):
        super().__init__(name, safety_level)
        self.use_external_tool = True
        self.tool_command: list[str] = tool_command

    def generate_fixes(
        self,
        issue: Issue,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> list[FixAction]:
        # 返回标记，实际修复由 apply_fixes 通过运行工具完成
        return [
            FixAction(
                rule_id=issue.rule_id,
                file=file_path,
                line=issue.line,
                column=issue.column,
                original="",  # 占位符，实际由工具处理
                replacement="",  # 占位符
                safety_level=self.safety_level,
                description=f"{self.name} auto-fix for {issue.rule_id}",
                confidence=0.9,
            )
        ]

    def _run_tool(self, full_path: Path) -> tuple[bool, str]:
        """运行外部工具; 返回 (是否成功, 错误消息)。"""
        import subprocess

        cmd = self.tool_command + [str(full_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False, "Tool timed out"
        except Exception as e:  # noqa: BLE001 - 工具异常统一转为错误消息
            return False, f"Tool error: {e}"

        if result.returncode != 0 and "error" in result.stderr.lower():
            return False, f"Tool failed: {result.stderr}"
        return True, ""

    def apply_fixes(self, file_path: str, actions: list[FixAction], project_root: Path) -> FixResult:
        """运行外部工具修复文件"""
        full_path = project_root / file_path
        if not full_path.exists():
            return FixResult(file=file_path, errors=[f"File not found: {file_path}"])

        # 备份
        backup_path = full_path.with_suffix(full_path.suffix + ".bak")
        backup_path.write_text(full_path.read_text())

        ok, error = self._run_tool(full_path)
        if not ok:
            # 恢复备份
            full_path.write_text(backup_path.read_text())
            return FixResult(file=file_path, applied=[], skipped=actions, errors=[error])

        # 生成 diff
        original_content = backup_path.read_text()
        new_content = full_path.read_text()
        diff = self._generate_diff(original_content, new_content, file_path)

        return FixResult(file=file_path, applied=actions, skipped=[], diff=diff)


class RuffFixProvider(ToolBasedFixProvider):
    """Ruff 修复提供者 (格式化、导入排序、安全重构)"""

    def __init__(self) -> None:
        super().__init__("ruff", FixSafetyLevel.SAFE, [sys.executable, "-m", "ruff", "check", "--fix"])

    def generate_fixes(
        self,
        issue: Issue,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> list[FixAction]:
        if issue.rule_id.startswith(
            ("E", "W", "F", "I", "UP", "B", "C4", "SIM", "TID", "PTH", "ERA", "RET", "ARG", "PL", "TRY", "NPY", "RUF")
        ):
            return [
                FixAction(
                    rule_id=issue.rule_id,
                    file=file_path,
                    line=issue.line,
                    column=issue.column,
                    original="",
                    replacement="",
                    safety_level=FixSafetyLevel.SAFE,
                    description=f"Ruff auto-fix for {issue.rule_id}",
                    confidence=0.9,
                )
            ]
        return []


class IsortFixProvider(ToolBasedFixProvider):
    """isort 导入排序修复"""

    def __init__(self) -> None:
        super().__init__("isort", FixSafetyLevel.SAFE, ["isort"])

    def generate_fixes(
        self,
        issue: Issue,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> list[FixAction]:
        if issue.rule_id in ("I001", "I002", "I003", "I004", "I005"):
            return [
                FixAction(
                    rule_id=issue.rule_id,
                    file=file_path,
                    line=issue.line,
                    column=issue.column,
                    original="",
                    replacement="",
                    safety_level=FixSafetyLevel.SAFE,
                    description="Sort imports with isort",
                    confidence=0.95,
                )
            ]
        return []


class AutoFlakeFixProvider(ToolBasedFixProvider):
    """autoflake 移除未使用导入"""

    def __init__(self) -> None:
        super().__init__(
            "autoflake", FixSafetyLevel.LOW_RISK, ["autoflake", "--remove-all-unused-imports", "--in-place"]
        )

    def generate_fixes(
        self,
        issue: Issue,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> list[FixAction]:
        if issue.rule_id in ("F401", "F811", "F841"):
            return [
                FixAction(
                    rule_id=issue.rule_id,
                    file=file_path,
                    line=issue.line,
                    column=issue.column,
                    original="",
                    replacement="",
                    safety_level=FixSafetyLevel.LOW_RISK,
                    description="Remove unused imports with autoflake",
                    confidence=0.85,
                )
            ]
        return []


def create_default_orchestrator() -> AutoFixOrchestrator:
    """创建默认编排器并注册内置提供者"""
    orchestrator = AutoFixOrchestrator()
    orchestrator.register_provider(RegexFixProvider("regex", FixSafetyLevel.SAFE))
    orchestrator.register_provider(RuffFixProvider())
    orchestrator.register_provider(IsortFixProvider())
    orchestrator.register_provider(AutoFlakeFixProvider())
    return orchestrator


def run_auto_fix(
    results: list[CheckResult],
    project_root: Path,
    strategy: FixStrategy = FixStrategy.AUTO,
    safety_level: FixSafetyLevel = FixSafetyLevel.SAFE,
    config: dict[str, Any] | None = None,
) -> list[FixResult]:
    """便捷函数: 运行自动修复"""
    orchestrator = create_default_orchestrator()
    orchestrator.strategy = strategy
    orchestrator.safety_level = safety_level

    plan = orchestrator.create_plan(results, config)
    return orchestrator.execute_plan(plan, project_root)
