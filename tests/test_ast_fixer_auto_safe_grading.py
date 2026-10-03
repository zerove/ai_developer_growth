"""auto_safe 分级回归测试 (ADR-067).

背景 (实测):
ADR-066 让 ``ASTFixer.fix_file`` 真正写盘后, 此前不可达的
``auto_safe`` 标记问题立即显现:
``ast-fix --path tools/scripts --dry-run`` 报出 **204 处 auto-safe
修复**, 抽样查看全部是 ``fix-empty-except``, 其替换内容为

    pass  ->  pass  # TODO: Handle this exception

该规则只插入 ``# TODO`` 注释, **标记**问题而非**修复**问题,
降低代码质量。修复前不写盘, 204 处注入根本不会发生。

ADR-067 将其降级为 ``auto_safe=False``, 实测真实代码库
auto-safe 修复从 204 降到 2, 而 25 处 ``fix-empty-except``
仍被报告, 交人工决定。

分级原则:
``auto_safe`` 只授予"语义等价且质量提升"的改写, 不授予
"仅仅是把问题标出来"的建议。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.scripts.rules_engine.ast_fixer import ASTFixer

REPO_ROOT = Path(__file__).resolve().parent.parent

# 裸 except + pass: 同时触发 fix-bare-except(安全) 与
# fix-empty-except(不安全, 仅插 TODO) 两条规则, 便于对比分级
BARE_EXCEPT_SRC = '"""M."""\n\n\ndef f():\n    """D."""\n    try:\n        pass\n    except:\n        pass\n'

TODO_MARKER = "TODO: Handle this exception"


def _write(path: Path, src: str) -> Path:
    path.write_text(src, encoding="utf-8")
    return path


def _fix(target: Path) -> object:
    report = ASTFixer().fix_file(target, dry_run=False)
    assert report is not None
    return report


class TestAutoSafeGrading:
    """核心回归: auto_safe 只给语义安全改写."""

    def test_empty_except_is_not_auto_safe(self, tmp_path: Path) -> None:
        """fix-empty-except 必须是 auto_safe=False."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = _fix(target)

        empty_except = [f for f in report.fixes if f.rule_id == "fix-empty-except"]  # type: ignore[attr-defined]
        assert empty_except, "探针未触发 fix-empty-except —— 变量没被隔离"
        for fix in empty_except:
            assert fix.auto_safe is False, "fix-empty-except 被标为 auto_safe —— 会批量注入 # TODO"

    def test_bare_except_remains_auto_safe(self, tmp_path: Path) -> None:
        """对照组: 真正的语义安全改写必须仍是 auto_safe.

        except: -> except Exception: 是语义等价改写, 不降低质量,
        降级它会让工具失去唯一有价值的自动修复能力。
        """
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = _fix(target)

        bare_except = [f for f in report.fixes if f.rule_id == "fix-bare-except"]  # type: ignore[attr-defined]
        assert bare_except, "探针未触发 fix-bare-except —— 变量没被隔离"
        for fix in bare_except:
            assert fix.auto_safe is True, "fix-bare-except 被误降级 —— 真正的语义安全改写"

    def test_unsafe_fix_never_reaches_disk(self, tmp_path: Path) -> None:
        """端到端核心断言: # TODO 绝不落盘."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        _fix(target)

        on_disk = target.read_text(encoding="utf-8")
        assert TODO_MARKER not in on_disk, "非 auto_safe 的 # TODO 注入仍写入了磁盘"

    def test_safe_fix_still_lands_on_disk(self, tmp_path: Path) -> None:
        """对照组: 降级不应连累真正的修复 —— except Exception 必须落盘."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        _fix(target)

        on_disk = target.read_text(encoding="utf-8")
        assert "except Exception:" in on_disk, "auto_safe 修复未落盘 —— 降级过头了"
        assert "\n    except:" not in on_disk

    def test_unsafe_fix_still_reported(self, tmp_path: Path) -> None:
        """降级不等于隐藏 —— 仍须出现在报告里供人工决定."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = _fix(target)

        empty_except = [f for f in report.fixes if f.rule_id == "fix-empty-except"]  # type: ignore[attr-defined]
        assert report.total_fixes >= 2, "降级后不应丢失发现能力"
        assert empty_except, "降级后 fix-empty-except 不再被报告"


class TestGradingEndToEnd:
    """端到端: CLI 行为必须与分级一致."""

    def test_cli_does_not_inject_todo(self, tmp_path: Path) -> None:
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "scripts" / "hooks_runner.py"),
                "ast-fix",
                "--path",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
            check=False,
            env={**os.environ},
        )

        on_disk = target.read_text(encoding="utf-8")
        assert TODO_MARKER not in on_disk, f"CLI 注入了 # TODO:\n{proc.stdout}\n磁盘:\n{on_disk}"
        assert "except Exception:" in on_disk, f"CLI 未应用真正的修复:\n{proc.stdout}"

    def test_cli_only_marks_auto_safe_rules(self, tmp_path: Path) -> None:
        """CLI 的 [AUTO] 段不得包含 fix-empty-except."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "scripts" / "hooks_runner.py"),
                "ast-fix",
                "--path",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
            check=False,
            env={**os.environ},
        )

        auto_lines = [line for line in proc.stdout.splitlines() if line.startswith("[AUTO]")]
        assert auto_lines, f"预期有 auto_safe 修复:\n{proc.stdout}"
        assert not any("fix-empty-except" in line for line in auto_lines), (
            f"fix-empty-except 出现在 [AUTO] 段:\n{proc.stdout}"
        )
