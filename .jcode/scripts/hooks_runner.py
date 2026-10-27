#!/usr/bin/env python3
"""
jcode Hooks 执行引擎

读取 .jcode/hooks.json 配置，根据 git 事件自动触发对应的 skill actions。
支持: on_commit, on_pr, on_merge, scheduled 事件。

用法:
    python .jcode/scripts/hooks_runner.py on_commit [--files file1 file2]
    python .jcode/scripts/hooks_runner.py on_pr [--files file1 file2]
    python .jcode/scripts/hooks_runner.py on_merge
    python .jcode/scripts/hooks_runner.py scheduled
    python .jcode/scripts/hooks_runner.py list
"""

import json
import os
import re
import shlex
import subprocess
import sys
from typing import Any

from _common import get_project_root, print_check, print_section


def load_hooks_config() -> dict[str, Any]:
    """加载 hooks.json 配置"""
    config_path = get_project_root() / ".jcode" / "hooks.json"
    if not config_path.exists():
        print(f"❌ 未找到 hooks 配置: {config_path}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def _translate_glob(pattern: str, *, path_mode: bool) -> str:
    """把 glob 模式转换为正则源码。"""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if path_mode and pattern.startswith("**/", i):
                parts.append(r"(?:[^/]+/)*")
                i += 3
            elif path_mode and pattern.startswith("**", i):
                parts.append(r".*")
                i += 2
            else:
                parts.append(r"[^/]*" if path_mode else r".*")
                i += 1
        elif ch == "?":
            parts.append(r"[^/]" if path_mode else ".")
            i += 1
        elif ch in ".^$+{}[]|()\\":
            parts.append("\\" + ch)
            i += 1
        else:
            parts.append(ch)
            i += 1
    return "".join(parts)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """将 glob 模式转换为正则表达式（支持 **、*、?）。"""
    path_mode = "/" in pattern
    return re.compile("^" + _translate_glob(pattern, path_mode=path_mode) + "$")


_TERM_RE = re.compile(r"(\w+)\('([^']*)'\)")
_ALLOWED_TERMS = frozenset({"files_contain", "pr_label"})


def _parse_condition_terms(condition: str) -> list[tuple[str, str]] | None:
    """解析 OR term；语法错误返回 None（fail-closed）。"""
    parsed: list[tuple[str, str]] = []
    for raw in condition.split("||"):
        term = raw.strip()
        if not term:
            continue
        match = _TERM_RE.fullmatch(term)
        if not match:
            print(f"⚠️  无法解析条件 term: {term}", file=sys.stderr)
            return None
        func_name, arg = match.group(1), match.group(2)
        if func_name not in _ALLOWED_TERMS:
            print(f"⚠️  未知条件函数: {func_name}", file=sys.stderr)
            return None
        parsed.append((func_name, arg))
    return parsed


def _term_matches(func_name: str, arg: str, changed_files: list[str]) -> bool:
    """评估单个已解析 term。"""
    if func_name == "files_contain":
        if "*" not in arg:
            return any(arg in changed for changed in changed_files)
        glob_re = _glob_to_regex(arg)
        anchored = "/" in arg
        return any(glob_re.match(changed if anchored else changed.rsplit("/", 1)[-1]) for changed in changed_files)
    labels_env = os.environ.get("JCODE_PR_LABELS", "")
    if not labels_env:
        return False
    return arg in {label.strip() for label in labels_env.split(",")}


def files_match_condition(changed_files: list[str] | None, condition: str) -> bool:
    """检查变更文件是否满足触发条件。

    支持的条件语法：
    - 空条件或空白 -> True
    - 以 || 分隔的 term 列表：term1 || term2 || ...
    - 每个 term 格式：func('arg')，支持：
      - files_contain(arg): glob 匹配（含 *）或子串匹配（不含 *）
      - pr_label(label): 从环境变量 JCODE_PR_LABELS（逗号分隔）匹配精确标签
    - 解析失败的 term -> False（fail-closed）
    - 条件非空但无可识别 term -> False（fail-closed）
    - 无 changed_files 且条件包含 files_contain 或 pr_label -> False
    """
    if not condition or not condition.strip():
        return True
    parsed_terms = _parse_condition_terms(condition)
    if not parsed_terms or not changed_files:
        return False
    return any(_term_matches(func_name, arg, changed_files) for func_name, arg in parsed_terms)


def run_hook(hook: dict[str, Any], changed_files: list[str] | None = None) -> bool:
    """执行单个 hook 并返回是否成功"""
    name = hook.get("name", "unknown")
    skill = hook.get("skill", "")
    action = hook.get("action", "")
    command = hook.get("command", "")
    condition = hook.get("condition", "")

    if not files_match_condition(changed_files, condition):
        print(f"⏭️  跳过 {name}: 条件不满足 ({condition})")
        return True

    print(f"\n🔄 执行: {name} ({skill}/{action})")

    if command:
        # 直接执行命令 - 使用 shlex.split 避免 shell=True
        cmd_args = shlex.split(command)
        result = subprocess.run(cmd_args, capture_output=True, text=True, cwd=get_project_root())  # nosec B603
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        print_check(name, passed, output)
        if not passed:
            print(output)
        return passed
    else:
        # 调用 skill 脚本 - 受信任路径 # nosec B603
        script = get_project_root() / ".jcode" / "scripts" / f"{skill}.py"
        if not script.exists():
            print(f"❌ 未找到 skill 脚本: {script}")
            return False
        cmd = [sys.executable, str(script), action]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=get_project_root())  # nosec B603
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        print_check(name, passed, output)
        if not passed:
            print(output)
        return passed


