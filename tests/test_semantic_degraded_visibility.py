"""语义检查降级可见性回归测试 (Phase 40, ADR-064)。

背景:
    ``checker._run_semantic_checks`` 原先在 tree-sitter 不可用时直接
    ``return issues``(空列表)。调用方无法区分"检查通过"与"检查根本没跑"
    —— 实测依赖缺失时 SemanticChecker 报 0 个问题、依赖齐全时报 54 个，
    输出看起来像"代码完美"，属典型 fail-open 假绿灯。

修复后不可用时产生一条 ``semantic-degraded`` Issue。

关键设计(实测得出, 见 ADR-064):
    严重度必须是 ``error``。因为 ``CheckResult.passed`` 只看
    ``error_count``(models.py:57), info 与 warning 都会被
    report_generator / quality_gate 渲染成 "PASS ✅", 等于把降级重新
    伪装成绿灯。

这些用例必须在**子进程**里跑, 且必须在导入检查器**之前**屏蔽包。
若在导入之后才屏蔽, 旧实现同样"通过", 测试就测不出真实缺陷
(Phase 38 变异测试已暴露过该方法论问题)。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_TREE_SITTER_PACKAGES = ["tree_sitter", "tree_sitter_python"]

_BLOCKER = '''
import sys

BLOCKED = {blocked!r}


class _BlockingFinder:
    """在模块被导入前拦截指定包, 模拟环境里未安装。"""

    def find_module(self, name, path=None):
        return self if name in BLOCKED else None

    def load_module(self, name):
        raise ImportError("simulated missing package: " + name)


sys.meta_path.insert(0, _BlockingFinder())
'''

_CLEAN_SOURCE = '"""M."""\n\n\ndef f() -> int:\n    """D."""\n    return 1\n'


def _run_probe(blocked: list[str], body: str) -> str:
    """在干净子进程中运行探针, 返回其标准输出。"""
    script = _BLOCKER.format(blocked=blocked) + textwrap.dedent(body)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
    )
    if result.returncode != 0:
        raise AssertionError(f"探针执行失败:\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def _probe_check_file(blocked: list[str]) -> dict[str, object]:
    """对临时 python 文件跑 check_file(semantic=True), 返回结构化结果。"""
    payload = _run_probe(
        blocked,
        f"""
        import json, tempfile, pathlib
        from tools.scripts.rules_engine.checker import check_file

        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "probe.py"
            f.write_text({_CLEAN_SOURCE!r})
            r = check_file(f, language="python", semantic=True)
            deg = [i for i in r.issues if i.rule_id == "semantic-degraded"]
            print("JSON:" + json.dumps({{
                "total": len(r.issues),
                "degraded": len(deg),
                "severity": deg[0].severity if deg else None,
                "passed": r.passed,
            }}))
        """,
    )
    line = next(ln for ln in payload.splitlines() if ln.startswith("JSON:"))
    result: dict[str, object] = json.loads(line[len("JSON:") :])
    return result


class DegradedVisibilityTest(unittest.TestCase):
    """tree-sitter 完全缺失时, 降级必须可见。"""

    def test_missing_tree_sitter_produces_degraded_issue(self) -> None:
        result = _probe_check_file(_TREE_SITTER_PACKAGES)
        self.assertEqual(
            result["degraded"],
            1,
            "tree-sitter 缺失时未产生 semantic-degraded —— 降级被静默吞掉了",
        )

    def test_degraded_issue_is_error_severity(self) -> None:
        """必须是 error: passed 只看 error_count, info/warning 会渲染成 PASS。"""
        result = _probe_check_file(_TREE_SITTER_PACKAGES)
        self.assertEqual(result["severity"], "error")

    def test_degraded_result_is_not_reported_as_passed(self) -> None:
        """降级不得让 passed=True —— 那正是要根除的假绿灯。"""
        result = _probe_check_file(_TREE_SITTER_PACKAGES)
        self.assertFalse(
            result["passed"],
            "降级时 CheckResult.passed 仍为 True, 报告层会渲染成 PASS",
        )

    def test_dependency_error_is_not_silently_ignored(self) -> None:
        """依赖缺失必须走 ImportError 分支并留痕, 不得 except: pass。

        直接阻断 ``semantic_rules`` 的导入来制造 ImportError —— 屏蔽
        ``json`` 之类的基础模块只会在导入检查器时就崩掉, 测不到目标分支
        (首次实现即踩此坑, 变异测试纠正)。
        """
        out = _run_probe(
            ["tools.scripts.rules_engine.semantic_rules"],
            """
            import sys, pathlib
            from tools.scripts.rules_engine.checker import _run_semantic_checks
            out = _run_semantic_checks(pathlib.Path("x.py"), "python")
            print("COUNT:", len(out))
            print("DEGRADED:", any(i.rule_id == "semantic-degraded" for i in out))
            """,
        )
        self.assertIn("DEGRADED: True", out)
        self.assertIn("COUNT: 1", out)

    def test_unexpected_exception_is_reported(self) -> None:
        """语义规则自身抛异常时必须留痕。

        覆盖 ``except Exception`` 分支 —— 该分支原先是 ``except: pass``,
        是"检查没跑成却什么都不说"的最后一道口子。此前无任何测试覆盖
        (grep '语义分析异常' 仅命中实现本身), Phase 40 补上。
        """
        script = textwrap.dedent(
            """
            import pathlib, tempfile
            import tools.scripts.rules_engine.checker as ck

            def _boom(*args, **kwargs):
                raise RuntimeError("规则内部炸了")

            import tools.scripts.rules_engine.semantic_rules as sr
            sr.run_semantic_rules = _boom
            with tempfile.TemporaryDirectory() as d:
                f = pathlib.Path(d) / "probe.py"
                f.write_text("x = 1\\n")
                out = ck._run_semantic_checks(f, "python")
            print("COUNT:", len(out))
            for i in out:
                if i.rule_id == "semantic-degraded":
                    print("MSG:", i.message)
            """
        )
        out = _run_probe([], script)
        self.assertIn("COUNT: 1", out, "语义规则抛异常时未产生降级 Issue")
        self.assertIn("语义分析异常", out, "异常类型未写入降级原因")
        self.assertIn("规则内部炸了", out, "原始异常信息未保留")


class HealthyPathTest(unittest.TestCase):
    """依赖齐全时不得产生任何降级 Issue (防回归)。"""

    def test_healthy_path_has_no_degraded_issue(self) -> None:
        out = _run_probe(
            [],
            f"""
            import tempfile, pathlib
            from tools.scripts.rules_engine.checker import check_file
            with tempfile.TemporaryDirectory() as d:
                f = pathlib.Path(d) / "probe.py"
                f.write_text({_CLEAN_SOURCE!r})
                r = check_file(f, language="python", semantic=True)
                print("DEGRADED:", any(i.rule_id == "semantic-degraded" for i in r.issues))
            """,
        )
        if "DEGRADED: False" not in out:
            self.skipTest("当前环境未安装 tree-sitter, 跳过正常路径断言")
        self.assertIn("DEGRADED: False", out)


class PartialLanguageTest(unittest.TestCase):
    """指定语言解析器缺失, 必须与"整个依赖缺失"区分开。"""

    def test_unknown_language_reports_distinct_reason(self) -> None:
        out = _run_probe(
            [],
            """
            import tempfile, pathlib
            from tools.scripts.rules_engine.checker import _run_semantic_checks
            with tempfile.TemporaryDirectory() as d:
                f = pathlib.Path(d) / "probe.xyz"
                f.write_text("nope\\n")
                out = _run_semantic_checks(f, "unknownlang")
                print("COUNT:", len(out))
                for i in out:
                    if i.rule_id == "semantic-degraded":
                        print("MSG:", i.message)
            """,
        )
        self.assertIn("COUNT: 1", out, "未知语言未产生降级 Issue")
        self.assertIn("解析器不可用", out, "未知语言应报告解析器不可用而非解析失败")


class HookPathTest(unittest.TestCase):
    """真实 hook 路径 (phase_runner._run_semantic_check) 必须可见且非零退出。"""

    # 只含一条赋值: 命中 0 条 regex 规则 (py-missing-all 之类只对
    # def/class/from 触发), 因此健康环境 exit=0。降级环境若仍 exit=0,
    # 就说明降级被伪装成了绿灯 —— 这正是本测试要卡住的行为。
    # 曾误用含 def 的探针文件, 那种文件无论是否降级都因 py-missing-all
    # 退出 1, 断言形同虚设 (变异测试暴露)。
    _CLEAN_PROBE = "X = 1\n"

    def test_hook_path_exits_nonzero_when_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "probe.py"
            f.write_text(self._CLEAN_PROBE)
            script = _BLOCKER.format(blocked=_TREE_SITTER_PACKAGES) + textwrap.dedent(
                """
                import sys
                from pathlib import Path
                from tools.scripts.hooks.phase_runner import _run_semantic_check
                code = _run_semantic_check(Path(sys.argv[1]), "python", 1)
                print("EXITCODE:", code)
                """
            )
            result = subprocess.run(
                [sys.executable, "-c", script, str(f)],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                timeout=300,
            )
        self.assertIn(
            "semantic-degraded",
            result.stdout,
            "真实 hook 路径看不到降级提示",
        )
        self.assertIn("EXITCODE: 1", result.stdout, "降级时 hook 未以非零码退出")

    def test_healthy_hook_path_exits_zero(self) -> None:
        """对照组: 依赖齐全时同一文件必须 exit=0, 证明退出码只由降级驱动。"""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "probe.py"
            f.write_text(self._CLEAN_PROBE)
            script = textwrap.dedent(
                """
                import sys
                from pathlib import Path
                from tools.scripts.hooks.phase_runner import _run_semantic_check
                code = _run_semantic_check(Path(sys.argv[1]), "python", 1)
                print("EXITCODE:", code)
                """
            )
            result = subprocess.run(
                [sys.executable, "-c", script, str(f)],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                timeout=300,
            )
        if "EXITCODE: 0" not in result.stdout:
            self.skipTest("当前环境未安装 tree-sitter, 跳过正常路径断言")
        self.assertIn("EXITCODE: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
