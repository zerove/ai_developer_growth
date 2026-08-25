#!/usr/bin/env python3
"""
jcode Skill Runner - 自我修正循环

用法:
    python .jcode/scripts/self-correction-loop.py validate --target <file> --tests <dir>
    python .jcode/scripts/self-correction-loop.py run --target <file> --tests <dir> [--max-attempts 3]
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# 常见测试失败的模式 → 自动修正建议（pattern 策略）
PATTERNS = [
    (r"ModuleNotFoundError: No module named '(\w+)'", "缺少依赖: pip install {0} 或补充 sys.path"),
    (r"ImportError: cannot import name '(\w+)'", "导入名变更: 同步导出或更新引用 {0}"),
    (r"assert (\d+) == (\d+)", "数值断言失败: 检查边界值（off-by-one）"),
    (r"ZeroDivisionError", "除零: 增加分母非零守卫"),
    (r"KeyError: '(\w+)'", "键缺失: 用 .get() 或补数据 {0}"),
]


def run_pytest(tests_dir: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", tests_dir, "-q", "--no-header", "-x", "--timeout=120"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def diagnose(output: str) -> list[str]:
    """模式匹配诊断失败原因（pattern 策略）。"""
    suggestions = []
    for pattern, advice in PATTERNS:
        m = re.search(pattern, output)
        if m:
            suggestions.append(advice.format(*m.groups()) if m.groups() else advice)
    return suggestions


def validate(target: str, tests_dir: str) -> int:
    print(f"[validate] target={target} tests={tests_dir}")
    code, output = run_pytest(tests_dir)
    status = "PASS" if code == 0 else "FAIL"
    report = {"status": status, "attempts": 1, "strategy": "retry"}
    print(json.dumps(report, ensure_ascii=False))
    if code != 0:
        for s in diagnose(output):
            print(f"  建议: {s}")
    return code


def run_loop(target: str, tests_dir: str, max_attempts: int = 3) -> int:
    """验证→重试→修正闭环。无 LLM 时 pattern 策略只给建议不自动改码（安全边界）。"""
    start = time.time()
    attempts = 0
    strategies_used = ["retry"]
    last_output = ""
    while attempts < max_attempts:
        attempts += 1
        code, output = run_pytest(tests_dir)
        last_output = output
        if code == 0:
            break
        suggestions = diagnose(output)
        if suggestions and attempts < max_attempts:
            strategies_used.append("pattern")
            print(f"[attempt {attempts}] 失败，pattern 建议:")
            for s in suggestions:
                print(f"  - {s}")
            # 安全边界：自动改码需 LLM 策略与人工确认，此处仅重试
            time.sleep(1)
    success = code == 0
    report = {
        "status": "success" if success else "failed",
        "attempts": attempts,
        "strategies": strategies_used,
        "elapsed_ms": round((time.time() - start) * 1000, 1),
    }
    print(json.dumps(report, ensure_ascii=False))
    if not success:
        for s in diagnose(last_output):
            print(f"  最终建议: {s}")
    return 0 if success else 1


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else ""

    def get_flag(flag: str, default: str | None = None) -> str | None:
        return args[args.index(flag) + 1] if flag in args else default

    if action == "validate":
        sys.exit(validate(get_flag("--target", ""), get_flag("--tests", "tests")))
    elif action == "run":
        max_attempts = int(get_flag("--max-attempts", "3") or 3)
        sys.exit(run_loop(get_flag("--target", ""), get_flag("--tests", "tests"), max_attempts))
    else:
        print("用法: self-correction-loop.py <validate|run> --target <file> --tests <dir> [--max-attempts N]")
        sys.exit(1)


if __name__ == "__main__":
    main()
