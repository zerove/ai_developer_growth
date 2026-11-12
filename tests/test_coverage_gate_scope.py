"""锁定覆盖率门禁的作用域。

本轮会话的核心失效模式：`tools/` 被测量，而承载全部
on_commit / on_pr / on_merge / scheduled hook 入口的 `.jcode/scripts`
完全在门禁之外——覆盖率劣化不触发任何报警。

两个执行点都必须同时测量两棵树：
- 本地 / pre-push：tools/scripts/hooks/basic_checks.py 构造 pytest 命令
- CI：.github/workflows/jobs-tests.yml 的 pytest 调用

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
CI_TESTS = ROOT / ".github" / "workflows" / "jobs-tests.yml"
COMBINE_COVERAGE = ROOT / ".github" / "workflows" / "jobs-combine-coverage.yml"

REQUIRED_TREES = ("--cov=tools", "--cov=.jcode/scripts")
# 本地与 CI 已统一为 --cov=tools。此前本地用 --cov=tools/scripts, 把
# tools/ 下 9 个子包排除在度量外, 本地看到的覆盖率因此偏高; CI 虽测全,
# 但开发者日常先看本地门禁, 那 4 个子包缺陷正是在这层差异下溜过去的。
# .jcode/scripts 仍须显式声明 —— hook 入口脚本历史上正是从这里掉的。
REQUIRED_CI_FLAGS = ("--cov=tools", "--cov=.jcode/scripts")
MIN_STANDARD = 80
MEASURED_WITH_BOTH = 86.0
BRANCH_MIN_STANDARD = 75
MEASURED_BRANCH = 81.2


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
    """权威 CI 门禁（jobs-tests.yml）里的 pytest --cov 调用。

    只扫这一个文件：`.github/workflows/example-ci-template.yml` 与
    `.github/ci-templates/` 是给**其他项目**用的模板，测的是它们自己的
    `--cov=src`，不适用本仓库口径，纳入扫描会误报。

    调用可能被 YAML 折行拆开，因此按 `--cov=` 出现次数切分而非按 pytest 前缀。
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
        # cov_min 是唯一来源: 本地由 --cov-fail-under 读它, CI 的 coverage-config
        # 步骤读同一键。曾在此重复断言 [tool.coverage.report].fail_under, 但两份
        # 副本可各自漂移, 故已删除后者。
        assert "fail_under" not in cfg["tool"]["coverage"]["report"], "覆盖率阈值只应在 [tool.adg].cov_min 定义一处"

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

    def test_single_full_invocation_exists(self) -> None:
        """分片已移除；只保留一次全量调用，避免 CI 重复跑同一套测试。"""
        assert len(_ci_coverage_invocations()) == 1

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


class TestCoverageArtifactHandoff:
    """覆盖率数据必须真的从 test 作业传到 combine 作业。

    历史失效形态: upload-artifact v4 默认跳过隐藏文件, 而 `.coverage` 正是
    隐藏文件 → 上传步骤显示**成功**但零文件; combine 作业随后在另一个 job
    里报 "Couldn't combine from non-existent path"。根因与症状隔了两层,
    表现为"测试全绿却挂了个看不懂的覆盖率作业"。
    """

    def _coverage_upload_step(self) -> dict:
        data = yaml.safe_load(CI_TESTS.read_text(encoding="utf-8"))
        steps = data["jobs"]["test"]["steps"]
        uploads = [s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact")]
        coverage_uploads = [s for s in uploads if "coverage" in str(s.get("name", "")).lower()]
        assert len(coverage_uploads) == 1, f"应有且仅有一个覆盖率上传步骤: {coverage_uploads}"
        return coverage_uploads[0]

    def test_hidden_coverage_file_is_included(self) -> None:
        step = self._coverage_upload_step()
        assert step["with"].get("include-hidden-files") is True, (
            ".coverage 是隐藏文件, upload-artifact 默认跳过 → 必须显式 include-hidden-files"
        )

    def test_missing_coverage_fails_loudly(self) -> None:
        step = self._coverage_upload_step()
        assert step["with"].get("if-no-files-found") == "error", "覆盖率数据缺失必须当场失败, 不能静默上传空集"

    def test_combine_does_not_use_globstar_pattern(self) -> None:
        text = COMBINE_COVERAGE.read_text(encoding="utf-8")
        assert "coverage combine coverage-artifacts/**/.coverage" not in text, (
            "bash 未开启 globstar 时 `**` 等价于 `*`, 该路径会静默失配"
        )
        assert "未下载到任何覆盖率数据" in text, "combine 缺少数据时必须显式报错"


class TestBranchCoverageGate:
    def test_branch_measurement_enabled(self) -> None:
        cfg = _config()
        assert cfg["tool"]["coverage"]["run"]["branch"] is True

    def test_branch_threshold_configured(self) -> None:
        cfg = _config()
        branch_min = cfg["tool"]["adg"]["branch_cov_min"]
        assert branch_min >= BRANCH_MIN_STANDARD
        assert branch_min <= MEASURED_BRANCH, "分支阈值高于实测值，门禁必然失败"

    def test_ci_reads_and_enforces_branch_threshold(self) -> None:
        text = CI_TESTS.read_text(encoding="utf-8")
        assert "branch_cov_min" in text
        assert "branch_fail_under" in text
        assert "branch-rate" in text
        assert "Branch coverage" in text

    def test_combine_reads_and_enforces_branch_threshold(self) -> None:
        text = COMBINE_COVERAGE.read_text(encoding="utf-8")
        assert "branch_cov_min" in text
        assert "branch_fail_under" in text
        assert "branch-rate" in text
        assert "Combined branch coverage" in text

    def test_combine_workflow_yaml_parses(self) -> None:
        data = yaml.safe_load(COMBINE_COVERAGE.read_text(encoding="utf-8"))
        assert "jobs" in data and "combine-coverage" in data["jobs"]


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


class TestGatePluginsDeclared:
    """门禁依赖的 pytest 插件必须在开发依赖中声明。

    test_reruns=2 此前因 pytest-rerunfailures 未被声明为依赖而完全失效：
    basic_checks._plugin_available 返回 False → 命令里不加 --reruns →
    注释宣称的"flaky 重试次数 2"从未生效，偶发测试直接挂门禁。
    """

    @pytest.mark.parametrize(
        ("plugin", "dist"),
        [
            ("pytest_rerunfailures", "pytest-rerunfailures"),
            ("pytest_cov", "pytest-cov"),
            ("xdist", "pytest-xdist"),
        ],
    )
    def test_plugin_is_declared_in_dev_deps(self, plugin: str, dist: str) -> None:
        cfg = _config()
        dev = cfg["project"]["optional-dependencies"]["dev"]
        assert any(d.startswith(dist) for d in dev), f"{dist} 未在 dev 依赖中声明，{plugin} 不可用"

    def test_reruns_setting_is_not_silently_ignored(self) -> None:
        """test_reruns > 0 时，插件必须真的可用，否则配置形同虚设。"""
        cfg = _config()
        reruns = cfg["tool"]["adg"]["test_reruns"]
        if reruns <= 0:
            pytest.skip("已显式禁用重试")
        import pytest_rerunfailures  # noqa: F401

    def test_requirements_dev_also_declares_it(self) -> None:
        text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        assert "pytest-rerunfailures" in text, "requirements-dev.txt 缺 pytest-rerunfailures"
