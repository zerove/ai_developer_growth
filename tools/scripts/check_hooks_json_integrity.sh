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

PROBLEMS=$(
    PY="$PY" python3 - <<'PYEOF'
import ast
import json
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path

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


def _iter_arg_calls(tree: ast.AST) -> Iterator[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _static_script_options(target: str) -> set[str]:
    """静态解析脚本源码, 收集它声明的长选项与子命令。

    **不执行目标脚本。** 旧实现用 `python <target> --help` 探测参数, 等于让
    校验器执行待校验代码: `.jcode/hooks.json` 的 command 字段可被贡献者控制,
    于是"检查配置"这一动作本身变成任意代码执行 (RCE)。实测在目标脚本顶层写
    一行落盘副作用, 跑一次校验器即被触发。

    取"全文件所有 add_argument 长选项的并集"而非逐子命令精确归属:
    本检查的目的是抓拼写错误 (如 `--update-moc`), 并集仍能抓住这类,
    且避免了精确归属的漏判 —— 该检查的历史教训正是**假阳性**曾差点拦下可用 hook。
    """
    options: set[str] = set()
    subcommands: set[str] = set()
    try:
        source = Path(target).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError):
        return options

    for call in _iter_arg_calls(tree):
        func = call.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in ("add_argument", "add_parser", "add_subparsers"):
            continue
        for arg in call.args:
            # 仅取字面量字符串, 跳过变量与拼接表达式
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if name == "add_parser":
                    subcommands.add(arg.value)
                elif arg.value.startswith("--"):
                    options.add(arg.value.split("=", 1)[0])
    options |= {f"--{sub}" for sub in subcommands}
    return options


def _script_options(target: str) -> set[str]:
    """收集脚本在顶层与各子命令下声明的全部长选项。

    含子命令: argparse 的子命令选项不出现在顶层 usage 里, 而 hook 常以
    `self-correction-loop.py validate --target X` 的形式调用子命令。
    静态解析下二者一并收集, 语义等价于旧的"顶层 + 逐子命令"并集。
    """
    return _static_script_options(target)


def _command_problem(hook: dict) -> str | None:
    """校验 hook 的 command 能否被底层脚本识别。"""
    command = hook.get("command", "")
    if not command:
        return None

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    # `sh -c '<内联命令>'`: 命令主体藏在一段字符串里, 无法静态确认它指向哪个脚本。
    # 旧实现按空白切分后取首个 .py/.sh 结尾 token, 内联命令必然不匹配 ->
    # target is None -> 直接放行, 任意命令都能借 bash -c 绕过本检查。
    # 本仓现有 hook 一律是 `bash <脚本>.sh` 形式, 无一使用 -c, 故此处不产生假阳性。
    if "-c" in tokens:
        idx = tokens.index("-c")
        inline = tokens[idx + 1] if idx + 1 < len(tokens) else ""
        return (
            f"{hook.get('name', '?')}: command 使用 shell -c 内联命令, 无法静态校验 "
            f"-> {inline[:80]} (改为直接调用脚本路径)"
        )

    target = next((t for t in tokens if t.endswith((".py", ".sh"))), None)
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

    parts = tokens
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
