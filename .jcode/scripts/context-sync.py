#!/usr/bin/env python3
"""
jcode Skill Runner - 上下文同步

将 examples/ai-context-sync 重构为 JCode 技能，集成到 hooks 流程中。

用法:
    python .jcode/scripts/context-sync.py sync --project-root .
    python .jcode/scripts/context-sync.py validate --context-file CONTEXT.md --adr-file ADR.md
    python .jcode/scripts/context-sync.py audit --spec-file SPEC.md
    python .jcode/scripts/context-sync.py evolve
"""

import argparse
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import print_check, print_section, run_command

# CONTEXT.md 中每条同步记录的行首标记。头部识别与窗口裁剪共用同一常量，
# 避免两处字面量漂移导致头部被误判成记录的一部分。
_ENTRY_PREFIX = "## 更新记录:"

# ============================================================================
# Core Components (简化版，保留核心功能)
# ============================================================================


@dataclass
class ContextConfig:
    context_file: str = "CONTEXT.md"
    adr_file: str = "ADR.md"
    spec_file: str = "SPEC.md"
    test_timeout: int = 30
    max_retries: int = 3
    executor_max_workers: int = 4
    # CONTEXT.md 滚动窗口: 保留最近 N 条更新记录（0 = 不限制）。
    # 背景: 更新记录只追加不裁剪，实测膨胀至 6300+ 行/220KB，
    # 持续稀释 AI 上下文质量（改进建议 6）
    max_update_entries: int = 50


class ContextSlicer:
    """上下文切片器 - 提取相关文件内容"""

    def slice(self, files: list[str]) -> str:
        parts = []
        for f in files:
            path = Path(f)
            if path.exists():
                content = path.read_text(encoding="utf-8")
                parts.append(f"=== {f} ===\n{content}")
            else:
                parts.append(f"=== {f} === (不存在)")
        return "\n\n".join(parts) if parts else "(无相关上下文)"


class SpecAuditor:
    """规范审计器 - 检查代码是否符合项目规范"""

    def __init__(self, config: ContextConfig) -> None:
        self.config = config

    def audit(self, diff: str, task: str) -> list[str]:
        violations = []

        # 检查硬编码密钥
        if re.search(r"(password|secret|key|token)\s*=\s*['\"][^'\"]+['\"]", diff, re.IGNORECASE):
            violations.append("检测到可能的硬编码密钥")

        # 检查 eval/exec
        if re.search(r"\b(eval|exec)\s*\(", diff):
            violations.append("检测到 eval/exec 调用，存在代码注入风险")

        # 检查 SQL 注入模式
        if re.search(r"(execute|query)\s*\(.+\+.+\)", diff):
            violations.append("检测到可能的 SQL 拼接，建议使用参数化查询")

        # 检查未指定异常类型的异常捕获
        # 早前条件为 `has_bare and not has_specific`，导致只要 diff 里出现
        # 任意一个 `except ValueError:`，所有裸 `except:` 都会被放过——实测
        # "2 个裸 except + 1 个具体异常" 报 0 项违规。此处意图是"检出裸
        # except 子句"，故只按裸 except 是否存在判定。
        if re.search(r"except\s*:", diff):
            violations.append("检测到未指定异常类型的捕获，建议指定具体异常类型")

        return violations


class ArchitectureGuard:
    """架构防护 - 检查设计偏移"""

    def check_design_drift(self, design_doc: str, task: str) -> str:
        issues = []

        if "TODO" in design_doc or "FIXME" in design_doc:
            issues.append("设计文档包含 TODO/FIXME，需细化")

        if len(design_doc) < 200:
            issues.append("设计文档过于简短，可能缺少关键细节")

        if "JSON" not in design_doc and "sub-task" not in design_doc.lower():
            issues.append("设计文档缺少子任务分解 JSON 格式")

        if not issues:
            return "✅ 无架构偏移风险"
        return "⚠️ 架构偏移检查:\n" + "\n".join(f"  - {i}" for i in issues)


