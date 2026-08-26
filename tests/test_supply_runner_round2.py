"""hooks/supply_runner.py 第二轮攻坚: SBOM/verify/signature/SARIF/SPDX/CycloneDX。

覆盖第二轮缺口(48%→70%+):
- _handle_supply_chain_sbom / _handle_sbom (json/spdx/cyclonedx × stdout/file)
- _handle_supply_chain_freshness (text/json/output)
- _verify_packages / _handle_supply_chain_verify / _print_verify_text
- _handle_verify_signature (cosign/slsa/未指定)
- _to_sarif_supply_chain / _severity_to_sarif_level
- _to_spdx_tagvalue / _to_cyclonedx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks import supply_runner as sr
from tools.scripts.supply_chain import SBOM, Dependency, ScanResult, Severity, Vulnerability


def make_args(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "path": Path("."),
        "fail_on": "high",
        "format": "text",
        "output": None,
        "sc_action": "scan",
        "max_age_days": 90,
        "max_age": 90,
        "cosign": None,
        "cosign_key": None,
        "slsa": None,
    }
    base.update(kw)
    return argparse.Namespace(**base)  # type: ignore[arg-type]


def make_dep(name: str = "pkg-a", ecosystem: str = "pypi", license_: str | None = "MIT") -> Dependency:
    return Dependency(name=name, version="1.0.0", ecosystem=ecosystem, license=license_)


def make_sbom(deps: list[Dependency] | None = None) -> SBOM:
    sbom = SBOM()
    sbom.name = "test-project"
    sbom.version = "1.0"
    sbom.packages = deps if deps is not None else [make_dep()]
    return sbom


def make_scan_result(vulns: list[Vulnerability] | None = None) -> ScanResult:
    return ScanResult(
        project_path="/tmp/p",
        dependencies=[make_dep()],
        vulnerabilities=vulns or [],
        license_issues=[],
        summary={
            "total_dependencies": 1,
            "direct_dependencies": 1,
            "vulnerabilities": len(vulns or []),
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "license_issues": 0,
        },
    )


class TestHandleSupplyChainSbom:
    """supply-chain sbom 子命令全分支。"""

    def _scanner_mock(self) -> MagicMock:
        scanner = MagicMock()
        scanner.generate_sbom.return_value = make_sbom()
        return scanner

    def test_path_not_found(self, tmp_path: Path) -> None:
        rc = sr._handle_supply_chain_sbom(make_args(path=tmp_path / "missing"))
        assert rc == 1

    @pytest.mark.parametrize("fmt", ["json", "spdx", "cyclonedx"])
    def test_formats_stdout(self, fmt: str, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(sr, "SupplyChainScanner", return_value=self._scanner_mock()):
            rc = sr._handle_supply_chain_sbom(make_args(format=fmt))
        assert rc == 0
        out = capsys.readouterr().out
        assert out.strip()

    @pytest.mark.parametrize("fmt", ["spdx", "cyclonedx"])
    def test_formats_to_file(self, fmt: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out_file = tmp_path / f"sbom.{fmt}"
        with patch.object(sr, "SupplyChainScanner", return_value=self._scanner_mock()):
            rc = sr._handle_supply_chain_sbom(make_args(format=fmt, output=out_file))
        assert rc == 0
        assert out_file.exists() and out_file.stat().st_size > 0

    def test_json_to_file_delegates_to_scanner(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """json+output 时由 scanner.generate_sbom 负责落盘(handler 只提示)。"""
        out_file = tmp_path / "sbom.json"
        scanner = self._scanner_mock()
        with patch.object(sr, "SupplyChainScanner", return_value=scanner):
            rc = sr._handle_supply_chain_sbom(make_args(format="json", output=out_file))
        assert rc == 0
        scanner.generate_sbom.assert_called_once()
        assert "written to" in capsys.readouterr().out

    def test_json_stdout_valid(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(sr, "SupplyChainScanner", return_value=self._scanner_mock()):
            sr._handle_supply_chain_sbom(make_args(format="json"))
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "test-project"


class TestHandleSbomAlias:
    """sbom 独立命令(与 supply-chain sbom 同逻辑)。"""

    def test_path_not_found_and_dispatch(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert sr._handle_sbom(make_args(path=tmp_path / "nope")) == 1

        scanner = MagicMock()
        scanner.generate_sbom.return_value = make_sbom()
        with patch.object(sr, "SupplyChainScanner", return_value=scanner):
            assert sr._handle_sbom(make_args(path=tmp_path, format="spdx")) == 0
        assert "SPDXVersion" in capsys.readouterr().out


class TestFreshnessHandler:
    """supply-chain freshness 子命令。"""

    def test_path_not_found(self, tmp_path: Path) -> None:
        rc = sr._handle_supply_chain_freshness(make_args(path=tmp_path / "gone"))
        assert rc == 1

    def test_text_with_output_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        out_file = tmp_path / "fresh.json"
        rc = sr._handle_supply_chain_freshness(
            make_args(path=empty, format="text", output=out_file, max_age_days=90, max_age=90)
        )
        assert rc == 0
        assert out_file.exists()

    def test_json_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        rc = sr._handle_supply_chain_freshness(make_args(path=empty, format="json"))
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "project" in data


class TestVerifyPackages:
    """_verify_packages 汇总逻辑。"""

    def test_mixed_ecosystems(self, tmp_path: Path) -> None:
        dep_pypi = make_dep("good-pkg")
        dep_npm = make_dep("npm-pkg", ecosystem="npm")
        scanner = MagicMock()
        scanner.sbom_generator.generate_from_project.return_value = make_sbom([dep_pypi, dep_npm])
        scanner._flatten_deps.return_value = [dep_pypi, dep_npm]
        scanner.signature_verifier.verify_pypi_package.return_value = {"verified": True, "details": "ok"}

        with patch.object(sr, "SupplyChainScanner", return_value=scanner):
            report = sr._verify_packages(tmp_path)

        assert report["total_packages"] == 2
        assert len(report["verified"]) == 1
        assert len(report["unverified"]) == 1
        assert report["unverified"][0]["reason"].startswith("No verifier")

    def test_verify_failure_goes_unverified(self, tmp_path: Path) -> None:
        dep = make_dep("bad-pkg")
        scanner = MagicMock()
        scanner.sbom_generator.generate_from_project.return_value = make_sbom([dep])
        scanner._flatten_deps.return_value = [dep]
        scanner.signature_verifier.verify_pypi_package.return_value = {"verified": False, "error": "no sig"}

        with patch.object(sr, "SupplyChainScanner", return_value=scanner):
            report = sr._verify_packages(tmp_path)

        assert report["verified"] == []
        assert report["unverified"][0]["reason"] == "no sig"

    def test_verify_missing_reason_defaults(self, tmp_path: Path) -> None:
        dep = make_dep("mystery")
        scanner = MagicMock()
        scanner.sbml_placeholder = None  # noqa: F841  防误用属性
        del scanner.sbml_placeholder
        scanner.sbom_generator.generate_from_project.return_value = make_sbom([dep])
        scanner._flatten_deps.return_value = [dep]
        scanner.signature_verifier.verify_pypi_package.return_value = {"verified": False}

        with patch.object(sr, "SupplyChainScanner", return_value=scanner):
            report = sr._verify_packages(tmp_path)

        assert report["unverified"][0]["reason"] == "No verification data"


class TestHandleSupplyChainVerify:
    """supply-chain verify 子命令。"""

    def test_path_not_found(self, tmp_path: Path) -> None:
        assert sr._handle_supply_chain_verify(make_args(path=tmp_path / "x")) == 1

    def test_all_verified_returns_zero(self, tmp_path: Path) -> None:
        with patch.object(sr, "_verify_packages", return_value=_verify_report(unverified=[])):
            assert sr._handle_supply_chain_verify(make_args(path=tmp_path)) == 0

    def test_unverified_returns_one(self, tmp_path: Path) -> None:
        rep = _verify_report(unverified=[{"name": "n", "version": "1", "reason": "r"}])
        with patch.object(sr, "_verify_packages", return_value=rep):
            assert sr._handle_supply_chain_verify(make_args(path=tmp_path)) == 1

    def test_json_output_file(self, tmp_path: Path) -> None:
        out = tmp_path / "v.json"
        rep = _verify_report(unverified=[{"name": "n", "version": "1", "reason": "r"}])
        with patch.object(sr, "_verify_packages", return_value=rep):
            sr._handle_supply_chain_verify(make_args(path=tmp_path, format="json", output=out))
        assert json.loads(out.read_text())["total_packages"] >= 0


def _verify_report(*, unverified: list[dict[str, str]]) -> dict[str, object]:
    return {
        "project": "/p",
        "verified_at": "now",
        "total_packages": 1 + len(unverified),
        "verified": [],
        "unverified": unverified,
        "failed": [],
    }


class TestPrintVerifyText:
    def test_full_report(self, capsys: pytest.CaptureFixture[str]) -> None:
        rep = _verify_report(unverified=[{"name": f"pkg{i}", "version": "1.0", "reason": "no data"} for i in range(12)])
        sr._print_verify_text(Path("/p"), rep)
        out = capsys.readouterr().out
        assert "Total packages: 13" in out
        assert "... and 2 more" in out


class TestHandleVerifySignature:
    """verify-signature 命令三分支。"""

    def test_no_target_specified(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = sr._handle_verify_signature(make_args())
        assert rc == 1
        assert "Specify" in capsys.readouterr().out

    def test_cosign_verified_text_and_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        verifier = MagicMock()
        verifier.verify_cosign_signature.return_value = {"verified": True, "output": "o", "error": ""}
        # 延迟导入 → patch 源头 tools.scripts.supply_chain.SignatureVerifier
        with patch("tools.scripts.supply_chain.SignatureVerifier", return_value=verifier):
            assert sr._handle_verify_signature(make_args(cosign="img@sha256:x")) == 0
            assert sr._handle_verify_signature(make_args(cosign="img", format="json")) == 0
        out = capsys.readouterr()
        assert "Verified" in out.out

    def test_cosign_failed(self, capsys: pytest.CaptureFixture[str]) -> None:
        verifier = MagicMock()
        verifier.verify_cosign_signature.return_value = {"verified": False, "error": "boom"}
        with patch("tools.scripts.supply_chain.SignatureVerifier", return_value=verifier):
            assert sr._handle_verify_signature(make_args(cosign="img")) == 1

    def test_slsa_branches(self, capsys: pytest.CaptureFixture[str]) -> None:
        verifier = MagicMock()
        verifier.verify_slsa_provenance.return_value = {"verified": True, "message": "ok"}
        with patch("tools.scripts.supply_chain.SignatureVerifier", return_value=verifier):
            assert sr._handle_verify_signature(make_args(slsa="prov.json")) == 0
            assert sr._handle_verify_signature(make_args(slsa="prov.json", format="json")) == 0
        verifier.verify_slsa_provenance.return_value = {"verified": False, "message": "bad"}
        with patch("tools.scripts.supply_chain.SignatureVerifier", return_value=verifier):
            assert sr._handle_verify_signature(make_args(slsa="prov.json")) == 1


class TestSarifConversion:
    def test_severity_mapping(self) -> None:
        from tools.scripts.supply_chain import Severity as Sev

        assert sr._severity_to_sarif_level(Sev.CRITICAL) == "error"
        assert sr._severity_to_sarif_level(Sev.HIGH) == "error"
        assert sr._severity_to_sarif_level(Sev.MEDIUM) == "warning"
        assert sr._severity_to_sarif_level(Sev.LOW) == "note"
        assert sr._severity_to_sarif_level(Sev.NONE) == "note"

    def test_sarif_structure(self) -> None:
        vuln = Vulnerability(
            id="GHSA-x",
            source="OSV",
            summary="s" * 150,
            severity=Severity.HIGH,
            affected_package="pkg",
            affected_version="1.0",
            fixed_version="1.1",
        )
        result = make_scan_result(vulns=[vuln])
        sarif = sr._to_sarif_supply_chain(result)
        run = sarif["runs"][0]
        assert run["tool"]["driver"]["name"] == "JCode Supply Chain Scanner"
        assert run["results"][0]["level"] == "error"
        assert len(run["results"][0]["ruleId"]) > 0

    def test_sarif_dedup_rules(self) -> None:
        v1 = Vulnerability(
            id="GHSA-dup",
            source="OSV",
            summary="s",
            severity=Severity.HIGH,
            affected_package="a",
            affected_version="1",
            fixed_version="2",
        )
        v2 = Vulnerability(
            id="GHSA-dup",
            source="OSV",
            summary="s",
            severity=Severity.MEDIUM,
            affected_package="b",
            affected_version="1",
            fixed_version="2",
        )
        sarif = sr._to_sarif_supply_chain(make_scan_result(vulns=[v1, v2]))
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        results = sarif["runs"][0]["results"]
        assert len(rules) == 1 and len(results) == 2


class TestSpdxCyclonedx:
    def test_spdx_contains_packages(self) -> None:
        sbom = make_sbom([make_dep("a"), make_dep("b", license_=None)])
        spdx = sr._to_spdx_tagvalue(sbom)
        assert "PackageName: a" in spdx
        assert "LicenseConcluded: NOASSERTION" in spdx
        assert spdx.startswith("SPDXVersion: SPDX-2.3")

    def test_cyclonedx_structure(self) -> None:
        sbom = make_sbom([make_dep("libx"), make_dep("liby", license_=None)])
        cdx = sr._to_cyclonedx(sbom)
        assert cdx["bomFormat"] == "CycloneDX"
        names = [c["name"] for c in cdx["components"]]
        assert names == ["libx", "liby"]
        assert cdx["components"][0]["purl"] == "pkg:pypi/libx@1.0.0"
        assert cdx["components"][1]["licenses"] == []


class TestScanResultSmoke:
    def test_make_scan_result_fields(self) -> None:
        r = make_scan_result()
        assert r.summary["total_dependencies"] == 1
