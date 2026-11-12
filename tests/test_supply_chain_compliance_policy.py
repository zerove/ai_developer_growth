"""供应链合规/校验行为的契约测试（许可证策略 + 版本约束）。

背景（真实失效形态）:
    1. `_handle_supply_chain_compliance` 之前调用 `_load_license_policy()` 却
       **丢弃返回值** —— 策略文件里的允许/禁止清单从未参与判定。
    2. 清单文件（pyproject/requirements）不含依赖自身的许可证，扫描结果的
       license 恒为 None → 全部落进 REVIEW 分支 → 合规检查恒红且毫无判别力。
    3. 清单里的 `>=0.23` 只是版本下界（PyPI 上真实版本是 0.23.0），按文本
       查版本必然判"不存在" → verify 恒红。
    4. REVIEW（未知 / copyleft 许可证）被当成违规阻断 —— 未知 ≠ 违规。

这些缺陷都不会报错，只会让流水线恒红，因此把判定语义锁进测试。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from tools.scripts._sc_models import SBOM, Dependency, LicensePolicy, ScanResult, Severity
from tools.scripts._sc_pypi import (
    CLASSIFIER_TO_SPDX,
    TEXT_KEYWORD_TO_SPDX,
    PyPIMetadataClient,
    license_from_classifiers,
    normalize_license_expression,
    normalize_license_text,
    version_at_least,
    version_key,
)
from tools.scripts._sc_scanners import LicenseChecker, SupplyChainScanner
from tools.scripts.hooks import supply_runner as sr

# ── 许可证归一化 ────────────────────────────────────────────


class TestLicenseNormalization:
    def test_classifier_mit(self) -> None:
        assert license_from_classifiers(["License :: OSI Approved :: MIT License"]) == "MIT"

    def test_classifier_ignores_non_license(self) -> None:
        assert license_from_classifiers(["Programming Language :: Python :: 3"]) is None

    def test_classifier_without_separator(self) -> None:
        assert license_from_classifiers(["License"]) is None

    def test_classifier_unknown_kept_verbatim(self) -> None:
        assert license_from_classifiers(["License :: Free For Educational Use"]) == "Free For Educational Use"

    def test_all_known_classifiers_map_to_spdx(self) -> None:
        """映射表里的每一条都要能被识别（防止键值被改坏却无人察觉）。"""
        for raw_name, spdx in CLASSIFIER_TO_SPDX.items():
            assert license_from_classifiers([f"License :: OSI Approved :: {raw_name}"]) == spdx

    def test_text_fallback(self) -> None:
        assert normalize_license_text("Apache Software License 2.0") == "Apache-2.0"

    def test_all_known_text_keywords_map_to_spdx(self) -> None:
        for keyword, spdx in TEXT_KEYWORD_TO_SPDX.items():
            assert normalize_license_text(f"licensed under the {keyword} terms") == spdx

    def test_text_unknown_returns_none(self) -> None:
        assert normalize_license_text("see LICENSE file") is None

    def test_text_empty_returns_none(self) -> None:
        assert normalize_license_text("") is None

    def test_expression_normalized(self) -> None:
        assert normalize_license_expression("  MIT   OR   Apache-2.0 ") == "MIT OR Apache-2.0"

    def test_expression_empty_returns_none(self) -> None:
        assert normalize_license_expression("") is None

    def test_expression_whitespace_only_returns_none(self) -> None:
        assert normalize_license_expression("   ") is None


# ── 版本比较 ────────────────────────────────────────────────


class TestVersionHelpers:
    def test_version_key(self) -> None:
        assert version_key("0.23.1") == (0, 23, 1)

    def test_version_key_non_numeric(self) -> None:
        assert version_key("1.0.post1") == (1, 0, 1)

    def test_version_key_without_digits(self) -> None:
        assert version_key("1.x") == (1, 0)

    def test_at_least(self) -> None:
        assert version_at_least("0.23.0", "0.23") is True
        assert version_at_least("0.22.9", "0.23") is False

    def test_at_least_equal(self) -> None:
        assert version_at_least("1.0", "1.0") is True


# ── PyPI 客户端（不触网） ───────────────────────────────────


class FakePyPI:
    """用假数据替身模拟 PyPI 元数据。"""

    def __init__(self, packages: dict[str, dict[str, Any]]) -> None:
        self.packages = packages

    def client(self) -> PyPIMetadataClient:
        client = PyPIMetadataClient()
        client._cache = {name: data for name, data in self.packages.items()}
        return client


class TestPyPIClient:
    def test_license_from_expression(self) -> None:
        fake = FakePyPI({"pkg": {"info": {"license_expression": "MIT"}}})
        assert fake.client().license_of("pkg") == "MIT"

    def test_license_from_classifier(self) -> None:
        fake = FakePyPI({"pkg": {"info": {"classifiers": ["License :: OSI Approved :: MIT License"]}}})
        assert fake.client().license_of("pkg") == "MIT"

    def test_license_unknown(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}}})
        assert fake.client().license_of("pkg") is None

    def test_exact_version_resolved(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.0.0": [], "1.1.0": []}}})
        assert fake.client().resolve_version("pkg", "1.0.0", "==") == "1.0.0"

    def test_lower_bound_resolved(self) -> None:
        """清单里的 ">=0.23" 必须能解析到真实发布版本 0.23.0。"""
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"0.23.0": [], "0.24.0": []}}})
        assert fake.client().resolve_version("pkg", "0.23", ">=") == "0.23.0"

    def test_unsatisfiable_returns_none(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"0.22.0": []}}})
        assert fake.client().resolve_version("pkg", "0.23", ">=") is None

    def test_missing_package_returns_none(self) -> None:
        fake = FakePyPI({})
        assert fake.client().resolve_version("pkg", "1.0", ">=") is None

    def test_exact_pin_not_published_returns_none(self) -> None:
        """精确锁定 (==) 的版本没发布 → 约束不满足, 不能降级成"下界匹配"。"""
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.0.0": []}}})
        assert fake.client().resolve_version("pkg", "1.0", "==") is None

    def test_compatible_specifier_keeps_minimum(self) -> None:
        """~= 允许同主版本内升级, 但不得低于声明版本。"""
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.1.0": [], "1.3.0": [], "2.0.0": []}}})
        assert fake.client().resolve_version("pkg", "1.2", "~=") == "1.3.0"

    def test_compatible_specifier_rejects_older(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.1.0": []}}})
        assert fake.client().resolve_version("pkg", "1.2", "~=") is None

    def test_missing_specifier_uses_lower_bound(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"0.23.0": [], "0.24.0": []}}})
        assert fake.client().resolve_version("pkg", "0.23", None) == "0.23.0"

    def test_metadata_is_cached(self) -> None:
        """同一包名只查一次（合规与校验两个动作共用同一进程缓存）。"""
        calls: list[str] = []

        class CountingClient(PyPIMetadataClient):
            def _fetch(self, name: str) -> dict[str, Any] | None:
                calls.append(name)
                return {"info": {}, "releases": {"1.0.0": []}}

        client = CountingClient()
        client.metadata("pkg")
        client.metadata("pkg")
        assert calls == ["pkg"]


# ── 许可证策略判定 ──────────────────────────────────────────


class TestLicensePolicyEvaluation:
    def test_denied_and_review_are_separated(self) -> None:
        checker = LicenseChecker(policy={"GPL-3.0": LicensePolicy.DENY})
        deps = [
            Dependency(name="ok", version="1.0", ecosystem="pypi", license="MIT"),
            Dependency(name="bad", version="1.0", ecosystem="pypi", license="GPL-3.0"),
            Dependency(name="unknown", version="1.0", ecosystem="pypi", license=None),
        ]
        denied, review = checker.evaluate_dependencies(deps)
        assert len(denied) == 1 and "bad" in denied[0]
        assert len(review) == 1 and "unknown" in review[0]
        assert checker.check_dependencies(deps) == denied

    def test_compound_or_expression_allows_when_one_branch_allowed(self) -> None:
        checker = LicenseChecker()
        assert checker.check_license("MIT OR GPL-3.0") == LicensePolicy.ALLOW

    def test_compound_and_expression_denies_when_one_branch_denied(self) -> None:
        checker = LicenseChecker(policy={"GPL-3.0": LicensePolicy.DENY})
        assert checker.check_license("MIT AND GPL-3.0") == LicensePolicy.DENY


class TestCompliancePolicyWiring:
    def test_policy_file_is_applied_to_scanner(self, tmp_path: Path) -> None:
        """策略文件里的禁止清单必须真正参与判定（此前返回值被丢弃）。"""
        policy = tmp_path / "policy.yaml"
        policy.write_text("allowed_licenses: [MIT]\ndisallowed_licenses: [GPL-3.0]\n", encoding="utf-8")
        loaded = sr._load_license_policy(policy)
        assert loaded == {"MIT": LicensePolicy.ALLOW, "GPL-3.0": LicensePolicy.DENY}
        checker = LicenseChecker(policy=loaded)
        assert checker.check_license("GPL-3.0") == LicensePolicy.DENY
        assert checker.check_license("MIT") == LicensePolicy.ALLOW

    def test_review_is_warning_not_violation(self, tmp_path: Path) -> None:
        """未知许可证是"待复核"，不是违规 —— 否则任何项目都恒红。"""
        result = ScanResult(
            project_path=str(tmp_path),
            license_issues=[],
            license_review=["REVIEW needed: pkg@1.0 (None)"],
            summary={"license_issues": 0, "license_review": 1},
        )
        compliance = sr._run_compliance_checks(tmp_path, result)
        assert compliance["passed"] is True
        assert compliance["violations"] == []
        assert compliance["warnings"][0]["type"] == "license"

    def test_denied_license_is_violation(self, tmp_path: Path) -> None:
        result = ScanResult(
            project_path=str(tmp_path),
            license_issues=["DENIED license: pkg@1.0 (GPL-3.0)"],
            summary={"license_issues": 1},
        )
        compliance = sr._run_compliance_checks(tmp_path, result)
        assert compliance["passed"] is False
        assert compliance["violations"][0]["type"] == "license"


# ── verify 的版本存在性判定 ─────────────────────────────────


class TestVerifySemantics:
    def _report(self, **kwargs: Any) -> dict[str, Any]:
        base = {"verified": [], "unverified": [], "unverifiable": [], "failed": []}
        base.update(kwargs)
        return base

    def test_unverified_blocks(self, tmp_path: Path) -> None:
        args = argparse.Namespace(path=tmp_path, format="json", output=None)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sr, "_verify_packages", lambda _root: self._report(unverified=[{"name": "x"}]))
            mp.setattr(sr, "_output_verify_report", lambda *_a, **_k: None, raising=False)
            assert sr._handle_supply_chain_verify(args) == 1

    def test_metadata_unreachable_alone_blocks(self, tmp_path: Path) -> None:
        """一个包都没校验成功 → 校验本身失效，必须阻断（不能"查不到即放行"）。"""
        args = argparse.Namespace(path=tmp_path, format="json", output=None)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                sr,
                "_verify_packages",
                lambda _root: self._report(unverifiable=[{"name": "x"}], verified=[]),
            )
            assert sr._handle_supply_chain_verify(args) == 1

    def test_partial_unreachable_does_not_block(self, tmp_path: Path) -> None:
        args = argparse.Namespace(path=tmp_path, format="json", output=None)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                sr,
                "_verify_packages",
                lambda _root: self._report(unverifiable=[{"name": "x"}], verified=[{"name": "y"}]),
            )
            assert sr._handle_supply_chain_verify(args) == 0


# ── SBOM 往返 ──────────────────────────────────────────────


class TestSBOMRoundTrip:
    def test_from_dict_restores_packages(self) -> None:
        sbom = SBOM(name="demo", version="1.0")
        sbom.packages.append(Dependency(name="pyyaml", version="6.0", ecosystem="pypi", license="MIT"))
        restored = SBOM.from_dict(json.loads(sbom.to_json()))
        assert restored.name == "demo"
        assert restored.packages[0].name == "pyyaml"
        assert restored.packages[0].license == "MIT"


class TestDependencySpecifier:
    def test_specifier_captured(self) -> None:
        from tools.scripts._sc_sbom import SBOMGenerator

        gen = SBOMGenerator()
        dep = gen._parse_dep_spec("tree-sitter-kotlin>=0.23")
        assert dep is not None
        assert dep.name == "tree-sitter-kotlin"
        assert dep.version == "0.23"
        assert dep.specifier == ">="

    def test_exact_pin_specifier(self) -> None:
        from tools.scripts._sc_sbom import SBOMGenerator

        dep = SBOMGenerator()._parse_dep_spec("ruff==0.15.17")
        assert dep is not None
        assert dep.specifier == "=="


def test_scanner_summary_reports_review_separately() -> None:
    """扫描汇总必须区分"禁用许可证"与"待复核许可证"。"""
    scanner = SupplyChainScanner(license_policy={"GPL-3.0": LicensePolicy.DENY})
    summary = scanner._build_scan_summary([], [], [], ["REVIEW needed: x@1 (None)"])
    assert summary["license_issues"] == 0
    assert summary["license_review"] == 1


def test_severity_enum_kept_in_scan_result() -> None:
    """ScanResult 的漏洞严重级别仍是枚举（SBOM 反序列化要能还原）。"""
    result = ScanResult(project_path=".")
    assert result.license_review == []
    assert Severity.NONE.value == "none"