class ContextSynthesizer:
    """上下文合成器 - 更新 CONTEXT.md

    输出守卫（P2-3）: 变更摘要只含结构化统计与文件名列表，
    绝不嵌入 diff 原文，防止 diff 标记行（+/@@/diff --git）污染文档。
    """

    # diff 原文特征前缀: 写入前检测到即拒绝（防回潮）
    _DIFF_MARKERS = ("diff --git ", "@@ ", "+++ b/", "--- a/")

    @classmethod
    def summarize_diff(cls, diff: str, max_files: int = 20) -> str:
        """把 raw diff 压缩为结构化摘要: 文件清单 + 增删行数统计。"""
        files: list[str] = []
        added = removed = 0
        for line in diff.splitlines():
            if line.startswith("diff --git "):
                parts = line.split(" b/", 1)
                files.append(parts[1] if len(parts) == 2 else line)
            elif line.startswith("+++") or line.startswith("---"):
                continue
            elif line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
        summary_lines = [f"- 变更文件 {len(files)} 个 (+{added} / -{removed} 行)"]
        summary_lines.extend(f"  - {f}" for f in files[:max_files])
        if len(files) > max_files:
            summary_lines.append(f"  - ... 等共 {len(files)} 个文件")
        return "\n".join(summary_lines)

    def synthesize_context_update(
        self, diff: str, task: str, current_context: str, max_update_entries: int = 50
    ) -> str:
        timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"{_ENTRY_PREFIX} {timestamp}\n\n### 任务\n{task}\n\n### 变更摘要\n{self.summarize_diff(diff)}"
        self.guard_no_diff_raw(entry)

        header, entries_text = self._split_header_and_entries(current_context)

        # 组装顺序: 固定头部 -> 新记录 -> 历史记录。
        # 头部必须排在所有 '## 更新记录:' 之前。若新记录排在最前，裁剪逻辑会把
        # "新记录 + 头部 + 历史记录" 整段当成"新记录"的正文（记录边界只由下一个
        # '## 更新记录:' 决定），头部因而落入滚动窗口，50 次同步后被静默丢弃 ——
        # 2026-08-23 CONTEXT.md 项目概述/状态就是这样消失的（ADR-061）。
        content = "\n\n".join(p for p in (header, entry, entries_text) if p)

        # 滚动窗口: 只保留最近 N 条更新记录，防止文件无限膨胀
        if max_update_entries > 0:
            content = self._prune_update_entries(content, max_update_entries)

        return content.strip()

    @classmethod
    def guard_no_diff_raw(cls, content: str) -> None:
        """输出守卫: 内容含 diff 原文特征行时抛错，阻断写入。"""
        marker_union = "|".join(re.escape(m) for m in cls._DIFF_MARKERS)
        pat = "^(" + marker_union + ")"
        for line in content.splitlines():
            if re.match(pat, line):
                raise ValueError(f"CONTEXT.md 更新内容混入 diff 原文行: {line[:60]!r}")

    @staticmethod
    def _split_header_and_entries(content: str) -> tuple[str, str]:
        """把 CONTEXT.md 切成 (固定头部, 更新记录区)。

        固定头部指首个 '## 更新记录:' 之前的内容（项目概述 / 状态 / 术语等），
        它必须始终独立于滚动窗口存在，否则窗口裁剪会连同项目上下文一起丢弃。
        """
        lines = content.splitlines()
        first = next((i for i, line in enumerate(lines) if line.startswith(_ENTRY_PREFIX)), None)
        if first is None:
            # 无任何更新记录: 整份都是固定头部
            return content.strip(), ""
        return "\n".join(lines[:first]).strip(), "\n".join(lines[first:]).strip()

    @staticmethod
    def _render(header: str, entries: list[str], pruned: int) -> str:
        """按 [固定头部区, 更新记录区] 组装文档，保证头部永远排在记录之前。"""
        chunks: list[str] = []
        if header:
            chunks.append(header)
        if entries:
            chunks.append("\n\n".join(entries))
        result = "\n\n".join(chunks)
        if not result:
            result = ""
        if pruned > 0:
            result += f"\n\n<!-- 滚动窗口: 已自动裁剪 {pruned} 条旧更新记录 -->\n"
        return result

    @staticmethod
    def _prune_update_entries(content: str, max_entries: int) -> str:
        """按 '## 更新记录:' 标题切分，保留头部说明 + 最近 N 条记录。

        首个更新记录之前的所有内容（项目概述等）视为固定头部原样保留，
        且始终排在更新记录之前 —— 头部不参与窗口裁剪。
        """
        header, entries_text = ContextSynthesizer._split_header_and_entries(content)
        if not entries_text:
            return content  # 无更新记录, 原样返回

        lines = entries_text.splitlines()
        starts = [i for i, line in enumerate(lines) if line.startswith(_ENTRY_PREFIX)]
        entries = []
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            entries.append("\n".join(lines[start:end]).strip("\n"))

        kept = entries[:max_entries]
        pruned = len(entries) - len(kept)
        return ContextSynthesizer._render(header, kept, pruned)


