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
import shlex
import subprocess
import sys
from pathlib import Path

from _common import get_project_root, print_check, print_section


def load_hooks_config() -> dict:
    """加载 hooks.json 配置"""
    config_path = get_project_root() / ".jcode" / "hooks.json"
    if not config_path.exists():
        print(f"❌ 未找到 hooks 配置: {config_path}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def files_match_condition(changed_files: list[str] | None, condition: str) -> bool:
    """检查变更文件是否满足触发条件"""
    if not condition:
        return True

    # 解析简单条件: files_contain('pattern')
    import re

    matches = re.findall(r"files_contain\('([^']+)'\)", condition)
    if not matches:
        return True

    if not changed_files:
        return False

    for pattern in matches:
        # 支持 glob 模式
        if "*" in pattern:
            for f in changed_files:
                if Path(f).match(pattern):
                    return True
        else:
            for f in changed_files:
                if pattern in f:
                    return True
    return False


def run_hook(hook: dict, changed_files: list[str] | None = None) -> bool:
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


EVENT_MODE_MAP = {
    "on_commit": "quality",
    "on_pr": "safe",
    "on_merge": "quality",
    "scheduled": "quality",
}

CONFIG_PATH = Path(__file__).parent.parent / "mode_decision.conf"


def _set_mode(mode: str) -> None:
    """写入 mode_decision.conf 自动切换模式。"""
    try:
        content = f"mode={mode}\ngovernance_level={'high' if mode in ('quality', 'safe') else 'medium'}\naudit_enabled={'true' if mode != 'perf' else 'false'}\n"
        CONFIG_PATH.write_text(content)
        print(f"  🔄 模式: {mode} (governance_level={'high' if mode in ('quality', 'safe') else 'medium'})")
    except OSError:
        pass  # 非阻断


def run_event_hooks(event: str, changed_files: list[str] | None = None) -> int:
    """运行事件的 hooks 并返回失败数量"""
    # 事件驱动模式切换
    if event in EVENT_MODE_MAP:
        _set_mode(EVENT_MODE_MAP[event])

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
        changed_files = sys.argv[idx + 1 :]

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