def run_event_hooks(event: str, changed_files: list[str] | None = None) -> int:
    """运行事件的 hooks 并返回失败数量"""
    config = load_hooks_config()
    hooks = config.get("hooks", {}).get(event, [])

    if not hooks:
        print(f"ℹ️  事件 '{event}' 无 hooks 配置")
        return 0

    print_section(f"执行 {event} hooks ({len(hooks)} 个)")
    failed = 0
    for hook in hooks:
        if not hook.get("enabled", True):
            print(f"⏭️  跳过 {hook.get('name', '?')}: 已禁用")
            continue
        if not run_hook(hook, changed_files):
            failed += 1

    # 钩子 (context-sync) 会更新自动维护的文档, 其内容含时间戳,
    # 每次运行必然产生新差异; 若不回填暂存区, pre-commit 会因
    # "files were modified by this hook" 无限失败。此处自动 stage。
    repo_root = get_project_root()
    auto_stage = [f for f in ("CONTEXT.md", "ADR.md", ".jcode/baseline.json") if (repo_root / f).exists()]
    if auto_stage and event == "on_commit":
        result = subprocess.run(
            ["git", "diff", "--quiet", "--"] + auto_stage,
            cwd=repo_root,
            capture_output=True,
        )
        if result.returncode != 0:
            subprocess.run(["git", "add", "--"] + auto_stage, cwd=repo_root, capture_output=True)
            print_check(f"已自动暂存钩子更新的文件: {', '.join(auto_stage)}", True)

    return failed


def list_hooks() -> None:
    """列出所有 hooks 配置"""
    config = load_hooks_config()
    hooks = config.get("hooks", {})

    print_section("jcode Hooks 配置")
    for event, hook_list in hooks.items():
        print(f"\n📌 {event}:")
        for hook in hook_list:
            status = "✅" if hook.get("enabled", True) else "⏸️"
            cmd = hook.get("command", f"{hook.get('skill')}/{hook.get('action')}")
            cond = hook.get("condition", "")
            print(f"  {status} {hook['name']}: {cmd}")
            if cond:
                print(f"     条件: {cond}")


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: hooks_runner.py <event> [--files file1 file2]")
        print("Events: on_commit, on_pr, on_merge, scheduled, list")
        sys.exit(1)

    event = sys.argv[1]

    if event == "list":
        list_hooks()
        sys.exit(0)

    # 解析 --files 参数
    changed_files = None
    if "--files" in sys.argv:
        idx = sys.argv.index("--files")
        collected: list[str] = []
        for arg in sys.argv[idx + 1 :]:
            if arg.startswith("--"):
                break
            collected.append(arg)
        # --files 后无值必须报错而非传空列表：files_match_condition 收到 []
        # 会判定所有条件型 hook 不匹配，于是 10 个条件型 hook 全被静默跳过，
        # 而本函数仍报告成功（fail-open）。此处显式失败以关闭该路径。
        if not collected:
            print("❌ --files 后必须跟至少一个文件路径")
            print("   （空列表会导致全部条件型 hook 被跳过并误报成功）")
            sys.exit(1)
        changed_files = collected

    valid_events = ["on_commit", "on_pr", "on_merge", "scheduled"]
    if event not in valid_events:
        print(f"❌ 未知事件: {event}")
        print(f"可用事件: {', '.join(valid_events)}")
        sys.exit(1)

    failed = run_event_hooks(event, changed_files)
    if failed:
        print(f"\n❌ {failed} 个 hooks 失败")
        sys.exit(1)
    else:
        print(f"\n✅ 所有 {event} hooks 通过")


if __name__ == "__main__":
    main()
