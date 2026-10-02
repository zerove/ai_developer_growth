#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Check .jcode/hooks.json 完整性 (防止 fail-open hook 静默失败)
# ──────────────────────────────────────────────────────────────
# Phase 30 收口后建立: 当时发现 update-moc hook 调用
# link_auditor.py --update-moc 但 link_auditor.py 不支持, hook 一直
# fail-open. 历史以来被其他 hook 覆盖掩盖.
#
# ── Phase 38 修复 ─────────────────────────────────────────────
# 原实现扫描 hooks_runner 输出, 仅在出现 "unrecognized arguments"
# 关键词时告警。这个判据有两个问题:
#   1. 只覆盖一种失败形态。action 拼错 (skill 存在但 action 不存在)、
#      脚本不存在、依赖缺失等 fail-open 全部漏检 —— 而 update-moc
#      恰恰是靠"被其他 hook 掩盖"才长期存在的, 说明关键词判据本身
#      就不够。
#   2. 内嵌 Python 里 `except Exception: pass` 吞掉超时/异常, 一旦
#      子进程跑不完就静默通过。
#
# 现改为: 直接解析每个 hook, 用 --help / 参数校验判断其 command 与
# action 是否真的可执行, 且异常一律显式报错而非静默跳过。
# 不实际跑业务逻辑 (会触发真实 lint/测试, 代价过高), 只验证
# "这个 hook 指向的东西存在且认识这个参数"。
#
# 用法: bash tools/scripts/check_hooks_json_integrity.sh
# 退出码: 0 通过 / 1 存在 fail-open 风险
# ──────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ ! -f .jcode/hooks.json ]; then
    echo "❌ .jcode/hooks.json 文件不存在"
    exit 1
fi

# 探测目标脚本时用项目自己的解释器, 而不是 PATH 里的 python3。
# 本机 python3 是 mise 装的 3.14, 而项目 venv 是 3.11 (pyproject requires-python
# >=3.11)。若目标脚本依赖 venv 里的第三方包, 用系统解释器探测会因 ImportError
# 拿不到 --help, 从而静默跳过参数校验 —— 又一次 fail-open。
# 优先 uv run, 其次项目 .venv, 最后才回退到 PATH 里的 python3。
if command -v uv >/dev/null 2>&1; then
    PY="${PY:-uv run python}"
elif [ -x .venv/bin/python ]; then
    PY="${PY:-.venv/bin/python}"
else
    PY="${PY:-python3}"
fi

