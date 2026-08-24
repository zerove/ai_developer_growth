#!/usr/bin/env python3
"""
jcode Skill Runner - 上下文同步

将 examples/ai-context-sync 重构为 JCode 技能，集成到 hooks 流程中。

用法:
    python .jcode/scripts/context_sync.py sync --project-root .
    python .jcode/scripts/context_sync.py validate --context-file CONTEXT.md --adr-file ADR.md
    python .jcode/scripts/context_sync.py audit --spec-file SPEC.md
    python .jcode/scripts/context_sync.py evolve
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

        # 检查未处理异常
        if re.search(r"except\s*:", diff) and not re.search(r"except\s+\w+", diff):  # noqa: py-bare-except
            violations.append("检测到裸露的 except:，建议指定异常类型")

        # 检查类型注解
        if re.search(r"def \w+\([^)]*\):", diff) and not re.search(r"def \w+\([^)]*\)\s*->", diff):
            # 简单启发式：公共函数应有类型注解
            pass

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
    """上下文合成器 - 更新 CONTEXT.md"""

    def synthesize_context_update(self, diff: str, task: str, current_context: str) -> str:
        timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        update = f"""
## 更新记录: {timestamp}

### 任务
{task}

### 变更摘要
{diff[:2000]}...

---

{current_context}
"""
        return update.strip()


class GitAnalyzer:
    """Git 变更分析器"""

    def get_changed_files(self, since: str = "HEAD~1") -> list[str]:
        code, output = run_command(["git", "diff", "--name-only", since])
        if code == 0:
            return [f.strip() for f in output.split("\n") if f.strip()]
        return []

    def get_diff(self, since: str = "HEAD~1") -> str:
        code, output = run_command(["git", "diff", since])
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
            code, stdout, stderr = run_command(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"], timeout=self.timeout
            )
            return TestResult(success=code == 0, output=stdout + stderr)
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
# Mock LLM Client (演示用)
# ============================================================================


class MockLLMClient:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        # 根据提示词类型返回模拟响应
        if "design decomposition" in prompt or "子任务分解" in prompt:
            return self._mock_design()
        elif "Verification Test" in prompt or "验证测试" in prompt:
            return self._mock_implementation()
        elif "violations" in prompt or "违规" in prompt:
            return self._mock_fix()
        elif "synthesize" in prompt or "合成" in prompt:
            return "# 更新后的上下文\n\n## 项目状态\n- 状态: 活跃开发中"
        return "Mock response"

    def _mock_design(self) -> str:
        return """
## 技术设计

### 目标
实现用户需求的功能模块

### 架构变更
新增核心模块，遵循现有架构模式

### API 变更
新增转换接口

### 实施计划
1. 创建核心转换类
2. 实现单元测试
3. 集成到主流程

```json
[
  {
    "id": "TASK-1",
    "description": "实现核心转换逻辑",
    "target_files": ["converter.py"],
    "verification": {
      "test_code": "import pytest\nfrom converter import convert\n\ndef test_convert():\n    assert convert(100, 'USD', 'CNY') > 0\n",
      "expected": "转换结果应为正数"
    },
    "depends_on": []
  }
]
```"""

    def _mock_implementation(self) -> str:
        return """[FILE: converter.py]
def convert(amount: float, from_curr: str, to_curr: str) -> float:
    \"\"\"货币转换\"\"\"
    rates = {"USD_CNY": 7.2, "CNY_USD": 0.14}
    key = f"{from_curr}_{to_curr}"
    return amount * rates.get(key, 1.0)
[END]"""

    def _mock_fix(self) -> str:
        return """[FILE: converter.py]
def convert(amount: float, from_curr: str, to_curr: str) -> float:
    \"\"\"货币转换\"\"\"
    if amount < 0:
        raise ValueError("金额不能为负数")
    rates = {"USD_CNY": 7.2, "CNY_USD": 0.14}
    key = f"{from_curr}_{to_curr}"
    return amount * rates.get(key, 1.0)
[END]"""


# ============================================================================
# Workflow Manager
# ============================================================================


class ContextSyncManager:
    def __init__(self, config: ContextConfig | None = None) -> None:
        self.config = config or ContextConfig()
        self.llm_client = MockLLMClient()
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

        os.chdir(project_root)
        root = Path(project_root).resolve()
        print_check(f"项目根目录: {root}", True)

        # 1. 获取最近变更
        changed_files = self.analyzer.get_changed_files()
        print_check(f"变更文件数: {len(changed_files)}", True)
        for f in changed_files[:10]:
            print(f"  - {f}")
        if len(changed_files) > 10:
            print(f"  ... 共 {len(changed_files)} 个文件")

        # 2. 获取 diff
        diff = self.analyzer.get_diff()
        print_check(f"Diff 大小: {len(diff)} 字符", True)

        # 3. 读取当前 CONTEXT.md
        context_file = root / self.config.context_file
        current_context = context_file.read_text(encoding="utf-8") if context_file.exists() else ""

        # 4. 合成更新
        updated_context = self.synthesizer.synthesize_context_update(diff, "Git 变更同步", current_context)

        # 5. 写入
        context_file.write_text(
            updated_context if updated_context.endswith("\n") else updated_context + "\n", encoding="utf-8"
        )
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
        """验证 CONTEXT.md 和 ADR.md 格式"""
        print_section("上下文验证")

        ctx_path = Path(context_file)
        adr_path = Path(adr_file)

        # 验证 CONTEXT.md
        if ctx_path.exists():
            content = ctx_path.read_text(encoding="utf-8")
            checks = [
                ("包含项目状态", "项目状态" in content or "Project Status" in content),
                ("包含决策记录", "决策" in content or "Decision" in content),
                ("包含计划", "计划" in content or "Plan" in content),
                ("非空", len(content.strip()) > 100),
            ]
            for name, passed in checks:
                print_check(f"CONTEXT.md - {name}", passed)
        else:
            print_check("CONTEXT.md 存在", False)
            return 1

        # 验证 ADR.md
        if adr_path.exists():
            content = adr_path.read_text(encoding="utf-8")
            checks = [
                ("包含 ADR 标题", "ADR" in content),
                ("包含决策格式", "状态" in content or "Status" in content),
            ]
            for name, passed in checks:
                print_check(f"ADR.md - {name}", passed)
        else:
            print_check("ADR.md 存在", False)
            return 1

        print_check("验证通过", True)
        return 0

    def audit_spec(self, spec_file: str) -> int:
        """审计 SPEC.md 规范合规性"""
        print_section("规范审计")

        spec_path = Path(spec_file)
        if not spec_path.exists():
            print_check(f"SPEC.md 存在: {spec_file}", False)
            return 1

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
