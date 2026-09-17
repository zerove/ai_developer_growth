"""增强后的 PatternLearner — 从代码库中学习团队规范。

之前: 简单聚合 Issue 频率。
之后: 分析代码库中的命名模式、错误处理风格、注释风格，
      自动生成 .adg/rules.yml 自定义规则建议。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.checker import check_directory
from tools.scripts.rules_engine.models import Issue


def _classify_function_name(name: str) -> str | None:
    """将函数名分类为 snake_case / camelCase, 跳过 dunder 与 self。

    Phase 36c cc 拆分: 从 PatternLearner._collect_function_names 抽出。
    """
    if name.startswith("__") or name == "self":
        return None
    if name[0].islower() and "_" in name:
        return "snake_case"
    if name[0].islower() and name[0].isalpha():
        return "camelCase"
    return None


class PatternLearner:
    """Learns common issue patterns and team coding norms from a codebase."""

    MIN_OCCURRENCES = 3

    def learn_from_directory(self, project_path: Path) -> list[dict[str, Any]]:
        """Analyze codebase and suggest team-specific rules.

        Returns both issue-based patterns AND norm-based suggestions.
        """
        suggestions: list[dict[str, Any]] = []

        # 1. 基于 Issue 聚合（原有功能）
        suggestions.extend(self._learn_from_issues(project_path))

        # 2. 基于代码统计的团队规范学习（G7 新增）
        suggestions.extend(self._learn_naming_patterns(project_path))

        suggestions.extend(self._learn_error_handling_style(project_path))

        if not suggestions:
            suggestions.append(
                {
                    "pattern": "no-patterns-found",
                    "message": "未发现明显的高频模式或团队规范",
                    "confidence": 0,
                }
            )

        return suggestions

    def _learn_from_issues(self, project_path: Path) -> list[dict[str, Any]]:
        """Aggregate issues from rules engine and find frequent patterns."""
        # run_linters=False: external linter per-file subprocess spawns dominate
        # runtime for bulk scans; pattern learning only needs internal rule results.
        results = check_directory(project_path, run_linters=False)
        pattern_groups: dict[str, list[Issue]] = {}
        for result in results:
            for issue in result.issues:
                key = issue.message[:60]
                if key not in pattern_groups:
                    pattern_groups[key] = []
                pattern_groups[key].append(issue)

        rules: list[dict[str, Any]] = []
        for msg_key, issues in pattern_groups.items():
            if len(issues) >= self.MIN_OCCURRENCES:
                example = issues[0]
                rules.append(
                    {
                        "type": "issue-pattern",
                        "rule_id": example.rule_id,
                        "pattern": f"Suggested: {example.rule_id}",
                        "message": example.message,
                        "severity": example.severity,
                        "frequency": len(issues),
                        "files": list({i.file for i in issues}),
                        "confidence": min(len(issues) / 10, 1.0),
                        "suggested_action": ("add_to_rules" if len(issues) >= 5 else "monitor"),
                    }
                )
        return rules

    def _learn_naming_patterns(self, project_path: Path) -> list[dict[str, Any]]:
        """分析代码库命名风格，建议团队命名规范。"""
        code_files = [
            f
            for f in list(project_path.rglob("*.py")) + list(project_path.rglob("*.ts"))
            if not any(seg in {"node_modules", ".git", "__pycache__", "build", "dist", ".opencode"} for seg in f.parts)
        ]
        naming_patterns = self._analyze_naming(code_files)

        suggestions = []
        for style, examples in naming_patterns.items():
            if len(examples) >= 3:
                suggestions.append(
                    {
                        "type": "naming-convention",
                        "pattern": style,
                        "message": f"团队使用 {style} 命名风格 (发现 {len(examples)} 处)",
                        "examples": examples[:5],
                        "confidence": min(len(examples) / 20, 0.95),
                        "suggested_action": "add_naming_rule",
                    }
                )
        return suggestions

    def _analyze_naming(self, files: list[Path]) -> dict[str, list[str]]:
        """Analyze naming patterns in code (V2.21 P5-55 拆分: 抽 _collect_function_names + _collect_class_names, 方法级 helper)."""
        patterns: dict[str, list[str]] = {}
        func_pattern = re.compile(r"def (\w+)|\bfn (\w+)|\bfunction (\w+)")
        cls_pattern = re.compile(r"class (\w+)")

        for filepath in files[:200]:  # 限制文件数
            try:
                content = filepath.read_text(encoding="utf-8")
            except OSError:
                continue

            self._collect_function_names(content, func_pattern, patterns)
            self._collect_class_names(content, cls_pattern, patterns)

        return patterns

    def _collect_function_names(
        self, content: str, func_pattern: re.Pattern[str], patterns: dict[str, list[str]]
    ) -> None:
        """从 content 提取 function 名 + 分类 (snake_case/camelCase, 方法级 helper).

        Args:
            content: 文件内容
            func_pattern: 函数名正则
            patterns: 累积目标字典
        """
        for match in func_pattern.finditer(content):
            name = match.group(1) or match.group(2) or match.group(3)
            category = _classify_function_name(name)
            if category is not None:
                patterns.setdefault(category, []).append(name)

    def _collect_class_names(self, content: str, cls_pattern: re.Pattern[str], patterns: dict[str, list[str]]) -> None:
        """从 content 提取 class 名 (PascalCase, 方法级 helper).

        Args:
            content: 文件内容
            cls_pattern: class 名正则
            patterns: 累积目标字典
        """
        for match in cls_pattern.finditer(content):
            name = match.group(1)
            if name[0].isupper():
                patterns.setdefault("PascalCase", []).append(name)

    def _learn_error_handling_style(self, project_path: Path) -> list[dict[str, Any]]:
        """分析错误处理风格。"""
        suggestions = []
        try_files = list(project_path.rglob("*.py"))[:100]
        try_count = 0
        specific_except = 0
        bare_except = 0

        for filepath in try_files:
            try:
                content = filepath.read_text(encoding="utf-8")
                try_count += content.count("except")
                bare_except += len(re.findall(r"except\s*:", content))
                specific_except += len(re.findall(r"except\s+\w+", content))
            except OSError:
                continue

        if try_count > 5:
            specific_ratio = specific_except / try_count if try_count > 0 else 0
            if specific_ratio >= 0.8:
                suggestions.append(
                    {
                        "type": "error-handling-style",
                        "pattern": "specific-exceptions",
                        "message": f"团队使用具体异常类型: {specific_ratio:.0%} 的 except 指定了类型",
                        "confidence": 0.8,
                        "suggested_action": "add_exception_rule",
                    }
                )
        return suggestions


def run_pattern_learning(project_path: Path) -> None:
    """CLI 入口: 分析并打印团队规范建议。"""
    learner = PatternLearner()
    patterns = learner.learn_from_directory(project_path)
    print(f"🔍 AI 分析完成，发现 {len(patterns)} 个模式和建议")
    for p in patterns:
        freq = p.get("frequency", p.get("confidence", 0))
        conf = p.get("confidence", 0)
        ptype = p.get("type", "pattern")
        action = p.get("suggested_action", "")
        if freq > 0 or conf > 0:
            print(f"\n  [{ptype}] {p.get('message', p.get('pattern', ''))}")
            print(f"    置信度: {conf:.0%} | 建议: {action}")