class GitAnalyzer:
    """Git 变更分析器"""

    def get_changed_files(self, since: str = "HEAD~1", cwd: Path | None = None) -> list[str]:
        code, output = run_command(["git", "diff", "--name-only", since], cwd=cwd)
        if code == 0:
            return [f.strip() for f in output.split("\n") if f.strip()]
        return []

    def get_diff(self, since: str = "HEAD~1", cwd: Path | None = None) -> str:
        code, output = run_command(["git", "diff", since], cwd=cwd)
        if code == 0:
            return str(output)
        return ""


class TestRunner:
    """测试运行器"""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def run_test(self, test_code: str, target_files: list[str]) -> "TestResult":
        # 写入临时测试文件
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix="_test.py", delete=False, encoding="utf-8") as f:
            f.write(test_code)
            test_file = f.name

        try:
            code, output = run_command(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"], timeout=self.timeout
            )
            return TestResult(success=code == 0, output=output)
        finally:
            try:
                os.unlink(test_file)
            except OSError:
                pass


@dataclass
class TestResult:
    success: bool
    output: str


class ParallelExecutor:
    """并行执行器"""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def execute(self, tasks: list[dict[str, Any]], worker_fn: Callable[[dict[str, Any]], str]) -> dict[str, str]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {executor.submit(worker_fn, task): task for task in tasks}
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    results[task["id"]] = future.result()
                except Exception as e:
                    results[task["id"]] = f"Error: {e}"
        return results


class SpecificationEvolution:
    """规范演化分析"""

    def analyze_conflicts(self) -> list[dict[str, Any]]:
        # 简化版：返回空列表
        return []


# ============================================================================
# Workflow Manager
# ============================================================================


