"""license_review 成因归因测试 (supply_runner._attribute_license_review)。

独立成文件的原因: 追加进 test_supply_runner_round2.py 会触发测试文件
500 行上限守卫 (test_test_file_size), 且归因是独立特性, 值得单独契约。

归因设计背景见 supply_runner._attribute_license_review docstring:
待复核许可证混合三种成因 (copyleft / PyPI 元数据不可达 / 许可证确实未声明),
摘要必须显式区分后两者, 否则网络抖动会被误读成"依赖许可证有问题"。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tools.scripts.hooks import supply_runner as sr
from tools.scripts.supply_chain import ScanResult


def make_dep(name: str, ecosystem: str = "pypi", license_: str | None = None):
    from tools.scripts.supply_chain import Dependency

    return Dependency(name=name, version="1.0.0", ecosystem=ecosystem, license=license_)


def _mixed_client() -> MagicMock:
    """按包名区分成因: flaky-pkg 不可达 / gone-pkg 不存在 / known-pkg 可达但无许可证。"""
    client = MagicMock()
    client.metadata.side_effect = lambda name: {"info": {}} if name == "known-pkg" else None
    client.package_missing.side_effect = lambda name: name == "gone-pkg"
    client.license_of.return_value = None
    return client


def _summary_with_attribution(**extra: int) -> dict[str, int]:
    base = {
        "total_dependencies": 2,
        "direct_dependencies": 2,
        "vulnerabilities": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "license_issues": 0,
        "license_review": 2,
        "license_review_unreachable": 1,
        "license_review_unknown": 1,
    }
    base.update(extra)
    return base


class TestLicenseReviewAttribution:
    """license_review 成因归因: 元数据不可达 vs 许可证确实未声明/未知。"""

    def test_attribution_splits_causes(self) -> None:
        deps = [
            make_dep("flaky-pkg"),
            make_dep("gone-pkg"),
            make_dep("known-pkg"),
            make_dep("mit-pkg", license_="MIT"),  # 已知许可证, 不参与归因
            make_dep("npm-pkg", ecosystem="npm"),  # 非 PyPI, 不参与归因
        ]
        result = ScanResult(project_path="/tmp/p", dependencies=deps, summary={})
        sr._attribute_license_review(result, _mixed_client())
        assert result.summary["license_review_unreachable"] == 1
        assert result.summary["license_review_unknown"] == 2

    def test_resolve_licenses_writes_attribution(self) -> None:
        """补齐许可证后, 摘要必须带上成因统计键 (即使全为 0)。"""
        dep = make_dep("flaky-pkg")
        result = ScanResult(project_path="/tmp/p", dependencies=[dep], summary={})
        scanner = MagicMock()
        scanner.license_checker.evaluate_dependencies.return_value = (
            [],
            ["REVIEW needed: flaky-pkg@1.0.0 (None)"],
        )
        sr._resolve_licenses(scanner, result, _mixed_client())
        assert result.summary["license_review_unreachable"] == 1
        assert result.summary["license_review_unknown"] == 0

    def test_scan_text_prints_attribution(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = ScanResult(project_path="/tmp/p", summary=_summary_with_attribution())
        sr._print_scan_text(Path("/tmp/p"), result)
        out = capsys.readouterr().out
        assert "待复核许可证: 2" in out
        assert "PyPI 元数据不可达: 1" in out
        assert "许可证未声明/未知: 1" in out

    def test_scan_text_no_attribution_without_keys(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = ScanResult(
            project_path="/tmp/p",
            summary=_summary_with_attribution(
                **{
                    "license_review_unreachable": 0,
                    "license_review_unknown": 0,
                }
            ),
        )
        sr._print_scan_text(Path("/tmp/p"), result)
        out = capsys.readouterr().out
        assert "元数据不可达" not in out

    def test_compliance_text_prints_attribution(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        compliance = sr._run_compliance_checks(
            tmp_path, ScanResult(project_path=str(tmp_path), summary=_summary_with_attribution())
        )
        sr._print_compliance_text(tmp_path, compliance)
        out = capsys.readouterr().out
        assert "待复核许可证 (license_review): 2" in out
        assert "PyPI 元数据不可达: 1" in out
        assert "许可证未声明/未知: 1" in out

    def test_compliance_text_silent_when_no_review(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        compliance = sr._run_compliance_checks(tmp_path, ScanResult(project_path=str(tmp_path), summary={}))
        sr._print_compliance_text(tmp_path, compliance)
        out = capsys.readouterr().out
        assert "待复核许可证" not in out

    def test_ledger_items_capture_cause_and_fields(self) -> None:
        """复核台账项应逐条带出依赖标识、许可证与成因 (机器可读盘点)。"""
        from tools.scripts.supply_chain import LicensePolicy

        deps = [
            make_dep("flaky-pkg"),
            make_dep("gone-pkg"),
            make_dep("copyleft-pkg", license_="GPL-3.0"),
            make_dep("mit-pkg", license_="MIT"),  # ALLOW, 不入台账
        ]
        # simulate post-evaluation state
        deps[0].license_policy = LicensePolicy.REVIEW
        deps[1].license_policy = LicensePolicy.REVIEW
        deps[2].license_policy = LicensePolicy.REVIEW
        deps[3].license_policy = LicensePolicy.ALLOW
        result = ScanResult(project_path="/tmp/p", dependencies=deps, summary={})
        sr._attribute_license_review(result, _mixed_client())

        items = result.summary["license_review_items"]
        assert isinstance(items, list) and len(items) == 3
        by_name = {it["name"]: it for it in items}
        assert by_name["flaky-pkg"]["cause"] == "unreachable"
        assert by_name["gone-pkg"]["cause"] == "unknown_license"
        assert by_name["copyleft-pkg"]["cause"] == "policy_review"
        for name in ("flaky-pkg", "gone-pkg", "copyleft-pkg"):
            it = by_name[name]
            assert it["ecosystem"] == "pypi"
            assert it["policy"] == "review"
            assert "REVIEW needed:" in str(it["message"])
            assert it["version"] == "1.0.0"

    def test_compliance_summary_includes_ledger_items(self, tmp_path: Path) -> None:
        """compliance 输出应透出 license_review_items (随 summary 供周期盘点)。"""
        from tools.scripts.supply_chain import LicensePolicy

        dep = make_dep("flaky-pkg")
        dep.license_policy = LicensePolicy.REVIEW
        result = ScanResult(project_path=str(tmp_path), dependencies=[dep], summary={})
        sr._attribute_license_review(result, _mixed_client())
        compliance = sr._run_compliance_checks(tmp_path, result)
        items = compliance["summary"]["license_review_items"]
        assert len(items) == 1
        assert items[0]["cause"] == "unreachable"

    def test_write_review_ledger_outputs_json(self, tmp_path: Path) -> None:
        """--review-ledger 应输出可用于周期盘点的台账 JSON。"""
        out = tmp_path / "license-review-ledger.json"
        args = SimpleNamespace(review_ledger=out)
        summary = _summary_with_attribution()
        summary["license_review_items"] = [
            {"name": "flaky-pkg", "version": "1.0.0", "ecosystem": "pypi", "license": None, "cause": "unreachable"}
        ]
        sr._write_review_ledger(args, tmp_path, "2026-11-13T00:00:00", summary)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["project"] == str(tmp_path)
        assert data["scanned_at"] == "2026-11-13T00:00:00"
        assert data["summary"]["license_review"] == 2
        assert data["summary"]["total_items"] == 1
        assert data["items"][0]["name"] == "flaky-pkg"

    def test_output_compliance_writes_ledger(self, tmp_path: Path) -> None:
        """compliance 输出路径应同时落盘复核台账。"""
        out = tmp_path / "ledger.json"
        compliance = sr._run_compliance_checks(
            tmp_path, ScanResult(project_path=str(tmp_path), summary=_summary_with_attribution())
        )
        compliance["scanned_at"] = "2026-11-13T00:00:00"
        args = SimpleNamespace(format="text", output=None, review_ledger=out)
        sr._output_compliance(args, tmp_path, compliance)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["summary"]["license_review"] == 2
        assert isinstance(data["items"], list)

    def test_diff_review_ledger_detects_added_removed_changed(self, tmp_path: Path) -> None:
        """ledger diff 应识别新增/移除/变更项 (按 ecosystem,name,version 键)。"""
        baseline = [
            {
                "ecosystem": "pypi",
                "name": "a",
                "version": "1",
                "license": None,
                "cause": "unreachable",
                "policy": "review",
                "message": "m1",
            },
            {
                "ecosystem": "pypi",
                "name": "b",
                "version": "1",
                "license": "GPL-3.0",
                "cause": "policy_review",
                "policy": "review",
                "message": "m2",
            },
            {
                "ecosystem": "pypi",
                "name": "c",
                "version": "1",
                "license": None,
                "cause": "unknown_license",
                "policy": "review",
                "message": "m3",
            },
        ]
        current = [
            {
                "ecosystem": "pypi",
                "name": "b",
                "version": "1",
                "license": "GPL-3.0",
                "cause": "unknown_license",
                "policy": "review",
                "message": "m2b",
            },
            {
                "ecosystem": "pypi",
                "name": "c",
                "version": "1",
                "license": None,
                "cause": "unknown_license",
                "policy": "review",
                "message": "m3",
            },
            {
                "ecosystem": "pypi",
                "name": "d",
                "version": "2",
                "license": None,
                "cause": "unreachable",
                "policy": "review",
                "message": "m4",
            },
        ]
        diff = sr._diff_review_ledger(current, baseline, tmp_path / "base.json")
        assert diff["summary"] == {"added": 1, "removed": 1, "changed": 1, "unchanged": 1}
        assert [it["name"] for it in diff["added"]] == ["d"]
        assert [it["name"] for it in diff["removed"]] == ["a"]
        assert diff["changed"][0]["from"]["name"] == "b"

    def test_compute_review_ledger_diff_reads_baseline_file(self, tmp_path: Path) -> None:
        """--review-ledger-baseline 应加载基线并将 diff 写入 summary。"""
        baseline = {
            "items": [
                {
                    "ecosystem": "pypi",
                    "name": "gone",
                    "version": "1.0.0",
                    "license": None,
                    "cause": "unknown_license",
                    "policy": "review",
                    "message": "m",
                }
            ]
        }
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
        summary = _summary_with_attribution()
        summary["license_review_items"] = [
            {
                "ecosystem": "pypi",
                "name": "new",
                "version": "1.0.0",
                "license": None,
                "cause": "unreachable",
                "policy": "review",
                "message": "m",
            }
        ]
        args = SimpleNamespace(review_ledger=None, review_ledger_baseline=baseline_path)
        diff = sr._compute_review_ledger_diff(args, summary)
        assert diff is not None
        assert diff["summary"]["added"] == 1
        assert diff["summary"]["removed"] == 1
        assert summary["license_review_diff"]["summary"]["unchanged"] == 0

    def test_write_review_ledger_includes_diff(self, tmp_path: Path) -> None:
        """ledger JSON 在提供基线时应包含 diff 段。"""
        out = tmp_path / "ledger.json"
        args = SimpleNamespace(review_ledger=out)
        summary = _summary_with_attribution()
        diff = {
            "summary": {"added": 1, "removed": 0, "changed": 0, "unchanged": 0},
            "added": [],
            "removed": [],
            "changed": [],
        }
        sr._write_review_ledger(args, tmp_path, "2026-11-13T00:00:00", summary, diff)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["diff"]["summary"]["added"] == 1

    def test_review_new_failures_counts_added(self) -> None:
        """ratchet 仅统计新增项 (added)。"""
        assert sr._review_new_failures(None) == 0
        assert sr._review_new_failures({"summary": {"added": 2, "removed": 1, "changed": 3}}) == 2
        assert sr._review_new_failures({"summary": {}}) == 0

    def test_scan_fail_on_review_new_blocks_added(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """scan + --fail-on-review-new: 基线出现新增待复核项时必须失败。"""
        import argparse

        args = argparse.Namespace(
            path=tmp_path,
            fail_on="high",
            format="text",
            output=None,
            policy_file=None,
            review_ledger=None,
            review_ledger_baseline=tmp_path / "base.json",
            fail_on_review_new=True,
        )
        result = ScanResult(project_path=str(tmp_path), summary=_summary_with_attribution())
        scanner = MagicMock()
        scanner.scan_project.return_value = result
        monkeypatch.setattr(sr, "SupplyChainScanner", lambda **_: scanner)
        monkeypatch.setattr(sr, "_output_scan_result", lambda *a, **k: None)
        monkeypatch.setattr(sr, "_write_review_ledger", lambda *a, **k: None)
        monkeypatch.setattr(
            sr,
            "_compute_review_ledger_diff",
            lambda a, s: {"summary": {"added": 1, "removed": 0, "changed": 0, "unchanged": 0}},
        )
        assert sr._handle_supply_chain_scan(args) == 1

    def test_scan_fail_on_review_new_passes_without_added(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """scan ratchet: 无新增项时不应因该策略失败。"""
        import argparse

        args = argparse.Namespace(
            path=tmp_path,
            fail_on="high",
            format="text",
            output=None,
            policy_file=None,
            review_ledger=None,
            review_ledger_baseline=tmp_path / "base.json",
            fail_on_review_new=True,
        )
        result = ScanResult(project_path=str(tmp_path), summary=_summary_with_attribution())
        scanner = MagicMock()
        scanner.scan_project.return_value = result
        monkeypatch.setattr(sr, "SupplyChainScanner", lambda **_: scanner)
        monkeypatch.setattr(sr, "_output_scan_result", lambda *a, **k: None)
        monkeypatch.setattr(sr, "_write_review_ledger", lambda *a, **k: None)
        monkeypatch.setattr(
            sr,
            "_compute_review_ledger_diff",
            lambda a, s: {"summary": {"added": 0, "removed": 1, "changed": 0, "unchanged": 1}},
        )
        assert sr._handle_supply_chain_scan(args) == 0

    def test_compliance_fail_on_review_new_adds_violation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """compliance + --fail-on-review-new: 新增待复核项应记为违规并失败。"""
        import argparse

        args = argparse.Namespace(
            path=tmp_path,
            policy_file=None,
            format="text",
            output=None,
            review_ledger=None,
            review_ledger_baseline=tmp_path / "base.json",
            fail_on_review_new=True,
        )
        result = ScanResult(project_path=str(tmp_path), summary=_summary_with_attribution())
        scanner = MagicMock()
        scanner.scan_project.return_value = result
        monkeypatch.setattr(sr, "SupplyChainScanner", lambda **_: scanner)
        monkeypatch.setattr(sr, "_load_license_policy", lambda _: None)
        monkeypatch.setattr(sr, "_resolve_licenses", lambda *a, **k: None)
        monkeypatch.setattr(sr, "_output_compliance", lambda *a, **k: None)
        monkeypatch.setattr(
            sr,
            "_compute_review_ledger_diff",
            lambda a, s: {"summary": {"added": 2, "removed": 0, "changed": 0, "unchanged": 0}},
        )
        # capture compliance via output hook
        captured = {}

        def _cap(args_, root, comp, diff=None):
            captured["comp"] = comp

        monkeypatch.setattr(sr, "_output_compliance", _cap)
        assert sr._handle_supply_chain_compliance(args) == 1
        assert captured["comp"]["passed"] is False
        assert any(
            v["type"] == "license_review" and "New license review items" in v["message"]
            for v in captured["comp"]["violations"]
        )

    def test_apply_review_allowlist_excludes_accepted_items(self, tmp_path: Path) -> None:
        """已知可接受项应从待复核集合/计数中移除, 并记录 accepted。"""
        import json

        allow = tmp_path / "allow.json"
        allow.write_text(
            json.dumps(
                {"accepted": [{"ecosystem": "pypi", "name": "flaky-pkg", "version": "1.0.0", "cause": "unreachable"}]}
            ),
            encoding="utf-8",
        )
        deps = [make_dep("flaky-pkg"), make_dep("gone-pkg")]
        for d in deps:
            d.license_policy = sr.LicensePolicy.REVIEW
        result = ScanResult(
            project_path=str(tmp_path),
            dependencies=deps,
            license_review=[
                "REVIEW needed: flaky-pkg@1.0.0 (None)",
                "REVIEW needed: gone-pkg@1.0.0 (None)",
            ],
            summary={},
        )
        sr._attribute_license_review(result, _mixed_client())
        args = SimpleNamespace(review_allowlist=allow)
        sr._apply_review_allowlist(args, result)
        assert result.summary["license_review"] == 1
        assert result.summary["license_review_accepted"] == 1
        names = [it["name"] for it in result.summary["license_review_items"]]
        assert names == ["gone-pkg"]
        assert result.summary["license_review_unreachable"] == 0
        assert result.summary["license_review_unknown"] == 1
        assert result.license_review == ["REVIEW needed: gone-pkg@1.0.0 (None)"]

    def test_allowlist_suppresses_ratchet_for_accepted_new_item(self, tmp_path: Path) -> None:
        """豁免项不应计入当前台账, 因而不触发新增项 ratchet。"""
        import json

        baseline = tmp_path / "base.json"
        baseline.write_text(json.dumps({"items": []}), encoding="utf-8")
        allow = tmp_path / "allow.json"
        allow.write_text(
            json.dumps({"accepted": [{"ecosystem": "pypi", "name": "new-pkg", "version": "1.0.0"}]}),
            encoding="utf-8",
        )
        summary = {
            "license_review": 1,
            "license_review_unreachable": 1,
            "license_review_unknown": 0,
            "license_review_items": [
                {
                    "ecosystem": "pypi",
                    "name": "new-pkg",
                    "version": "1.0.0",
                    "license": None,
                    "cause": "unreachable",
                    "policy": "review",
                    "message": "REVIEW needed: new-pkg@1.0.0 (None)",
                }
            ],
        }
        result = ScanResult(
            project_path=str(tmp_path), license_review=["REVIEW needed: new-pkg@1.0.0 (None)"], summary=summary
        )
        args = SimpleNamespace(review_allowlist=allow, review_ledger_baseline=baseline, fail_on_review_new=True)
        sr._apply_review_allowlist(args, result)
        diff = sr._compute_review_ledger_diff(args, result.summary)
        assert sr._review_new_failures(diff) == 0
        assert result.summary["license_review"] == 0
