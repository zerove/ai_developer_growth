"""license_review 成因归因测试 (supply_runner._attribute_license_review)。

独立成文件的原因: 追加进 test_supply_runner_round2.py 会触发测试文件
500 行上限守卫 (test_test_file_size), 且归因是独立特性, 值得单独契约。

归因设计背景见 supply_runner._attribute_license_review docstring:
待复核许可证混合三种成因 (copyleft / PyPI 元数据不可达 / 许可证确实未声明),
摘要必须显式区分后两者, 否则网络抖动会被误读成"依赖许可证有问题"。
"""

from __future__ import annotations

from pathlib import Path
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
        import json

        from types import SimpleNamespace

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
        import json

        from types import SimpleNamespace

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