class ContextSyncManager:
    def __init__(self, config: ContextConfig | None = None) -> None:
        self.config = config or ContextConfig()
        self.analyzer = GitAnalyzer()
        self.slicer = ContextSlicer()
        self.guard = ArchitectureGuard()
        self.auditor = SpecAuditor(self.config)
        self.synthesizer = ContextSynthesizer()
        self.executor = ParallelExecutor(max_workers=self.config.executor_max_workers)
        self.tester = TestRunner(timeout=self.config.test_timeout)
        self.evolution = SpecificationEvolution()

    def sync_context(self, project_root: str = ".") -> int:
        """同步上下文：分析 Git 变更 -> 更新 CONTEXT.md"""
        print_section("上下文同步")

        root = Path(project_root).resolve()
        print_check(f"项目根目录: {root}", True)

        # 1. 获取最近变更
        changed_files = self.analyzer.get_changed_files(cwd=root)
        print_check(f"变更文件数: {len(changed_files)}", True)
        for f in changed_files[:10]:
            print(f"  - {f}")
        if len(changed_files) > 10:
            print(f"  ... 共 {len(changed_files)} 个文件")

        # 2. 获取 diff
        diff = self.analyzer.get_diff(cwd=root)
        print_check(f"Diff 大小: {len(diff)} 字符", True)

        # 3. 读取当前 CONTEXT.md
        context_file = root / self.config.context_file
        current_context = context_file.read_text(encoding="utf-8") if context_file.exists() else ""

        # 4. 合成更新（内嵌输出守卫: 摘要仅结构化信息，不含 diff 原文）
        updated_context = self.synthesizer.synthesize_context_update(
            diff, "Git 变更同步", current_context, max_update_entries=self.config.max_update_entries
        )

        # 5. 写入 (diff 内容可能携带尾随空格, 统一清除避免与
        #    pre-commit trailing-whitespace 钩子形成修改循环)
        cleaned = "\n".join(line.rstrip() for line in updated_context.splitlines())
        context_file.write_text(cleaned if cleaned.endswith("\n") else cleaned + "\n", encoding="utf-8")
        print_check(f"已更新: {context_file}", True)

        # 6. 同步 ADR（如果有架构决策）
        self._sync_adr(root, diff)

        return 0

    def _sync_adr(self, root: Path, diff: str) -> None:
        adr_file = root / self.config.adr_file
        if not adr_file.exists():
            # 创建初始 ADR
            adr_content = """# 架构决策记录 (ADR)

## 格式
- 标题: ADR-XXX: 简短描述
- 状态: 接受/废弃/替代
- 背景: 决策背景
- 决策: 具体决策
- 后果: 正面/负面影响

---

"""
            adr_file.write_text(adr_content if adr_content.endswith("\n") else adr_content + "\n", encoding="utf-8")
            print_check(f"已创建初始 ADR: {adr_file}", True)

    def validate_context(self, context_file: str, adr_file: str) -> int:
        """验证 CONTEXT.md 和 ADR.md 格式。

        返回非 0 表示校验失败。任一子检查失败都必须让整体失败 —— 此前失败只
        打印不返回，退出码恒为 0，使该校验在 hooks / CI 中形同虚设（fail-open）。
        """
        print_section("上下文验证")

        ctx_path = Path(context_file)
        adr_path = Path(adr_file)
        failed: list[str] = []

        def report(scope: str, name: str, passed: bool) -> None:
            print_check(f"{scope} - {name}", passed)
            if not passed:
                failed.append(f"{scope} - {name}")

        # 验证 CONTEXT.md
        if ctx_path.exists():
            content = ctx_path.read_text(encoding="utf-8")
            # 头部区 = 首个 '## 更新记录:' 之前的内容。ADR-061: 头部曾被滚动窗口
            # 静默吞噬，仅靠全文 substring 检查（"项目状态" in content）无法发现 ——
            # 被吞掉的恰好就是含这些词的段落。必须做位置校验而非存在性校验。
            header, entries_text = ContextSynthesizer._split_header_and_entries(content)
            # 有更新记录却没有头部 = CONTEXT.md 已退化为纯同步日志（ADR-061 事故形态）
            header_required = bool(entries_text.strip())
            ctx_checks = [
                ("包含项目状态", "项目状态" in header or "Project Status" in header),
                ("包含决策记录", "决策" in header or "Decision" in header),
                ("包含计划", "计划" in header or "Plan" in header),
                ("固定头部非空", len(header.strip()) > 0 or not header_required),
                ("以一级标题开头", header.lstrip().startswith("# ")),
                ("非空", len(content.strip()) > 100),
            ]
            for name, passed in ctx_checks:
                report("CONTEXT.md", name, passed)
        else:
            report("CONTEXT.md", "存在", False)

        # 验证 ADR.md
        if adr_path.exists():
            content = adr_path.read_text(encoding="utf-8")
            adr_checks = [
                ("包含 ADR 标题", "ADR" in content),
                ("包含决策格式", "状态" in content or "Status" in content),
            ]
            for name, passed in adr_checks:
                report("ADR.md", name, passed)
        else:
            report("ADR.md", "存在", False)

        if failed:
            print_check(f"验证失败: {len(failed)} 项未通过", False)
            for item in failed:
                print(f"    - {item}")
            return 1

        print_check("验证通过", True)
        return 0

    def audit_spec(self, spec_file: str) -> int:
        """审计 SPEC.md 规范合规性"""
        print_section("规范审计")

        spec_path = Path(spec_file)
        if not spec_path.exists():
            print(f"ℹ️  未找到规范文件 {spec_file}，跳过规范审计")
            return 0

        content = spec_path.read_text(encoding="utf-8")
        diff = f"+++ b/{spec_file}\n{content}"

        violations = self.auditor.audit(diff, "规范文档审计")
        passed = len(violations) == 0
        print_check(f"规范合规 ({len(violations)} 个违规)", passed)

        for v in violations:
            print(f"  - {v}")

        return 0 if passed else 1

    def check_evolution(self) -> int:
        """检查规范演化机会"""
        print_section("规范演化分析")

        candidates = self.evolution.analyze_conflicts()
        print_check(f"演化机会: {len(candidates)} 个", True)

        for c in candidates:
            print(f"  - {c}")

        return 0


