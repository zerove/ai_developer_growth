"""锁定覆盖率门禁的作用域。

本轮会话的核心失效模式：`tools/` 被测量，而承载全部
on_commit / on_pr / on_merge / scheduled hook 入口的 `.jcode/scripts`
完全在门禁之外——覆盖率劣化不触发任何报警。

两个执行点都必须同时测量两棵树：
- 本地 / pre-push：tools/scripts/hooks/basic_checks.py 构造 pytest 命令
- CI：.github/workflows/jobs/tests.yml 的两处 pytest 调用
  （分片与非分片各一处，漏掉任一处都会让 CI 与本地口径不一致）

实测两树合并约 86%，高于项目标准 80，因此按 80 把关而非降低阈值。
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
GATE_BUILDER = ROOT / "tools" / "scripts" / "hooks" / "basic_checks.py"
CI_TESTS = ROOT / ".github" / "workflows" / "jobs" / "tests.yml"

REQUIRED_TREES = ("--cov=tools/scripts", "--cov=.jcode/scripts")
# CI 用更宽的 --cov=tools（已包含 tools/scripts），两个执行点口径不同，
# 但都必须覆盖 .jcode/scripts —— hook 入口脚本历史上正是从这里掉的。
REQUIRED_CI_FLAGS = ("--cov=tools", "--cov=.jcode/scripts")
MIN_STANDARD = 80
MEASURED_WITH_BOTH = 86.0


def _config() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _built_pytest_args() -> list[str]:
    """实际调用 basic_checks.run_tests 并抓取它构造的 pytest 命令。"""
    import sys

    sys.path.insert(0, str(ROOT))
    from tools.scripts.hooks import basic_checks

    with (
        patch.object(basic_checks, "_run_subprocess", return_value=(True, "")) as run,
        patch.object(basic_checks.sys, "executable", "python"),
    ):
        basic_checks.run_tests()
    return list(run.call_args[0][0])


def _ci_coverage_invocations() -> list[str]:
    """权威 CI 门禁（jobs/tests.yml）里的 pytest --cov 调用。

    只扫这一个文件：`.github/workflows/example-ci-template.yml` 与
    `.github/ci-templates/` 是给**其他项目**用的模板，测的是它们自己的
    `--cov=src`，不适用本仓库口径，纳入扫描会误报。

    该文件的两个调用（分片/非分片）位于同一个 shell if/else 的折叠标量里，
    且被 YAML 换行续行拆开，因此按 `--cov=` 出现次数切分而非按 pytest 前缀。
    """
    text = CI_TESTS.read_text(encoding="utf-8")
    flags = re.findall(r"--cov=[A-Za-z0-9_./-]+", text)
    assert flags, "tests.yml 中未找到任何 --cov 调用"
    # 每两个相邻 flag（tools + .jcode/scripts）构成一次调用
    return [
        "pytest " + " ".join(flags[i : i + len(REQUIRED_CI_FLAGS)])
        for i in range(0, len(flags), len(REQUIRED_CI_FLAGS))
    ]


class TestLocalGateScope:
    def test_measures_both_trees(self) -> None:
        args = _built_pytest_args()
        for tree in REQUIRED_TREES:
            assert tree in args, f"本地门禁未测量 {tree}"

    def test_enforces_configured_threshold(self) -> None:
        args = _built_pytest_args()
        assert "--cov-fail-under" in args, "门禁必须带阈值"
        cov_min = _config()["tool"]["adg"]["cov_min"]
        assert str(cov_min) in args, "阈值未取自 pyproject 的 cov_min"

    def test_project_standard_not_lowered(self) -> None:
        cfg = _config()
        assert cfg["tool"]["adg"]["cov_min"] >= MIN_STANDARD
        assert cfg["tool"]["coverage"]["report"]["fail_under"] >= MIN_STANDARD

    def test_threshold_has_headroom_over_measured(self) -> None:
        """实测合并约 86%；阈值须留余量，又不得高到无法达成。"""
        cov_min = _config()["tool"]["adg"]["cov_min"]
        assert cov_min <= MEASURED_WITH_BOTH, "阈值高于实测值，门禁必然失败"


class TestCiGateScope:
    def test_ci_has_coverage_invocations(self) -> None:
        assert _ci_coverage_invocations(), "CI 中未找到任何 --cov 调用"

    @pytest.mark.parametrize("flag", REQUIRED_CI_FLAGS)
    def test_no_ci_invocation_omits_a_flag(self, flag: str) -> None:
        """只测一棵树的 CI 调用会造成口径漂移（.jcode/scripts 历史正是这样掉的）。"""
        offenders = [c for c in _ci_coverage_invocations() if flag not in c]
        assert not offenders, f"以下 CI 覆盖率调用缺少 {flag}: {offenders}"

    def test_both_sharded_and_plain_invocations_exist(self) -> None:
        """分片与非分片各一处；只改一处会让 CI 与本端口径不一致。"""
        assert len(_ci_coverage_invocations()) == 2

    def test_ci_reads_threshold_from_pyproject(self) -> None:
        text = CI_TESTS.read_text(encoding="utf-8")
        assert "fail_under" in text, "CI 阈值应从 pyproject 读取而非硬编码"

    def test_workflow_yaml_parses(self) -> None:
        data = yaml.safe_load(CI_TESTS.read_text(encoding="utf-8"))
        assert "jobs" in data and "test" in data["jobs"]

    def test_coverage_check_step_exists(self) -> None:
        data = yaml.safe_load(CI_TESTS.read_text(encoding="utf-8"))
        steps = data["jobs"]["test"]["steps"]
        assert any("coverage" in str(s.get("name", "")).lower() for s in steps), "缺少覆盖率校验步骤"


class TestBothTreesExist:
    def test_hook_entry_scripts_parse(self) -> None:
        scripts = sorted((ROOT / ".jcode" / "scripts").glob("*.py"))
        assert len(scripts) >= 10, "hook 入口脚本数量异常，--cov 路径可能已失效"
        for p in scripts:
            ast.parse(p.read_text(encoding="utf-8"))

    @pytest.mark.parametrize(
        "name",
        ["hooks_runner.py", "knowledge-curator.py", "governance-auditor.py", "context-sync.py"],
    )
    def test_named_entry_script_exists(self, name: str) -> None:
        assert (ROOT / ".jcode" / "scripts" / name).exists(), f"{name} 缺失，--cov 路径失效"
