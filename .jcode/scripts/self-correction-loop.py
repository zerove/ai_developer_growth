#!/usr/bin/env python3
"""jcode Skill Runner - 自我修正循环

修正循环的实现在 examples/self-correction-loop/src（模块化拆分，且有测试覆盖）。
本文件只负责 jcode skill 需要的 CLI 与报告输出，逻辑一律复用该实现，
避免同一套策略链存在两份副本。
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from _common import print_check, print_section

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_SRC = ROOT / "examples" / "self-correction-loop" / "src"

sys.path.insert(0, str(EXAMPLE_SRC))

from results import CorrectionResult  # noqa: E402
from runner import CorrectionLoop, run_tests  # noqa: E402
from strategies.base import get_registry  # noqa: E402


def _as_dict(result: CorrectionResult) -> dict[str, Any]:
    data = asdict(result)
    data["status"] = result.status.value
    return data


def _report(result: CorrectionResult, history: list[CorrectionResult], output_json: str | None) -> None:
    """打印最终结果、修正历史，并按需写出 JSON 报告。"""
    if result.is_success:
        print_check(f"修正成功 (尝试 {result.attempt}, 策略: {result.strategy})", True)
    else:
        print_check(f"修正失败 (尝试 {result.attempt})", False)
        print(f"  错误: {result.message}")

    print_section("修正历史")
    for r in history:
        status = "✅" if r.is_success else "❌"
        print(f"  {status} 尝试 {r.attempt}: {r.strategy} - {r.message} ({r.duration_s:.2f}s)")

    if not output_json:
        return
    payload = {
        "success": result.is_success,
        "final_result": _as_dict(result),
        "history": [_as_dict(r) for r in history],
    }
    # 早前直接 write_text，父目录不存在时抛 FileNotFoundError
    # （`--output-json reports/run.json` 是很常见的写法）。
    out_path = Path(output_json)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print_check(f"结果已写入: {output_json}", True)


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

    loop = CorrectionLoop(
        target_file=target_file,
        test_dir=test_dir,
        max_attempts=max_attempts,
        runner=runner,
        registry=get_registry(
            enable_retry=enable_retry,
            enable_pattern=enable_pattern,
            enable_llm=enable_llm,
            llm_model=llm_model,
        ),
    )

    result = loop.run()
    _report(result, loop.history, output_json)
    return 0 if result.is_success else 1


def validate_correction(
    target_file: str,
    test_dir: str = "tests",
    runner: str = "unittest",
    timeout: int = 300,
) -> int:
    """验证目标文件当前是否通过测试（不进行修正）"""
    print_section("验证模式 - 仅运行测试")

    if not Path(target_file).exists():
        print_check(f"目标文件存在: {target_file}", False)
        return 1

    return_code, stdout, stderr = run_tests(test_dir, runner, timeout=timeout)
    passed = return_code == 0
    print_check("测试通过", passed)
    if not passed:
        print(f"stdout:\n{stdout}")
        print(f"stderr:\n{stderr}")
    return 0 if passed else 1


def _add_run_arguments(subparsers: Any) -> None:
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


def _add_validate_arguments(subparsers: Any) -> None:
    validate_parser = subparsers.add_parser("validate", help="验证当前代码是否通过测试")
    validate_parser.add_argument("--target", required=True, help="目标源文件路径")
    validate_parser.add_argument("--tests", default="tests", help="测试目录 (默认: tests)")
    validate_parser.add_argument(
        "--runner", choices=["unittest", "pytest"], default="unittest", help="测试运行器 (默认: unittest)"
    )
    validate_parser.add_argument("--timeout", type=int, default=300, help="测试运行超时秒数 (默认: 300)")


def main() -> None:
    parser = argparse.ArgumentParser(description="自我修正循环 - JCode 技能")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_run_arguments(subparsers)
    _add_validate_arguments(subparsers)

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
                timeout=args.timeout,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