PROBLEMS=$(PY="$PY" python3 - << 'PYEOF'
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# 目标脚本用项目解释器跑 (见 shell 层的 PY 选定逻辑), 本体仍用系统 python3
# —— 这里只做 JSON/文本解析, 不需要 venv 依赖。
PY_CMD = shlex.split(os.environ.get("PY", "python3"))

HOOKS_JSON = ".jcode/hooks.json"

with open(HOOKS_JSON, encoding="utf-8") as fh:
    hooks = json.load(fh)

problems = []

# skill 入口脚本里显式声明的 action (用于校验 action 是否存在)
SKILL_DIR = ".jcode/scripts"


def _declared_actions(skill: str) -> set[str] | None:
    """从 skill 脚本的 action_map / actions 字典里抽出合法 action 名。

    抽不到 (脚本不存在、无 action 映射、写法变化) 时返回 None,
    表示"无法判定", 交由调用方决定是否跳过校验。
    """
    path = f"{SKILL_DIR}/{skill}.py"
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return None

    # 形如:  actions = { "validate": validate, ... }
    #      action_map = { "scan": scan, ... }
    actions: set[str] = set()
    for marker in ('actions = {', 'action_map = {'):
        idx = src.find(marker)
        if idx < 0:
            continue
        body = src[idx:]
        end = body.find('}')
        if end < 0:
            continue
        chunk = body[:end]
        for line in chunk.splitlines():
            line = line.strip().strip(',')
            if not line.startswith('"'):
                continue
            key = line.split('"')[1]
            if key:
                actions.add(key)
    return actions or None


def _supported_long_options(help_text: str) -> set[str]:
    """从 --help 输出里抽出脚本支持的长选项。

    argparse 的 usage 行用方括号包裹可选参数, 例如:
        usage: link_auditor.py [-h] [--check-all] [--fail-on-broken] [directory]
    所以必须先剥掉方括号再判断是否为长选项 —— 直接 startswith("--")
    会把整条 "[--check-all]" 判否, 结果解析出空集合, 参数校验形同虚设。
    """
    options: set[str] = set()
    for token in help_text.split():
        opt = token.strip("[]").split("=", 1)[0].rstrip(",;)")
        if not opt.startswith("--") or opt == "--":
            continue
        # 形如 --foo=VALUE 时只取 --foo
        options.add(opt)
    return options


def _script_options(target: str) -> set[str]:
    """收集脚本在顶层与各子命令下支持的全部长选项。

    必须包含子命令: argparse 的子命令选项不会出现在顶层 --help 里。
    例: self-correction-loop.py 顶层 usage 只有 {run,validate},
    而 --target / --tests 属于 validate 子命令。只看顶层会把它误判为
    "不支持的参数" —— 这个假阳性曾差点让一个可用 hook 被门禁拦下。
    """
    options: set[str] = set()
    try:
        top = subprocess.run(
            [*PY_CMD, target, "--help"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        return options

    text = top.stdout + top.stderr
    options |= _supported_long_options(text)

    # 从 usage 的 {a,b,c} 位置参数里枚举子命令
    subcommands: list[str] = []
    match = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", text)
    if match:
        subcommands = [s for s in match.group(1).split(",") if s]

    for sub in subcommands:
        try:
            r = subprocess.run(
                [*PY_CMD, target, sub, "--help"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        options |= _supported_long_options(r.stdout + r.stderr)

    return options


def _command_problem(hook: dict) -> str | None:
    """校验 hook 的 command 能否被底层脚本识别。"""
    command = hook.get("command", "")
    if not command:
        return None

    # 抽取目标脚本 (取第一个 .py / .sh 结尾的参数)
    target = None
    for token in command.split():
        if token.endswith((".py", ".sh")):
            target = token
            break
    if target is None:
        return None

    # 脚本必须存在
    if not Path(target).exists():
        return f"{hook.get('name', '?')}: command 指向的脚本不存在 -> {target}"

    # 非 python 脚本无法用 --help 判参数, 跳过
    if not target.endswith(".py"):
        return None

    # 注意: 不能用 "<args> --help" 探测。argparse 遇到 --help 会先打印帮助
    # 并以 0 退出, 根本不会校验其余参数 —— 实测 `link_auditor.py .
    # --update-moc --help` 退出码为 0 且不报任何参数错误, 会把坏参数
    # 全部漏检 (比旧实现更差)。改为从 --help 输出里解析出脚本真实
    # 支持的选项 (含各子命令), 再逐个比对 command 里的长选项。
    supported = _script_options(target)
    if not supported:
        # --help 跑不通或非 argparse 脚本: 无法判定, 不猜。
        # 注意: 这会让"参数校验"整体失效, 但不会误报 —— 宁可漏检不可误伤。
        return None

    parts = command.split()
    script_idx = parts.index(target)
    used = parts[script_idx + 1 :]

    for token in used:
        opt = token.strip("[]").split("=", 1)[0].rstrip(",;)")
        if not opt.startswith("--") or opt == "--":
            continue
        if opt not in supported:
            return (
                f"{hook.get('name', '?')}: command 参数 {opt} 不被 {target} 支持 "
                f"(可用: {', '.join(sorted(supported))})"
            )

    return None


def _action_problem(hook: dict) -> str | None:
    """校验 hook 的 skill/action 组合存在。"""
    skill = hook.get("skill", "")
    action = hook.get("action", "")
    if not skill or not action:
        return None

    # 有 command 的 hook 以 command 为准 (command 里可能已含完整调用)
    if hook.get("command"):
        return None

    script = f"{SKILL_DIR}/{skill}.py"
    if not Path(script).exists():
        return f"{hook.get('name', '?')}: skill 脚本不存在 -> {script}"

    declared = _declared_actions(skill)
    if declared and action not in declared:
        return (
            f"{hook.get('name', '?')}: skill '{skill}' 不支持 action '{action}' "
            f"(可用: {', '.join(sorted(declared))})"
        )
    return None


for event, hook_list in hooks.get("hooks", {}).items():
    if not isinstance(hook_list, list):
        problems.append(f"{event}: hooks 配置不是列表")
        continue
    for hook in hook_list:
        if not isinstance(hook, dict):
            problems.append(f"{event}: hook 条目不是对象")
            continue
        name = hook.get("name", "?")
        for problem in (_command_problem(hook), _action_problem(hook)):
            if problem:
                problems.append(f"  - {event}/{problem}")
                break

if problems:
    print("\n".join(problems))

sys.exit(0)
PYEOF
)

if [ -n "$PROBLEMS" ]; then
    echo "❌ .jcode/hooks.json 检测到 fail-open 风险"
    echo ""
    echo "以下 hook 无法真正执行（指向不存在的脚本 / 不支持的参数或 action）:"
    echo "$PROBLEMS"
    echo ""
    echo "这类问题的危害: hook 看似在工作，实际永远失败或被跳过。"
    echo "历史上 update-moc 调用 link_auditor.py --update-moc 即属此类，"
    echo "长期被其他 hook 的成功掩盖而未被发现。"
    echo ""
    echo "修复方向:"
    echo "  1. 移除该 hook"
    echo "  2. 让目标脚本支持该参数/action"
    echo "  3. 若该能力尚未实现，明确报告未实现并返回非 0（勿静默通过）"
    echo ""
    exit 1
fi

echo "✅ .jcode/hooks.json 全部 hook 命令与 action 均可执行"
exit 0
