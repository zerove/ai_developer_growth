#!/usr/bin/env python3
"""
jcode Skill Runner - 自我修正循环

将 examples/self-correction-loop 重构为 JCode 技能，集成到 hooks 流程中。

用法:
    python .jcode/scripts/self_correction_loop.py run --target <file> --tests <dir>
    python .jcode/scripts/self_correction_loop.py run --target <file> --tests <dir> --max-attempts 3
    python .jcode/scripts/self_correction_loop.py run --target <file> --tests <dir> --runner pytest
    python .jcode/scripts/self_correction_loop.py validate --target <file> --tests <dir>
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from types import ModuleType
from typing import ClassVar

from _common import print_check, print_section

# ============================================================================
# Strategy 定义 (从 examples/self-correction-loop 迁移并适配)
# ============================================================================


class StrategyKind(Enum):
    RETRY = auto()
    PATTERN = auto()
    LLM = auto()
    CUSTOM = auto()


class Strategy(ABC):
    _registry: ClassVar[dict[StrategyKind, type["Strategy"]]] = {}

    def __init__(self) -> None:
        pass

    @classmethod
    def register(cls, kind: StrategyKind) -> type["Strategy"]:
        def decorator(subclass: type["Strategy"]) -> type["Strategy"]:
            cls._registry[kind] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, kind: StrategyKind, **kwargs: object) -> "Strategy":
        factory = cls._registry.get(kind)
        if factory is None:
            raise ValueError(f"No strategy registered for {kind!r}")
        return factory(**kwargs)

    @classmethod
    def available_kinds(cls) -> list[StrategyKind]:
        return list(cls._registry)

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        pass


class StrategyRegistry:
    def __init__(self, strategies: list["Strategy"] | None = None) -> None:
        self._strategies: list[Strategy] = list(strategies) if strategies else []

    def add(self, strategy: "Strategy") -> None:
        self._strategies.append(strategy)

    @property
    def strategies(self) -> list["Strategy"]:
        return list(self._strategies)

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> tuple[str | None, "Strategy | None"]:
        for strategy in self._strategies:
            try:
                result = strategy.fix(
                    code,
                    error_output,
                    file_path,
                    test_dir=test_dir,
                    runner=runner,
                )
            except TypeError:
                result = strategy.fix(code, error_output, file_path)
            if result is not None:
                return result, strategy
        return None, None


def get_registry(
    *,
    enable_retry: bool = True,
    enable_pattern: bool = True,
    enable_llm: bool = True,
    llm_model: str = "gpt-4-turbo-preview",
    **llm_kwargs: object,
) -> StrategyRegistry:
    chain: list[Strategy] = []
    if enable_retry:
        chain.append(RetryStrategy())
    if enable_pattern:
        chain.append(PatternStrategy())
    if enable_llm:
        chain.append(LLMStrategy(model=llm_model, **llm_kwargs))
    return StrategyRegistry(chain)


# ============================================================================
# Pattern Strategy
# ============================================================================


@dataclass(frozen=True)
class Pattern:
    name: str
    error_regex: str
    code_pattern: str
    code_replacement: str
    description: str = ""

    _compiled_error: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled_error", re.compile(self.error_regex, re.IGNORECASE))

    def matches_error(self, error_output: str) -> bool:
        return bool(self._compiled_error.search(error_output))

    def apply(self, code: str) -> str | None:
        new_code, count = re.subn(self.code_pattern, self.code_replacement, code)
        if count > 0:
            return new_code
        return None


_BUILTIN_PATTERNS: list[Pattern] = [
    Pattern(
        name="off-by-one-range",
        error_regex=r"AssertionError",
        code_pattern=r"range\(len\((\w+)\)\s*-\s*1\)",
        code_replacement=r"range(len(\1))",
        description="Fix off-by-one: range(len(x)-1) → range(len(x))",
    ),
    Pattern(
        name="off-by-one-iteration",
        error_regex=r"AssertionError",
        code_pattern=r"for\s+\w+\s+in\s+range\((\w+)\s*-\s*1\):",
        code_replacement=r"for i in range(len(\1)):",
        description="Fix iteration that skips the last element",
    ),
    Pattern(
        name="missing-import",
        error_regex=r"NameError:\s*name '(\w+)' is not defined",
        code_pattern=r"# missing import placeholder",
        code_replacement=r"# (import fix requires LLM strategy)",
        description="Detect undefined name errors (defers to LLM for import insertion)",
    ),
    Pattern(
        name="zero-division-guard",
        error_regex=r"ZeroDivisionError",
        code_pattern=r"(def\s+\w+\([^)]*\):)\s*\n(\s+)(.+)",
        code_replacement=r"\1\n\2if True:  # guard\n\3",
        description="Insert a division-by-zero guard (skeleton – LLM refines)",
    ),
]


@Strategy.register(StrategyKind.PATTERN)
class PatternStrategy(Strategy):
    def __init__(self, patterns: list[Pattern] | None = None) -> None:
        super().__init__()
        self._patterns: list[Pattern] = list(patterns or _BUILTIN_PATTERNS)

    @property
    def name(self) -> str:
        return "pattern"

    @property
    def patterns(self) -> list[Pattern]:
        return list(self._patterns)

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        for pattern in self._patterns:
            if pattern.matches_error(error_output):
                new_code = pattern.apply(code)
                if new_code is not None:
                    return new_code
        return None


# ============================================================================
# Retry Strategy
# ============================================================================


@Strategy.register(StrategyKind.RETRY)
class RetryStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return "retry"

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        return None


# ============================================================================
# LLM Strategy (带 Mock 回退)
# ============================================================================


_openai_mod: ModuleType | None = None


def _get_openai() -> ModuleType:
    global _openai_mod
    if _openai_mod is None:
        try:
            import openai as _mod

            _openai_mod = _mod
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for the LLM strategy.  Install it with: pip install openai"
            ) from exc
    return _openai_mod


def _mock_fix(code: str, error_output: str) -> str | None:
    if "range(len(" in code and re.search(r"-\s*1", code):
        fixed, count = re.subn(r"range\(len\((\w+)\)\s*-\s*1\)", r"range(len(\1))", code)
        if count > 0:
            return fixed
    return None


def _build_prompt(code: str, error_output: str) -> str:
    return (
        "The following Python code is failing a test.\n\n"
        f"Code:\n```\n{code}\n```\n\n"
        f"Error output:\n```\n{error_output}\n```\n\n"
        "Please provide ONLY the corrected Python code.  "
        "No explanations, no markdown fences, no extra text."
    )


@Strategy.register(StrategyKind.LLM)
class LLMStrategy(Strategy):
    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.0,
        max_retries: int = 1,
        **client_kwargs: object,
    ) -> None:
        super().__init__()
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._client_kwargs = client_kwargs

    @property
    def name(self) -> str:
        return "llm"

    def _call_llm(self, prompt: str) -> str | None:
        openai_mod = _get_openai()
        client = openai_mod.OpenAI(**self._client_kwargs)
        response = client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        return content if isinstance(content, str) else None

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        api_key = os.environ.get("OPENAI_API_KEY")

        if _openai_mod is None or api_key is None:
            return _mock_fix(code, error_output)

        prompt = _build_prompt(code, error_output)
        try:
            result: str | None = self._call_llm(prompt)
            return result.strip() if result else None
        except Exception:
            return _mock_fix(code, error_output)


# ============================================================================
# Result Types
# ============================================================================


@dataclass
class CorrectionResult:
    is_success: bool
    attempt: int
    strategy: str
    message: str
    file_path: str
    original_code: str = ""
    fixed_code: str = ""
    test_output: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "is_success": self.is_success,
            "attempt": self.attempt,
            "strategy": self.strategy,
            "message": self.message,
            "file_path": self.file_path,
            "original_code": self.original_code,
            "fixed_code": self.fixed_code,
            "test_output": self.test_output,
            "duration_s": self.duration_s,
        }


def success_result(
    *,
    attempt: int,
    strategy: str,
    file_path: str,
    original_code: str,
    fixed_code: str = "",
    test_output: str = "",
    duration_s: float = 0.0,
) -> CorrectionResult:
    return CorrectionResult(
        is_success=True,
        attempt=attempt,
        strategy=strategy,
        message="Tests passed",
        file_path=file_path,
        original_code=original_code,
        fixed_code=fixed_code,
        test_output=test_output,
        duration_s=duration_s,
    )


def failure_result(
    *,
    attempt: int,
    strategy: str,
    message: str,
    file_path: str,
    original_code: str = "",
    fixed_code: str = "",
    test_output: str = "",
    duration_s: float = 0.0,
) -> CorrectionResult:
    return CorrectionResult(
        is_success=False,
        attempt=attempt,
        strategy=strategy,
        message=message,
        file_path=file_path,
        original_code=original_code,
        fixed_code=fixed_code,
        test_output=test_output,
        duration_s=duration_s,
    )


# ============================================================================
# Correction Loop
# ============================================================================


class FixError(Exception):
    def __init__(self, message: str, file_path: str = "", reason: str = "") -> None:
        super().__init__(message)
        self.file_path = file_path
        self.reason = reason


def run_tests(
    test_dir: str = "tests",
    runner: str = "unittest",
) -> tuple[int, str, str]:
    if runner == "pytest":
        cmd = [sys.executable, "-m", "pytest", test_dir, "-q"]
    else:
        cmd = [sys.executable, "-m", "unittest", "discover", test_dir]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _read_code(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def _write_code(file_path: Path, code: str) -> None:
    try:
        file_path.write_text(code, encoding="utf-8")
    except OSError as exc:
        raise FixError(
            f"Cannot write to {file_path}",
            file_path=str(file_path),
            reason=str(exc),
        ) from exc


class CorrectionLoop:
    def __init__(
        self,
        target_file: str | Path,
        test_dir: str = "tests",
        max_attempts: int = 3,
        runner: str = "unittest",
        registry: StrategyRegistry | None = None,
        on_attempt: Callable[["CorrectionResult"], None] | None = None,
    ) -> None:
        self._target_file = Path(target_file)
        self._test_dir = test_dir
        self._max_attempts = max_attempts
        self._runner = runner
        self._registry = registry or get_registry()
        self._on_attempt = on_attempt
        self._history: list[CorrectionResult] = []

    @property
    def history(self) -> list[CorrectionResult]:
        return list(self._history)

    @property
    def succeeded(self) -> bool:
        return bool(self._history) and self._history[-1].is_success

    def run(self) -> CorrectionResult:
        self._history.clear()

        for attempt in range(1, self._max_attempts + 1):
            result = self._attempt(attempt)
            self._history.append(result)
            self._notify(result)

            if result.is_success:
                return result

        return (
            self._history[-1]
            if self._history
            else failure_result(
                attempt=self._max_attempts,
                strategy="none",
                message=f"Exhausted {self._max_attempts} attempts without a fix.",
                file_path=str(self._target_file),
            )
        )

    def _run_verification(self) -> tuple[bool, str]:
        return_code, stdout, stderr = run_tests(self._test_dir, self._runner)
        return return_code == 0, f"{stdout}\n{stderr}".strip()

    def _try_strategies(self, original_code: str, error_output: str) -> tuple[str | None, Strategy | None]:
        return self._registry.fix(
            original_code,
            error_output,
            str(self._target_file),
            test_dir=self._test_dir,
            runner=self._runner,
        )

    def _apply_fix(self, target_file: Path, fixed_code: str) -> tuple[bool, str]:
        _write_code(target_file, fixed_code)
        return_code, stdout, stderr = run_tests(self._test_dir, self._runner)
        return return_code == 0, f"{stdout}\n{stderr}".strip()

    def _attempt(self, attempt: int) -> CorrectionResult:
        t0 = time.monotonic()
        passed, test_output = self._run_verification()
        if passed:
            return success_result(
                attempt=attempt,
                strategy="none",
                file_path=str(self._target_file),
                original_code="",
                test_output=test_output,
                duration_s=time.monotonic() - t0,
            )
        original_code = _read_code(self._target_file)
        fixed_code, strategy = self._try_strategies(original_code, test_output)
        if fixed_code is None or strategy is None:
            return failure_result(
                attempt=attempt,
                strategy="none",
                message="No strategy could produce a fix.",
                file_path=str(self._target_file),
                original_code=original_code,
                test_output=test_output,
                duration_s=time.monotonic() - t0,
            )
        try:
            passed, verify_output = self._apply_fix(self._target_file, fixed_code)
        except FixError as exc:
            return failure_result(
                attempt=attempt,
                strategy=strategy.name,
                message=str(exc),
                file_path=str(self._target_file),
                original_code=original_code,
                fixed_code=fixed_code,
                test_output=test_output,
                duration_s=time.monotonic() - t0,
            )
        duration = time.monotonic() - t0
        if passed:
            return success_result(
                attempt=attempt,
                strategy=strategy.name,
                file_path=str(self._target_file),
                original_code=original_code,
                fixed_code=fixed_code,
                test_output=verify_output,
                duration_s=duration,
            )
        return failure_result(
            attempt=attempt,
            strategy=strategy.name,
            message=f"Fix via '{strategy.name}' did not resolve test failures.",
            file_path=str(self._target_file),
            original_code=original_code,
            fixed_code=fixed_code,
            test_output=verify_output,
            duration_s=duration,
        )

    def _notify(self, result: CorrectionResult) -> None:
        if self._on_attempt is not None:
            self._on_attempt(result)


# ============================================================================
# CLI Entry Points
# ============================================================================


def run_correction(
    target_file: str,
    test_dir: str = "tests",
    max_attempts: int = 3,
    runner: str = "unittest",
    enable_retry: bool = True,
    enable_pattern: bool = True,
    enable_llm: bool = True,
    llm_model: str = "gpt-4-turbo-preview",
    output_json: str | None = None,
) -> int:
    """运行自我修正循环"""
    print_section("自我修正循环")

    if not Path(target_file).exists():
        print_check(f"目标文件存在: {target_file}", False)
        return 1

    print_check(f"目标文件: {target_file}", True)
    print_check(f"测试目录: {test_dir}", True)
    print_check(f"最大尝试次数: {max_attempts}", True)
    print_check(f"测试运行器: {runner}", True)

    registry = get_registry(
        enable_retry=enable_retry,
        enable_pattern=enable_pattern,
        enable_llm=enable_llm,
        llm_model=llm_model,
    )

    loop = CorrectionLoop(
        target_file=target_file,
        test_dir=test_dir,
        max_attempts=max_attempts,
        runner=runner,
        registry=registry,
    )

    result = loop.run()

    # 输出结果
    if result.is_success:
        print_check(f"修正成功 (尝试 {result.attempt}, 策略: {result.strategy})", True)
    else:
        print_check(f"修正失败 (尝试 {result.attempt})", False)
        print(f"  错误: {result.message}")

    # 输出历史记录
    print_section("修正历史")
    for r in loop.history:
        status = "✅" if r.is_success else "❌"
        print(f"  {status} 尝试 {r.attempt}: {r.strategy} - {r.message} ({r.duration_s:.2f}s)")

    # JSON 输出
    if output_json:
        output_data = {
            "success": result.is_success,
            "final_result": result.to_dict(),
            "history": [r.to_dict() for r in loop.history],
        }
        Path(output_json).write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
        print_check(f"结果已写入: {output_json}", True)

    return 0 if result.is_success else 1


def validate_correction(
    target_file: str,
    test_dir: str = "tests",
    runner: str = "unittest",
) -> int:
    """验证目标文件当前是否通过测试（不进行修正）"""
    print_section("验证模式 - 仅运行测试")

    if not Path(target_file).exists():
        print_check(f"目标文件存在: {target_file}", False)
        return 1

    return_code, stdout, stderr = run_tests(test_dir, runner)
    passed = return_code == 0
    print_check("测试通过", passed)
    if not passed:
        print(f"stdout:\n{stdout}")
        print(f"stderr:\n{stderr}")
    return 0 if passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="自我修正循环 - JCode 技能")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run 子命令
    run_parser = subparsers.add_parser("run", help="运行自我修正循环")
    run_parser.add_argument("--target", required=True, help="目标源文件路径")
    run_parser.add_argument("--tests", default="tests", help="测试目录 (默认: tests)")
    run_parser.add_argument("--max-attempts", type=int, default=3, help="最大尝试次数 (默认: 3)")
    run_parser.add_argument(
        "--runner", choices=["unittest", "pytest"], default="unittest", help="测试运行器 (默认: unittest)"
    )
    run_parser.add_argument("--no-retry", action="store_true", help="禁用重试策略")
    run_parser.add_argument("--no-pattern", action="store_true", help="禁用模式匹配策略")
    run_parser.add_argument("--no-llm", action="store_true", help="禁用 LLM 策略")
    run_parser.add_argument("--llm-model", default="gpt-4-turbo-preview", help="LLM 模型 (默认: gpt-4-turbo-preview)")
    run_parser.add_argument("--output-json", help="输出结果到 JSON 文件")

    # validate 子命令
    validate_parser = subparsers.add_parser("validate", help="验证当前代码是否通过测试")
    validate_parser.add_argument("--target", required=True, help="目标源文件路径")
    validate_parser.add_argument("--tests", default="tests", help="测试目录 (默认: tests)")
    validate_parser.add_argument(
        "--runner", choices=["unittest", "pytest"], default="unittest", help="测试运行器 (默认: unittest)"
    )

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(
            run_correction(
                target_file=args.target,
                test_dir=args.tests,
                max_attempts=args.max_attempts,
                runner=args.runner,
                enable_retry=not args.no_retry,
                enable_pattern=not args.no_pattern,
                enable_llm=not args.no_llm,
                llm_model=args.llm_model,
                output_json=args.output_json,
            )
        )
    elif args.command == "validate":
        sys.exit(
            validate_correction(
                target_file=args.target,
                test_dir=args.tests,
                runner=args.runner,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
