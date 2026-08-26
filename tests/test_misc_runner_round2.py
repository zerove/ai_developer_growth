"""hooks/misc_runner.py 第二轮攻坚: exception 全子命令/dep-graph 四动作/learn/dashboard/docs_validate。

覆盖第二轮缺口(35%→65%+):
- _exception_review(approve/reject/revoke × 成功/失败)
- _exception_list(空/多状态/带过期)
- _exception_check_expirations / _exception_sync_gitops
- _handle_exception 分发(audit/unknown)
- _dep_graph_analyze(tree/json/graphviz/mermaid + output 文件)
- _dep_graph_circular / conflicts / impact(命中与未命中)
- _dep_graph_build / _handle_learn / _handle_dashboard / _handle_docs_validate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.dependency_graph import CircularDependency, DependencyConflict, DependencyGraph, ImpactAnalysis
from tools.scripts.exception_manager import ExceptionStatus
from tools.scripts.hooks import misc_runner as mr


def make_args(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "path": Path("."),
        "exception_action": "request",
        "dep_graph_action": "analyze",
        "format": "tree",
        "output": None,
        "max_depth": 5,
        "pre_push": False,
        "pre_commit": False,
        "port": 8000,
        "db": None,
        "retention_days": 90,
        "status": None,
        "package": None,
        "version": None,
    }
    base.update(kw)
    return argparse.Namespace(**base)  # type: ignore[arg-type]


def make_req(status: ExceptionStatus = ExceptionStatus.PENDING, expires: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="req1",
        rule_id="R1",
        paths=["a.py"],
        reason="why",
        severity="warning",
        requested_severity="info",
        expires=expires,
        created_by="me",
        created_at="2026-08-26T00:00:00",
        status=status,
    )


class TestExceptionReview:
    def _manager(self, ok: bool) -> MagicMock:
        m = MagicMock()
        m.approve_exception.return_value = ok
        m.reject_exception.return_value = ok
        m.revoke_exception.return_value = ok
        return m

    @pytest.mark.parametrize("action,method", [("approve", "approve_exception"), ("reject", "reject_exception")])
    def test_approve_reject_ok(self, action: str, method: str, capsys: pytest.CaptureFixture[str]) -> None:
        args = make_args(request_id="req1", reviewer="bob", comment="ok")
        rc = mr._exception_review(self._manager(True), args, action)
        assert rc == 0 and "req1" in capsys.readouterr().out

    def test_revoke_ok_and_fail(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = make_args(request_id="req1")
        assert mr._exception_review(self._manager(True), args, "revoke") == 0
        assert mr._exception_review(self._manager(False), args, "revoke") == 1

    @pytest.mark.parametrize("action", ["approve", "reject"])
    def test_review_failure_message(self, action: str, capsys: pytest.CaptureFixture[str]) -> None:
        args = make_args(request_id="req1", reviewer="bob", comment="")
        assert mr._exception_review(self._manager(False), args, action) == 1
        assert "❌" in capsys.readouterr().out


class TestExceptionList:
    def test_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.approval.list_requests.return_value = []
        assert mr._exception_list(m, make_args()) == 0
        assert "No exception" in capsys.readouterr().out

    def test_with_status_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.approval.list_requests.return_value = [
            make_req(ExceptionStatus.APPROVED),
            make_req(ExceptionStatus.REJECTED),
            make_req(expires="2026-09-01"),
        ]
        args = make_args(status=None)
        assert mr._exception_list(m, args) == 0
        out = capsys.readouterr().out
        assert "req1" in out and "Expires: 2026-09-01" in out


class TestCheckExpirations:
    def test_no_alerts(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.check_expirations.return_value = []
        assert mr._exception_check_expirations(m) == 0
        assert "No exceptions expiring" in capsys.readouterr().out

    def test_alerts(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.check_expirations.return_value = [
            SimpleNamespace(days_until_expiry=7, request_id="req1", rule_id="R1", expires_at="2026-09-02")
        ]
        assert mr._exception_check_expirations(m) == 0
        assert "[7d]" in capsys.readouterr().out


class TestSyncGitops:
    def test_not_configured(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.gitops = None
        assert mr._exception_sync_gitops(m) == 1
        assert "not configured" in capsys.readouterr().out

    def test_sync_success_and_fail(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.get_all_requests.return_value = []
        m.gitops.sync_to_git.return_value = True
        assert mr._exception_sync_gitops(m) == 0
        m.gitops.sync_to_git.return_value = False
        assert mr._exception_sync_gitops(m) == 1


class TestHandleExceptionDispatch:
    def test_audit_action(self, capsys: pytest.CaptureFixture[str]) -> None:
        m = MagicMock()
        m.generate_audit_report.return_value = {"total": 3}
        with patch.object(mr, "_make_exception_manager", return_value=m):
            rc = mr._handle_exception(make_args(exception_action="audit"))
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["total"] == 3

    def test_unknown_action(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(mr, "_make_exception_manager", return_value=MagicMock()):
            assert mr._handle_exception(make_args(exception_action="bogus")) == 1

    @pytest.mark.parametrize("action,fn", [("request", "request"), ("list", "list")])
    def test_dispatch_to_handlers(self, action: str, fn: str) -> None:
        with (
            patch.object(mr, "_make_exception_manager", return_value=MagicMock()),
            patch.object(mr, f"_exception_{fn}", MagicMock(return_value=0)) as mocked,
        ):
            assert mr._handle_exception(make_args(exception_action=action)) == 0
        mocked.assert_called_once()


def make_graph(
    *, cycles: list[CircularDependency] | None = None, conflicts: list[DependencyConflict] | None = None
) -> MagicMock:
    g = MagicMock(spec=DependencyGraph)
    g.to_json.return_value = '{"nodes": []}'
    g.export_graphviz.return_value = "digraph {}"
    g.export_mermaid.return_value = "graph TD"
    g.get_dependency_tree.return_value = {"root": {}}
    g.detect_circular_dependencies.return_value = cycles or []
    g.detect_conflicts.return_value = conflicts or []
    return g


class TestDepGraphAnalyze:
    @pytest.mark.parametrize("fmt", ["json", "graphviz", "mermaid"])
    def test_formats_stdout(self, fmt: str, capsys: pytest.CaptureFixture[str]) -> None:
        assert mr._dep_graph_analyze(make_graph(), make_args(format=fmt)) == 0
        assert capsys.readouterr().out.strip()

    def test_tree_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert mr._dep_graph_analyze(make_graph(), make_args(format="tree")) == 0
        assert '"root"' in capsys.readouterr().out

    @pytest.mark.parametrize("fmt", ["json", "mermaid"])
    def test_output_file(self, fmt: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out = tmp_path / "g.out"
        assert mr._dep_graph_analyze(make_graph(), make_args(format=fmt, output=out)) == 0
        assert out.exists() and out.stat().st_size > 0


class TestDepGraphCircularConflicts:
    def test_circular_clean(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert mr._dep_graph_circular(make_graph(), make_args(output=None)) == 0
        assert "No circular" in capsys.readouterr().out

    def test_circular_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        cyc = [CircularDependency(cycle=["a", "b"], ecosystems=["pypi"], severity="error")]
        assert mr._dep_graph_circular(make_graph(cycles=cyc), make_args()) == 1
        assert "a -> b" in capsys.readouterr().out

    def test_conflicts_clean(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert mr._dep_graph_conflicts(make_graph(), make_args()) == 0
        assert "No version conflicts" in capsys.readouterr().out

    def test_conflicts_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        conf = [DependencyConflict(package_name="p", versions={"1.0": ["x"], "2.0": ["y"]})]
        assert mr._dep_graph_conflicts(make_graph(conflicts=conf), make_args()) == 1
        assert "'1.0', '2.0'" in capsys.readouterr().out or "1.0" in capsys.readouterr().out


class TestDepGraphImpact:
    def _impact(self) -> ImpactAnalysis:
        return ImpactAnalysis(
            package="p",
            version="1.0",
            direct_dependents=["x"],
            transitive_dependents=["y"],
            total_affected=2,
            critical_path=["root", "x", "p"],
        )

    def test_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        g = make_graph()
        g.analyze_impact.return_value = []
        assert mr._dep_graph_impact(g, make_args(package="ghost")) == 1
        assert "not found" in capsys.readouterr().out

    def test_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        g = make_graph()
        g.analyze_impact.return_value = [self._impact()]
        assert mr._dep_graph_impact(g, make_args(package="p")) == 0
        out = capsys.readouterr().out
        assert "Direct dependents: 1" in out and "Critical path" in out


class TestBuildAndLearnAndDashboard:
    def test_dep_graph_build(self, tmp_path: Path) -> None:
        scanner = MagicMock()
        scanner.generate_sbom.return_value = SimpleNamespace(packages=[])
        graph = MagicMock(spec=DependencyGraph)
        with (
            patch.object(mr, "SupplyChainScanner", return_value=scanner),
            patch.object(mr, "analyze_dependency_graph", return_value=graph) as ana,
        ):
            assert mr._dep_graph_build(tmp_path) is graph
        ana.assert_called_once()

    def test_learn_stdout_and_yaml(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out_file = tmp_path / "rules.yaml"
        result = {"rules": [{"id": "R1"}]}
        with (
            patch("tools.scripts.rules_engine.ai_rules_generator.analyze_project", return_value=result),
            patch(
                "tools.scripts.rules_engine.ai_rules_generator.format_analysis",
                return_value="ANALYSIS",
            ) as fmt,
        ):
            rc = mr._handle_learn(make_args(project_path=tmp_path))
            assert rc == 0
            assert mr._handle_learn(make_args(project_path=tmp_path, output=out_file)) == 0
        assert fmt.call_count == 2
        out = capsys.readouterr().out  # readouterr 会排空缓冲，只读一次
        assert "ANALYSIS" in out
        assert "Rules written" in out
        assert out_file.exists()

    def test_dashboard_runs_uvicorn(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        app = MagicMock()
        uvicorn = MagicMock()
        with (
            patch.dict("sys.modules", {"uvicorn": uvicorn}),
            patch("tools.scripts.rules_engine.dashboard.create_app", return_value=app),
            patch("tools.scripts.app_config.get_path", lambda k, d: d),
        ):
            rc = mr._handle_dashboard(make_args(port=9999))
        assert rc == 0
        uvicorn.run.assert_called_once()
        assert "9999" in capsys.readouterr().out


class TestDocsValidate:
    def test_return_code_passthrough(self) -> None:
        proc = MagicMock(returncode=0, stdout="OK", stderr="")
        with patch.object(mr.subprocess, "run", return_value=proc) as run:
            assert mr._handle_docs_validate(make_args(action2="validate")) == 0
        run.assert_called_once()

    def test_failure_and_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        proc = MagicMock(returncode=2, stdout="", stderr="bad docs")
        with patch.object(mr.subprocess, "run", return_value=proc):
            assert mr._handle_docs_validate(make_args(action2="full")) == 2
        # 源码用 print 输出 stderr 内容 → 实际落在 stdout 捕获里
        assert "bad docs" in capsys.readouterr().out
