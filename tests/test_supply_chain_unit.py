"""supply_chain 基础单元测试（改进建议 3）。

覆盖此前 0% 的供应链模块核心纯逻辑：许可证策略判定、依赖解析、
SBOM 生成与去重。网络类扫描器（OSV/GHSA）只测离线解析路径。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.supply_chain import (
    LicenseChecker,
    LicensePolicy,
    SBOMGenerator,
)

# ─────────────────────────────────────────────────────────────
# LicenseChecker
# ─────────────────────────────────────────────────────────────


class TestLicenseChecker:
    def test_permissive_default_allow(self) -> None:
        checker = LicenseChecker()
        assert checker.check_license("MIT") == LicensePolicy.ALLOW
        assert checker.check_license("Apache-2.0") == LicensePolicy.ALLOW

    def test_copyleft_default_review_or_deny(self) -> None:
        checker = LicenseChecker()
        result = checker.check_license("GPL-3.0")
        assert result in (LicensePolicy.REVIEW, LicensePolicy.DENY)

    def test_unknown_license_review(self) -> None:
        checker = LicenseChecker()
        assert checker.check_license("Some-Weird-License") == LicensePolicy.REVIEW

    def test_none_license_review(self) -> None:
        checker = LicenseChecker()
        assert checker.check_license(None) == LicensePolicy.REVIEW

    def test_explicit_policy_overrides(self) -> None:
        checker = LicenseChecker(policy={"MIT": LicensePolicy.DENY})
        assert checker.check_license("MIT") == LicensePolicy.DENY

    def test_whitespace_normalized(self) -> None:
        checker = LicenseChecker()
        assert checker.check_license("  MIT  ") == LicensePolicy.ALLOW


# ─────────────────────────────────────────────────────────────
# SBOMGenerator — Python 生态解析
# ─────────────────────────────────────────────────────────────


class TestParseRequirements:
    def test_basic_pinning(self, tmp_path: Path) -> None:
        gen = SBOMGenerator()
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\nflask>=3.0.0\n# comment\n\n")
        deps = gen._parse_requirements(req)
        names = {d.name for d in deps}
        assert "requests" in names and "flask" in names

    def test_missing_file_empty(self, tmp_path: Path) -> None:
        gen = SBOMGenerator()
        assert gen._parse_requirements(tmp_path / "nope.txt") == []


class TestGenerateFromPython:
    def test_pyproject_deps_collected(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\ndependencies = ["click>=8.1"]\n')
        sbom = SBOMGenerator().generate_from_python(tmp_path)
        assert sbom.name == tmp_path.name  # name 取项目根目录名
        assert any(d.name == "click" for d in sbom.packages)
        assert len(sbom.relationships) == len(sbom.packages)


class TestDedupe:
    def test_name_version_ecosystem_key(self) -> None:
        from tools.scripts.supply_chain import Dependency

        deps = [
            Dependency(name="a", version="1.0", ecosystem="pypi"),
            Dependency(name="a", version="1.0", ecosystem="pypi"),
            Dependency(name="a", version="2.0", ecosystem="pypi"),
        ]
        unique = SBOMGenerator._dedupe_dependencies(deps)
        assert len(unique) == 2


class TestOSVOffline:
    def test_empty_dependencies_no_network(self) -> None:
        from tools.scripts.supply_chain import OSVScanner

        scanner = OSVScanner()
        assert scanner.scan_dependencies([]) == []
