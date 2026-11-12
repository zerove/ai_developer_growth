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
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import (  # noqa: E402
    acquire_repo_mutation_lock as _acquire_repo_mutation_lock,
)
from conftest import (
    acquire_repo_read_lock,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "scripts" / "check_hooks_json_integrity.sh"
HOOKS_JSON = REPO_ROOT / ".jcode" / "hooks.json"


class FailOpenDetectorTest(unittest.TestCase):
    """注入 canary 验证检测器的三类判定能力。"""

    def setUp(self) -> None:
        # 跨进程互斥: 本类会真改仓库里的 .jcode/hooks.json。pytest-xdist 下
        # 多 worker 并行时彼此看不到对方的 addCleanup, 实测 -n 8 下 9 failed
        # 且 ZZZ-canary 残留在受控配置里。锁必须按"每个用例"获取 ——
        # 按类获取会让同类的用例仍可并行, 而它们互相改的是同一个文件。
        #
        # 用例写法是 unittest.TestCase, 无法注入 pytest fixture,
        # 故在此直接进入上下文管理器, 并由 addCleanup 退出
        # (失败路径也保证释放)。
        lock_cm = _acquire_repo_mutation_lock()
        lock_cm.__enter__()
        self.addCleanup(lock_cm.__exit__, None, None, None)

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

    跨进程共享读锁: 本类只**读**真实 hooks.json, 但同文件正被
    ``FailOpenDetectorTest`` 真改写。共享锁让多个读者并行, 同时被
    写者的独占锁挡住 —— 否则会在写者持有 canary 的窗口里读到临时
    内容而误报失败 (实测 ``-n 8`` 会出现)。
    """

    def setUp(self) -> None:
        self.read_lock = acquire_repo_read_lock()
        self.read_lock.__enter__()
        self.addCleanup(self.read_lock.__exit__, None, None, None)

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


class InterpreterConsistencyTest(unittest.TestCase):
    """探测用的解释器必须与项目一致 (ADR-062 补记)。

    本机 PATH 里的 python3 是 mise 装的 3.14, 而项目 venv 是 3.11。
    若探测时用错解释器, 依赖 venv 包的脚本会因 ImportError 拿不到 --help,
    参数校验就会被静默跳过 —— 又一次 fail-open, 且不报错。

    跨进程共享读锁: ``test_runs_from_unrelated_cwd`` 会跑真实探测脚本
    读受控 hooks.json, 需与 ``FailOpenDetectorTest`` 的独占写锁互斥。
    """

    def setUp(self) -> None:
        self.read_lock = acquire_repo_read_lock()
        self.read_lock.__enter__()
        self.addCleanup(self.read_lock.__exit__, None, None, None)

    def test_script_prefers_project_interpreter_over_path_python(self) -> None:
        """脚本不得直接用 PATH 里的 python3 探测目标脚本。"""
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("PY=", text, "应先选定项目解释器")
        self.assertNotIn(
            "[sys.executable, target",
            text,
            "探测目标脚本时不应使用内嵌解释器 sys.executable",
        )

    def test_runs_under_system_python_only_fallback(self) -> None:
        """强制回退到系统 python3 时仍能正确判定 (不崩溃、不误报)。"""
        env = dict(os.environ)
        env["PY"] = sys.executable
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=300,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"回退解释器下真实配置应通过:\n{result.stdout}{result.stderr}",
        )

    def test_runs_from_unrelated_cwd(self) -> None:
        """从任意目录调用都应正常工作 (脚本需自行 cd 到仓库根)。"""
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd="/",
            timeout=300,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"非仓库目录下应仍能通过:\n{result.stdout}{result.stderr}",
        )


class HelpersTest(unittest.TestCase):
    """直接测内嵌 Python 的两个纯函数。"""

    @staticmethod
    def _load_helpers() -> dict[str, object]:
        """从 shell 脚本里抽出内嵌 Python 并执行, 拿到其命名空间。"""
        text = SCRIPT.read_text(encoding="utf-8")
        # heredoc 标记的空白由格式化器决定（shfmt 会把 `<< 'PYEOF'` 规范成
        # `<<'PYEOF'`），按正则匹配而非固定字面量，避免"格式化脚本 → 测试挂"。
        match = re.search(r"python3 - <<\s*'PYEOF'", text)
        if match is None:
            raise AssertionError("未找到内嵌 Python 的 heredoc 起始标记")
        start = text.index("\n", match.end()) + 1
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

    def test_static_options_parses_add_argument(self) -> None:
        """从源码里的 add_argument 声明取长选项 (不再解析 --help 文本)。"""
        ns = self._load_helpers()
        parse = ns["_static_script_options"]
        assert callable(parse)
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "link_auditor.py"
            script.write_text(
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                'p.add_argument("--check-all", action="store_true")\n'
                'p.add_argument("--fail-on-broken")\n'
                'p.add_argument("-h", "--help")\n',
                encoding="utf-8",
            )
            opts = parse(str(script))
        assert isinstance(opts, set)
        self.assertIn("--check-all", opts)
        self.assertIn("--fail-on-broken", opts)
        self.assertIn("--help", opts)

    def test_static_options_ignores_non_argparse_source(self) -> None:
        """无 add_argument 的源码不该被解析出选项。

        旧实现从 --help 文本里正则抓选项, 故必须防御 help 里出现的散文性文字;
        改用 AST 后只认 add_argument 调用, 该风险从结构上消失, 此处锁住新行为。
        """
        ns = self._load_helpers()
        parse = ns["_static_script_options"]
        assert callable(parse)
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "prose.py"
            script.write_text(
                "import sys\n"
                "# 文档字符串里提到 --check-all 与 --fail-on-broken 也不算声明\n"
                'print("hello --check-all world")\n'
                "sys.exit(0)\n",
                encoding="utf-8",
            )
            self.assertEqual(parse(str(script)), set())


if __name__ == "__main__":
    unittest.main()
