"""check_hooks_json_integrity.sh 的 RCE 与绕过回归测试。

## 要锁住的两个缺陷

**缺陷 A — 校验器执行待校验脚本 (RCE)。**
旧实现用 `python <target> --help` 探测脚本参数, 于是"检查配置"这个动作本身
变成任意代码执行: `.jcode/hooks.json` 的 `command` 字段可被贡献者控制,
校验器会替他跑一遍。实测在目标脚本顶层写一行落盘副作用, 跑一次校验器即触发。

**缺陷 B — `bash -c '<内联命令>'` 完全绕过检查。**
旧实现按空白切分后取首个 `.py`/`.sh` 结尾的 token; 内联命令里若没有脚本路径
则 `target is None` 直接放行。于是任意命令都能挂在 `bash -c` 后面进 config。

## 为何用沙箱而不是改仓库里的 hooks.json

`tests/test_check_hooks_json_integrity.py` 会真改仓库里的 `.jcode/hooks.json`
(需持 repo mutation 锁)。本组测试**不碰仓库文件**: 把被测脚本复制到临时目录的
`tools/scripts/` 下 —— 脚本开头 `cd "$(dirname "$0")/../.."` 会自动落到该沙箱根,
因此读的是沙箱里的 `.jcode/hooks.json`。这样与既有测试零干扰, 也避免与他人的
ZZZ-canary 验证相互覆盖。

## 断言口径

全部落在**用户可见行为**上 (进程退出码 + 标准输出), 不断言内部函数返回值。
并对"合法命令不得被误伤"给出反向约束 —— 修复不得靠"一律判失败"来实现。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import acquire_repo_read_lock  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "scripts" / "check_hooks_json_integrity.sh"

# 顶层即产生副作用的"目标脚本": 若校验器执行了它, 哨兵文件必然出现
EVIL_SCRIPT = """\
import pathlib

pathlib.Path({sentinel!r}).write_text("executed", encoding="utf-8")
print("help ok")
"""

# 既是 argparse 脚本 (声明 --good) 又在顶层产生副作用: 用于同时验证
# "参数校验仍然生效" 与 "绝不执行目标脚本" 两件事。
# 不可只用无选项脚本 —— 那种脚本 _static_script_options 返回空集, 校验器会按
# "宁可漏检不可误伤" 跳过参数校验, 从而掩盖"检测能力是否退化"。
EVIL_ARGPARSE_SCRIPT = """\
import argparse
import pathlib

pathlib.Path({sentinel!r}).write_text("executed", encoding="utf-8")
p = argparse.ArgumentParser()
p.add_argument("--good", action="store_true")
"""

# 正常 argparse 脚本, 供反向约束使用
ARG_SCRIPT = """\
import argparse