# ============================================================================
# CLI Entry Points
# ============================================================================


def sync_context(project_root: str, context_file: str, adr_file: str) -> int:
    config = ContextConfig(context_file=context_file, adr_file=adr_file)
    manager = ContextSyncManager(config)
    return manager.sync_context(project_root)


def validate_context(context_file: str, adr_file: str) -> int:
    config = ContextConfig(context_file=context_file, adr_file=adr_file)
    manager = ContextSyncManager(config)
    return manager.validate_context(context_file, adr_file)


def audit_spec(spec_file: str) -> int:
    config = ContextConfig(spec_file=spec_file)
    manager = ContextSyncManager(config)
    return manager.audit_spec(spec_file)


def check_evolution() -> int:
    config = ContextConfig()
    manager = ContextSyncManager(config)
    return manager.check_evolution()


def main() -> None:
    parser = argparse.ArgumentParser(description="上下文同步 - JCode 技能")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync 子命令
    sync_parser = subparsers.add_parser("sync", help="同步上下文 (分析 Git 变更 -> 更新 CONTEXT.md/ADR.md)")
    sync_parser.add_argument("--project-root", default=".", help="项目根目录 (默认: .)")
    sync_parser.add_argument("--context-file", default="CONTEXT.md", help="上下文文件 (默认: CONTEXT.md)")
    sync_parser.add_argument("--adr-file", default="ADR.md", help="ADR 文件 (默认: ADR.md)")

    # validate 子命令
    validate_parser = subparsers.add_parser("validate", help="验证 CONTEXT.md 和 ADR.md 格式")
    validate_parser.add_argument("--context-file", default="CONTEXT.md", help="上下文文件 (默认: CONTEXT.md)")
    validate_parser.add_argument("--adr-file", default="ADR.md", help="ADR 文件 (默认: ADR.md)")

    # audit 子命令
    audit_parser = subparsers.add_parser("audit", help="审计 SPEC.md 规范合规性")
    audit_parser.add_argument("--spec-file", default="SPEC.md", help="规范文件 (默认: SPEC.md)")

    # evolve 子命令
    subparsers.add_parser("evolve", help="检查规范演化机会")

    args = parser.parse_args()

    if args.command == "sync":
        sys.exit(sync_context(args.project_root, args.context_file, args.adr_file))
    elif args.command == "validate":
        sys.exit(validate_context(args.context_file, args.adr_file))
    elif args.command == "audit":
        sys.exit(audit_spec(args.spec_file))
    elif args.command == "evolve":
        sys.exit(check_evolution())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
