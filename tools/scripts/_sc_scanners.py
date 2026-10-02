"""供应链扫描器 (从 supply_chain.py 拆分).

OSVScanner / GHSASource / LicenseChecker / SignatureVerifier / SupplyChainScanner.
由 supply_chain.py facade 统一 re-export.
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from ._sc_models import SBOM, Dependency, LicensePolicy, ScanResult, Severity, Vulnerability
from ._sc_sbom import SBOMGenerator

logger = logging.getLogger(__name__)


class OSVScanner:
    """OSV (Open Source Vulnerabilities) 扫描器"""

    OSV_API = "https://api.osv.dev/v1/querybatch"
    ECOSYSTEM_MAP = {
        "pypi": "PyPI",
        "npm": "npm",
        "cargo": "crates.io",
        "go": "Go",
        "maven": "Maven",
        "nuget": "NuGet",
        "rubygems": "RubyGems",
        "packagist": "Packagist",
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def scan_dependencies(self, dependencies: list[Dependency]) -> list[Vulnerability]:
        """批量扫描依赖漏洞.

        V2.20 P4-47 拆分: 抽 _build_osv_queries 收口依赖→OSV query 列表构造,
        _query_osv_batch 收口 HTTP 请求 + JSON 解析 + 漏洞遍历,
        主函数仅组装.
        """
        queries = self._build_osv_queries(dependencies)
        if not queries:
            return []
        try:
            return self._query_osv_batch(queries, dependencies)
        except Exception as e:
            logger.warning(f"OSV scan failed: {e}")
            return []

    def _build_osv_queries(self, dependencies: list[Dependency]) -> list[dict[str, Any]]:
        """构造 OSV API 批量查询 payload.

        Args:
            dependencies: 依赖列表

        Returns:
            OSV query 列表
        """
        queries: list[dict[str, Any]] = []
        for dep in dependencies:
            ecosystem = self.ECOSYSTEM_MAP.get(dep.ecosystem.lower(), dep.ecosystem)
            queries.append(
                {
                    "package": {"name": dep.name, "ecosystem": ecosystem},
                    "version": dep.version,
                }
            )
        return queries

    def _query_osv_batch(self, queries: list[dict[str, Any]], dependencies: list[Dependency]) -> list[Vulnerability]:
        """执行 OSV API 批量查询 + 解析响应.

        Args:
            queries: OSV query 列表
            dependencies: 依赖列表 (与 queries 索引对齐)

        Returns:
            Vulnerability 列表
        """
        payload = json.dumps({"queries": queries}).encode()
        req = urllib.request.Request(
            self.OSV_API,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:  # nosec B310
            data = json.loads(response.read().decode())

        vulns: list[Vulnerability] = []
        for i, result in enumerate(data.get("results", [])):
            dep = dependencies[i]
            for vuln_data in result.get("vulns", []):
                vulns.append(self._parse_osv_vuln(vuln_data, dep))
        return vulns

    def _parse_osv_vuln(self, data: dict[str, Any], dep: Dependency) -> Vulnerability:
        """解析单个 OSV 漏洞.

        V2.20 P4-38 拆分: 抽 _extract_cvss_severity 收口 CVSS 解析 + 等级判定,
        _extract_fixed_version 收口 3 层嵌套 fixed 提取.
        主函数仅构造 Vulnerability 对象.
        """
        severity, cvss_score, cvss_vector = self._extract_cvss_severity(data.get("severity", []))
        fixed_version = self._extract_fixed_version(data.get("affected", []))

        return Vulnerability(
            id=data.get("id", ""),
            source="OSV",
            summary=data.get("summary", ""),
            severity=severity,
            affected_package=dep.name,
            affected_version=dep.version,
            fixed_version=fixed_version,
            references=[r.get("url", "") for r in data.get("references", [])],
            published_at=data.get("published"),
            modified_at=data.get("modified"),
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
        )

    def _extract_cvss_severity(self, severities: list[dict[str, Any]]) -> tuple[Severity, float | None, str | None]:
        """从 OSV severity 列表提取 CVSS_V3 分数并映射到 Severity 等级.

        V2.20 P4-46 拆分: 抽 _score_to_severity 收口 CVSS 分数到 Severity 等级映射,
        主函数仅 for + 守卫 + break.
        """
        severity = Severity.NONE
        cvss_score: float | None = None
        cvss_vector: str | None = None

        for sev in severities:
            if sev.get("type") != "CVSS_V3":
                continue
            cvss_score = sev.get("score")
            cvss_vector = sev.get("vector")
            if cvss_score is not None:
                severity = self._score_to_severity(cvss_score)
            break

        return severity, cvss_score, cvss_vector

    @staticmethod
    def _score_to_severity(score: float) -> Severity:
        """CVSS_V3 分数映射到 Severity 等级 (模块级 helper).

        Args:
            score: CVSS 分数 (0.0-10.0)

        Returns:
            Severity 等级
        """
        if score >= 9.0:
            return Severity.CRITICAL
        if score >= 7.0:
            return Severity.HIGH
        if score >= 4.0:
            return Severity.MEDIUM
        return Severity.LOW

    def _extract_fixed_version(self, affected: list[dict[str, Any]]) -> str | None:
        """从 OSV affected 列表提取首个 fixed version.

        Args:
            affected: OSV affected 列表

        Returns:
            fixed version 字符串 (None if 未找到)
        """
        for entry in affected:
            for r in entry.get("ranges", []):
                for event in r.get("events", []):
                    if "fixed" in event:
                        return event["fixed"]
        return None


def _parse_ghsa_severity(raw: object | None) -> Severity:
    """将 GHSA severity 字符串映射为 Severity 枚举 (模块级 helper).

    Args:
        raw: GHSA API 返回的 severity 字段 (如 "high", "moderate", "low", "critical")

    Returns:
        Severity 枚举
    """
    normalized = str(raw).lower() if raw is not None else ""
    mapping = {
        "critical": Severity.CRITICAL,
        "high": Severity.HIGH,
        "moderate": Severity.MEDIUM,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
    }
    return mapping.get(normalized, Severity.NONE)


class GHSASource:
    """GHSA (GitHub Security Advisories) 数据源"""

    def __init__(self, github_token: str | None = None):
        self.github_token = github_token

    def fetch_advisories(self, ecosystem: str, package: str) -> list[Vulnerability]:
        """获取 GHSA 公告 (GitHub Security Advisories API).

        Args:
            ecosystem: 包生态 (如 pypi, npm)
            package: 包名

        Returns:
            Vulnerability 列表, API 失败时返回空列表
        """
        url = f"https://api.github.com/advisories?ecosystem={ecosystem}&affects={package}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if self.github_token:
            req.add_header("Authorization", f"Bearer {self.github_token}")
        try:
            # nosec B310 - scheme/host 是字面量 https://api.github.com，插值只落在 query
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
                advisories: list[dict[str, Any]] = json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"GHSA fetch failed for {package}: {e}")
            return []

        vulns: list[Vulnerability] = []
        for adv in advisories:
            for affected in adv.get("vulnerabilities", []):
                pkg_info = affected.get("package") or {}
                vulns.append(
                    Vulnerability(
                        id=adv.get("ghsa_id", f"GHSA-{package}"),
                        source="GHSA",
                        summary=adv.get("summary", ""),
                        severity=_parse_ghsa_severity(adv.get("severity")),
                        affected_package=pkg_info.get("name", package),
                        affected_version=affected.get("vulnerable_version_range", "*"),
                        fixed_version=affected.get("patched_versions"),
                        references=[r.get("url", "") for r in adv.get("references", []) if r.get("url")],
                        published_at=adv.get("published_at"),
                        modified_at=adv.get("updated_at"),
                        cvss_score=adv.get("cvss", {}).get("score"),
                        cvss_vector=adv.get("cvss", {}).get("vector_string"),
                    )
                )
        return vulns


class LicenseChecker:
    """许可证合规检查器"""

    # 常见许可证分类
    PERMISSIVE_LICENSES = {
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "ISC",
        "Unlicense",
        "CC0-1.0",
        "Zlib",
        "HPND",
    }
    COPYLEFT_LICENSES = {
        "GPL-2.0",
        "GPL-3.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "AGPL-3.0",
        "MPL-2.0",
        "EPL-2.0",
        "CDDL-1.0",
    }
    PROPRIETARY_LICENSES = {
        "Proprietary",
        "Commercial",
        "Non-OSI",
        "Custom",
    }

    def __init__(self, policy: dict[str, LicensePolicy] | None = None):
        """policy: 许可证 -> 策略映射，如 {"GPL-3.0": LicensePolicy.DENY}"""
        self.policy = policy or {}

    def check_license(self, license_str: str | None) -> LicensePolicy:
        """检查单个许可证.

        V2.20 P4-48 拆分: 抽 _classify_license 收口标准化后策略匹配 (4 档),
        主函数仅 None 守卫 + 标准化 + 委托.
        """
        if not license_str:
            return LicensePolicy.REVIEW

        license_str = license_str.strip()
        return self._classify_license(license_str)

    def _classify_license(self, license_str: str) -> LicensePolicy:
        """根据 license_str 返回 LicensePolicy (模块级 helper).

        Args:
            license_str: 已标准化的 license 字符串

        Returns:
            LicensePolicy 等级
        """
        if license_str in self.policy:
            return self.policy[license_str]
        if license_str in self.PERMISSIVE_LICENSES:
            return LicensePolicy.ALLOW
        if license_str in self.COPYLEFT_LICENSES:
            return LicensePolicy.REVIEW  # 需要人工评估
        if license_str in self.PROPRIETARY_LICENSES:
            return LicensePolicy.DENY
        return LicensePolicy.REVIEW

    def check_dependencies(self, dependencies: list[Dependency]) -> list[str]:
        """检查依赖许可证合规"""
        issues = []
        for dep in dependencies:
            policy = self.check_license(dep.license)
            dep.license_policy = policy
            if policy == LicensePolicy.DENY:
                issues.append(f"DENIED license: {dep.name}@{dep.version} ({dep.license})")
            elif policy == LicensePolicy.REVIEW:
                issues.append(f"REVIEW needed: {dep.name}@{dep.version} ({dep.license})")
        return issues


class SignatureVerifier:
    """签名验证器"""

    def __init__(self) -> None:
        pass

    def verify_pypi_package(self, name: str, version: str) -> dict[str, Any]:
        """验证 PyPI 包存在性 (PyPI JSON API).

        Args:
            name: 包名
            version: 版本号

        Returns:
            {"verified": bool, "message": str, ...包元数据}
        """
        url = f"https://pypi.org/pypi/{name}/{version}/json"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - host 字面量 https://pypi.org
                data: dict[str, Any] = json.loads(resp.read().decode())
        except Exception as e:
            return {"verified": False, "message": str(e)}

        info = data.get("info", {})
        urls = data.get("urls", [])
        has_digests = any(u.get("digests") for u in urls)
        return {
            "verified": bool(info.get("name")) and bool(urls) and has_digests,
            "message": f"PyPI 包 {name}=={version} 存在",
            "name": info.get("name"),
            "version": info.get("version"),
            "release_files": len(urls),
            "has_digests": has_digests,
        }

    def verify_cosign_signature(self, image: str, public_key: str | None = None) -> dict[str, Any]:
        """验证容器镜像签名"""
        try:
            cmd = ["cosign", "verify", image]
            if public_key:
                cmd.extend(["--key", public_key])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {
                "verified": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
            }
        except FileNotFoundError:
            return {"verified": False, "message": "cosign not installed"}
        except Exception as e:
            return {"verified": False, "message": str(e)}

    def verify_slsa_provenance(self, package_path: Path) -> dict[str, Any]:
        """验证 SLSA provenance (查找同目录 attestation/intoto 文件).

        Args:
            package_path: 待验证包/文件路径

        Returns:
            {"verified": bool, "message": str, ...}
        """
        if package_path.is_dir():
            candidates = (
                sorted(package_path.glob("*.attestation"))
                + sorted(package_path.glob("*.intoto.jsonl"))
                + sorted(package_path.glob("*.provenance"))
            )
        else:
            candidates = (
                sorted(package_path.parent.glob(f"{package_path.name}*.attestation"))
                + sorted(package_path.parent.glob(f"{package_path.name}*.intoto.jsonl"))
                + sorted(package_path.parent.glob(f"{package_path.name}*.provenance"))
            )
        if not candidates:
            return {"verified": False, "message": "未找到 SLSA provenance 文件"}

        for f in candidates:
            try:
                data: dict[str, Any] = json.loads(f.read_text())
                predicate_type = data.get("predicateType", "")
                if "slsa.dev/provenance" in predicate_type:
                    subject = (data.get("subject") or [{}])[0]
                    return {
                        "verified": True,
                        "message": f"检测到 SLSA provenance: {f.name}",
                        "file": str(f),
                        "predicate_type": predicate_type,
                        "subject_name": subject.get("name"),
                        "subject_digest": subject.get("digest"),
                    }
            except (json.JSONDecodeError, OSError):
                continue
        return {"verified": False, "message": "未找到有效 SLSA provenance"}


class SupplyChainScanner:
    """供应链安全扫描器主入口"""

    def __init__(
        self,
        osv_timeout: int = 30,
        license_policy: dict[str, LicensePolicy] | None = None,
    ):
        self.osv_scanner = OSVScanner(timeout=osv_timeout)
        self.license_checker = LicenseChecker(policy=license_policy)
        self.sbom_generator = SBOMGenerator()
        self.signature_verifier = SignatureVerifier()

    def scan_project(self, project_root: Path) -> ScanResult:
        """扫描整个项目.

        V2.20 P4-37 拆分: 抽 _link_vulns_to_deps 收口漏洞关联,
        _build_scan_summary 收口 summary 字段计算.
        主函数仅 4 段线性: SBOM → vulns → license → summary.
        """
        sbom = self.sbom_generator.generate_from_project(project_root)
        all_deps = self._flatten_deps(sbom.packages)
        vulns = self.osv_scanner.scan_dependencies(all_deps)
        self._link_vulns_to_deps(vulns, all_deps)
        license_issues = self.license_checker.check_dependencies(all_deps)

        return ScanResult(
            project_path=str(project_root),
            dependencies=all_deps,
            vulnerabilities=vulns,
            license_issues=license_issues,
            summary=self._build_scan_summary(all_deps, vulns, license_issues),
        )

    def _link_vulns_to_deps(self, vulns: list[Vulnerability], all_deps: list[Dependency]) -> None:
        """将漏洞关联到对应依赖对象 (in-place 修改).

        Args:
            vulns: 漏洞列表
            all_deps: 依赖列表 (in-place 写 vulnerabilities)
        """
        vuln_by_package: dict[str, list[Vulnerability]] = {}
        for v in vulns:
            vuln_by_package.setdefault(v.affected_package, []).append(v)

        for dep in all_deps:
            if dep.name in vuln_by_package:
                dep.vulnerabilities = vuln_by_package[dep.name]

    def _build_scan_summary(
        self,
        all_deps: list[Dependency],
        vulns: list[Vulnerability],
        license_issues: list[str],
    ) -> dict[str, int]:
        """构建扫描汇总字段.

        V2.20 P4-45 拆分: 抽 _count_vulns_by_severity 收口 4 行 vuln 计数,
        _count_direct_deps 收口 is_direct 计数, 主函数仅 dict 字面量构造.
        """
        return {
            "total_dependencies": len(all_deps),
            "direct_dependencies": self._count_direct_deps(all_deps),
            "vulnerabilities": len(vulns),
            "critical": self._count_vulns_by_severity(vulns, Severity.CRITICAL),
            "high": self._count_vulns_by_severity(vulns, Severity.HIGH),
            "medium": self._count_vulns_by_severity(vulns, Severity.MEDIUM),
            "low": self._count_vulns_by_severity(vulns, Severity.LOW),
            "license_issues": len(license_issues),
        }

    @staticmethod
    def _count_vulns_by_severity(vulns: list[Vulnerability], severity: Severity) -> int:
        """按 severity 计数 vulns (模块级 helper).

        Args:
            vulns: 漏洞列表
            severity: 严重等级

        Returns:
            该等级漏洞数
        """
        return sum(1 for v in vulns if v.severity == severity)

    @staticmethod
    def _count_direct_deps(deps: list[Dependency]) -> int:
        """计数直接依赖 (模块级 helper).

        Args:
            deps: 依赖列表

        Returns:
            is_direct=True 数量
        """
        return sum(1 for d in deps if d.is_direct)

    def _flatten_deps(self, deps: list[Dependency]) -> list[Dependency]:
        """扁平化依赖树"""
        result = []
        for dep in deps:
            result.append(dep)
            result.extend(self._flatten_deps(dep.dependencies))
        return result

    def generate_sbom(self, project_root: Path, output: Path | None = None) -> SBOM:
        """生成 SBOM (多语言支持)"""
        sbom = self.sbom_generator.generate_from_project(project_root)

        # 扫描漏洞并关联
        all_deps = self._flatten_deps(sbom.packages)
        vulns = self.osv_scanner.scan_dependencies(all_deps)

        vuln_by_package: dict[str, list[Vulnerability]] = {}
        for v in vulns:
            vuln_by_package.setdefault(v.affected_package, []).append(v)

        for dep in all_deps:
            if dep.name in vuln_by_package:
                dep.vulnerabilities = vuln_by_package[dep.name]

        # 更新 sbom
        sbom.packages = all_deps

        if output:
            output.write_text(sbom.to_json())

        return sbom
