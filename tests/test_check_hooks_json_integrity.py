"""Tests for tools/scripts/check_hooks_json_integrity.sh (fail-open hook 检测器).

背景 (Phase 38):
    该脚本是 on_commit 的前置门禁, 用于发现"看似在工作、实际永远失败"的
    hook。历史上 update-moc 调用 `link_auditor.py --update-moc`(该脚本根本
    不支持此参数) 就是典型, 长期被其他 hook 的成功掩盖。

    旧实现只匹配 "unrecognized arguments" 单一关键词, 且内嵌 Python 里
    `except Exception: pass` 吞掉异常, 导致 action 拼错 / 脚本不存在 /
    依赖缺失等 fail-open 全部漏检。

这些测试用 canary 注入真实故障, 验证检测器能抓到 —— 防止修复被静默回退。
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "scripts" / "check_hooks_json_integrity.sh"
HOOKS_JSON = REPO_ROOT / ".jcode" / "hooks.json"


class FailOpenDetectorTest(unittest.TestCase):
    """注入 canary 验证检测器的三类判定能力。"""

    def setUp(self) -> None:
        self._backup = HOOKS_JSON.read_text(encoding="utf-8")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        HOOKS_JSON.write_text(self._backup, encoding="utf-8")

    def _inject(self, hook: dict[str, object]) -> None:
        """把一个 canary hook 追加到 on_commit。"""
        data = json.loads(self._backup)
        data["hooks"]["on_commit"].append(hook)
        HOOKS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=300,
        )

    # ---------- 基线 ----------

    def test_real_hooks_json_passes(self) -> None:
        """真实配置必须通过 —— 否则门禁会变成永不通过的噪声。"""
        result = self._run()
        self.assertEqual(
            result.returncode,
            0,
            f"真实 hooks.json 应通过, 实际输出:\n{result.stdout}{result.stderr}",
        )

    # ---------- 注入故障 ----------

    def test_detects_unsupported_argument(self) -> None:
        """command 参数不被目标脚本支持 (update-moc 历史 bug 的形态)。"""
        self._inject(
            {
                "name": "ZZZ-canary",
                "skill": "knowledge-curator",
                "action": "audit",
                "command": "python tools/scripts/link_auditor.py . --update-moc",
                "enabled": True,
            }
        )
        result = self._run()
        self.assertEqual(result.returncode, 1, "应检测出不支持的参数")
        self.assertIn("ZZZ-canary", result.stdout)
        self.assertIn("--update-moc", result.stdout)

    def test_detects_unknown_skill_action(self) -> None:
        """skill 存在但 action 不存在 —— 旧实现完全漏检这一类。"""
        self._inject(
            {
                "name": "ZZZ-canary",
                "skill": "knowledge-curator",
                "action": "no-such-action",
                "enabled": True,
            }
        )
        result = self._run()
        self.assertEqual(result.returncode, 1, "应检测出不存在的 action")
        self.assertIn("ZZZ-canary", result.stdout)
        self.assertIn("no-such-action", result.stdout)

    def test_detects_missing_script(self) -> None:
        """command 指向不存在的脚本。"""
        self._inject(
            {
                "name": "ZZZ-canary",
                "skill": "knowledge-curator",
                "action": "audit",
                "command": "python tools/scripts/ghost-script.py run",
                "enabled": True,
            }
        )
        result = self._run()
        self.assertEqual(result.returncode, 1, "应检测出不存在的脚本")
        self.assertIn("ZZZ-canary", result.stdout)

    def test_detects_missing_skill_script(self) -> None:
        """skill 脚本本身不存在。"""
        self._inject(
            {
                "name": "ZZZ-canary",
                "skill": "ghost-skill",
                "action": "run",
                "enabled": True,
            }
        )
        result = self._run()
        self.assertEqual(result.returncode, 1, "应检测出不存在的 skill 脚本")
        self.assertIn("ZZZ-canary", result.stdout)


class SubcommandOptionTest(unittest.TestCase):
    """子命令级选项不得被误判为不支持 (假阳性回归)。

    `self-correction-loop.py` 顶层 usage 只暴露 {run,validate}, 而
    --target/--tests 属于 validate 子命令。若只看顶层 --help, 这个完全
    可用的 hook 会被门禁拦下 —— 那比漏检更糟。
    """

    def test_subcommand_options_are_accepted(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                ".jcode/scripts/self-correction-loop.py",
                "validate",
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--target", result.stdout, "前提: --target 确属 validate 子命令")

    def test_real_config_has_subcommand_hook_and_passes(self) -> None:
        """真实配置含 on_pr/self-correction 子命令 hook, 必须通过。"""
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        commands = [h.get("command", "") for h in data["hooks"].get("on_pr", []) if h.get("command")]
        self.assertTrue(
            any("self-correction-loop.py" in c for c in commands),
            "前提: on_pr 存在 self-correction 子命令 hook",
        )

        result = subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=300,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"含子命令选项的 hook 不应被误报:\n{result.stdout}{result.stderr}",
        )


class HelpersTest(unittest.TestCase):
    """直接测内嵌 Python 的两个纯函数。"""

    @staticmethod
    def _load_helpers() -> dict[str, object]:
        """从 shell 脚本里抽出内嵌 Python 并执行, 拿到其命名空间。"""
        text = SCRIPT.read_text(encoding="utf-8")
        start = text.index("python3 - << 'PYEOF'")
        start = text.index("\n", start) + 1
        end = text.index("PYEOF", start)
        body = text[start:end]
        # 去掉遍历 hooks.json 的尾部, 只保留函数定义
        body = body.split("for event, hook_list in")[0]
        # 替换读取 hooks.json 的部分
        body = body.replace('HOOKS_JSON = ".jcode/hooks.json"', "HOOKS_JSON = None")
        body = body.replace(
            'with open(HOOKS_JSON, encoding="utf-8") as fh:\n    hooks = json.load(fh)',
            "hooks = {}",
        )
        namespace: dict[str, object] = {"__name__": "helpers"}
        exec(compile(body, "<extracted>", "exec"), namespace)  # noqa: S102
        return namespace

    def test_supported_long_options_parses_usage(self) -> None:
        ns = self._load_helpers()
        parse = ns["_supported_long_options"]
        assert callable(parse)
        text = (
            "usage: link_auditor.py [-h] [--check-all] [--fail-on-broken]\n"
            "options:\n"
            "  -h, --help  show help\n"
            "  --check-all  Check all\n"
        )
        opts = parse(text)
        assert isinstance(opts, set)
        self.assertIn("--check-all", opts)
        self.assertIn("--fail-on-broken", opts)
        self.assertIn("--help", opts)
        self.assertNotIn("[-h]", opts)

    def test_supported_long_options_ignores_prose(self) -> None:
        """非 argparse 输出不该被解析出选项。"""
        ns = self._load_helpers()
        parse = ns["_supported_long_options"]
        assert callable(parse)
        self.assertEqual(parse("hello world"), set())


if __name__ == "__main__":
    unittest.main()