p = argparse.ArgumentParser()
p.add_argument("--good", action="store_true")
p.add_argument("validate", nargs="?", default="run")
sub = p.add_subparsers(dest="cmd")
sub.add_parser("validate")
q = sub.add_parser("audit")
q.add_argument("--target")
q.add_argument("--tests")
"""


def _sandbox(tmp_path: Path, hooks: list[dict], scripts: dict[str, str]) -> Path:
    """搭出 <root>/tools/scripts + <root>/.code 的最小可运行环境。"""
    root = tmp_path / "repo"
    (root / "tools" / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "tools" / "scripts" / SCRIPT.name)
    (root / ".jcode" / "scripts").mkdir(parents=True)
    for name, body in scripts.items():
        (root / ".jcode" / "scripts" / name).write_text(body, encoding="utf-8")
    (root / ".jcode" / "hooks.json").write_text(
        json.dumps({"hooks": {"on_commit": hooks}}, ensure_ascii=False), encoding="utf-8"
    )
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "tools" / "scripts" / SCRIPT.name)],
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestValidatorMustNotExecuteTarget:
    """缺陷 A: 校验器是审计器, 不是执行器。"""

    def test_target_script_is_not_executed(self, tmp_path: Path) -> None:
        sentinel = tmp_path / "RCE_SENTINEL"
        root = _sandbox(
            tmp_path,
            [{"name": "probe", "command": "python .jcode/scripts/evil.py --help"}],
            {"evil.py": EVIL_SCRIPT.format(sentinel=str(sentinel))},
        )

        result = _run(root)

        assert not sentinel.exists(), "校验器执行了待校验脚本 —— RCE 未修复"
        assert result.returncode == 0, f"合法 hook 不应报错: {result.stdout}"

    def test_side_effect_absent_even_when_flagged(self, tmp_path: Path) -> None:
        """即便该 hook 因参数问题被报出, 也绝不能执行目标脚本。

        目标脚本必须是 argparse 脚本: 无选项脚本会让校验器按"宁可漏检不可误伤"
        跳过参数校验, 那样 returncode 恒为 0, 就测不出"检测能力是否还在"。
        """
        sentinel = tmp_path / "RCE_SENTINEL2"
        root = _sandbox(
            tmp_path,
            [{"name": "probe", "command": "python .jcode/scripts/evil.py --bogus-flag"}],
            {"evil.py": EVIL_ARGPARSE_SCRIPT.format(sentinel=str(sentinel))},
        )

        result = _run(root)

        assert not sentinel.exists(), "校验器执行了待校验脚本 —— RCE 未修复"
        assert result.returncode == 1, "不支持的参数应被报出"
        assert "--bogus-flag" in result.stdout


class TestShellDashCIsRejected:
    """缺陷 B: 内联命令无法静态校验, 必须显式拒绝而非静默放行。"""

    def test_inline_command_rejected(self, tmp_path: Path) -> None:
        root = _sandbox(
            tmp_path,
            [{"name": "sneaky", "command": "bash -c 'echo hello'"}],
            {},
        )

        result = _run(root)

        assert result.returncode == 1, "shell -c 内联命令必须被拒绝"
        assert "sneaky" in result.stdout, "报错信息须指名 hook"

    def test_inline_command_hiding_missing_script_rejected(self, tmp_path: Path) -> None:
        """即使内联里引用了不存在的脚本, 也必须报出而不是被 split() 漏掉。"""
        root = _sandbox(
            tmp_path,
            [{"name": "ghost", "command": "bash -c 'python .jcode/scripts/ghost.py run'"}],
            {},
        )

        result = _run(root)

        assert result.returncode == 1
        assert "ghost" in result.stdout

    def test_quoted_dash_c_still_rejected(self, tmp_path: Path) -> None:
        """引号包裹的 `-c` 同样必须被识别。

        这一条专门锁住分词方式: 按空白 `split()` 会把 `"-c"` 拆成带引号的普通
        token, 判断不到 shell 内联命令, 绕过即成立。必须用 shlex 正确去引号。
        """
        root = _sandbox(
            tmp_path,
            [{"name": "sneaky-quoted", "command": "bash \"-c\" 'echo hello'"}],
            {},
        )

        result = _run(root)

        assert result.returncode == 1, "引号包裹的 -c 绕过了检查"
        assert "sneaky-quoted" in result.stdout


class TestNoFalsePositive:
    """修复不得靠"一律判失败"实现 —— 合法配置必须仍然通过。"""

    def test_plain_script_invocation_passes(self, tmp_path: Path) -> None:
        root = _sandbox(
            tmp_path,
            [{"name": "ok", "command": "bash .jcode/scripts/arg.py --good"}],
            {"arg.py": ARG_SCRIPT},
        )

        result = _run(root)

        assert result.returncode == 0, f"合法 hook 被误伤: {result.stdout}"

    def test_python_invocation_passes(self, tmp_path: Path) -> None:
        root = _sandbox(
            tmp_path,
            [{"name": "ok2", "command": "python .jcode/scripts/arg.py --good"}],
            {"arg.py": ARG_SCRIPT},
        )

        assert _run(root).returncode == 0

    def test_subcommand_options_recognised(self, tmp_path: Path) -> None:
        """`--target` 属 audit 子命令, 静态解析必须一并识别 (旧实现的原意)。"""
        root = _sandbox(
            tmp_path,
            [{"name": "ok3", "command": "python .jcode/scripts/arg.py audit --target x"}],
            {"arg.py": ARG_SCRIPT},
        )

        assert _run(root).returncode == 0, "子命令选项被误判为不支持"

    def test_shell_script_invocation_passes(self, tmp_path: Path) -> None:
        """`bash <script>.sh` 是本仓既有写法, 不得被 -c 规则误伤。"""
        root = _sandbox(
            tmp_path,
            [{"name": "ok4", "command": "bash .jcode/scripts/real.sh"}],
            {"real.sh": "#!/usr/bin/env bash\necho hi\n"},
        )

        assert _run(root).returncode == 0, "合法的 bash <script>.sh 被误伤"


class TestDetectionNotDegraded:
    """AST 静态解析不得悄悄削弱原有的参数校验能力。"""

    def test_unsupported_flag_still_detected(self, tmp_path: Path) -> None:
        root = _sandbox(
            tmp_path,
            [{"name": "bad", "command": "python .jcode/scripts/arg.py --update-moc"}],
            {"arg.py": ARG_SCRIPT},
        )

        result = _run(root)

        assert result.returncode == 1, "不支持的参数未被报出"
        assert "--update-moc" in result.stdout

    def test_missing_script_still_detected(self, tmp_path: Path) -> None:
        root = _sandbox(
            tmp_path,
            [{"name": "missing", "command": "python .jcode/scripts/nope.py --good"}],
            {},
        )

        result = _run(root)

        assert result.returncode == 1
        assert "nope.py" in result.stdout

    def test_real_repo_config_has_no_inline_shell(self) -> None:
        """本仓既有 hook 一律 `bash <脚本>.sh`, 无一使用 -c —— 新规则不会误伤本仓。"""
        # .jcode/hooks.json 是受控文件 (会与他人并发改动竞争), 读取须持共享读锁
        with acquire_repo_read_lock():
            config = json.loads((REPO_ROOT / ".jcode" / "hooks.json").read_text(encoding="utf-8"))
        offenders = [
            hook.get("name", "?")
            for hooks in config["hooks"].values()
            for hook in hooks
            if "-c" in str(hook.get("command", "")).split()
        ]
        assert not offenders, f"本仓出现 shell -c 内联命令, 需改写为直接调用脚本: {offenders}"


@pytest.mark.parametrize("script_name", ["arg.py"])
def test_sandbox_script_is_not_shared(tmp_path: Path, script_name: str) -> None:
    """沙箱脚本必须落在临时目录内, 确认没有写回仓库。"""
    root = _sandbox(tmp_path, [], {script_name: ARG_SCRIPT})
    assert root.is_relative_to(tmp_path)
    assert not (REPO_ROOT / ".jcode" / "scripts" / script_name).exists()
