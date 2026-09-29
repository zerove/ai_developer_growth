"""Supply Chain 数据模型 (从 supply_chain.py 拆分).

Severity/LicensePolicy/Vulnerability/Dependency/SBOM/ScanResult.
供 _sc_sbom / _sc_scanners 复用, 由 supply_chain.py facade 统一 re-export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """漏洞严重性"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class LicensePolicy(StrEnum):
    """许可证策略"""

    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


@dataclass
class Vulnerability:
    """漏洞信息"""

    id: str  # CVE-xxxx-xxxx or GHSA-xxxx
    source: str  # OSV, GHSA
    summary: str
    severity: Severity
    affected_package: str
    affected_version: str
    fixed_version: str | None = None
    references: list[str] = field(default_factory=list)
    published_at: str | None = None
    modified_at: str | None = None
    cvss_score: float | None = None
    cvss_vector: str | None = None


@dataclass
class Dependency:
    """依赖项"""

    name: str
    version: str
    ecosystem: str  # pypi, npm, cargo, go, maven, etc.
    license: str | None = None
    license_policy: LicensePolicy = LicensePolicy.REVIEW
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    is_direct: bool = True
    dependencies: list[Dependency] = field(default_factory=list)  # 传递依赖


@dataclass
class SBOM:
    """Software Bill of Materials"""

    spec_version: str = "1.5"
    spdx_version: str = "SPDX-2.3"
    name: str = ""
    version: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
    packages: list[Dependency] = field(default_factory=list)
    relationships: list[dict[str, str]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "specVersion": self.spec_version,
            "spdxVersion": self.spdx_version,
            "name": self.name,
            "version": self.version,
            "createdAt": self.created_at,
            "packages": [self._dep_to_dict(p) for p in self.packages],
            "relationships": self.relationships,
        }

    def _dep_to_dict(self, dep: Dependency) -> dict[str, Any]:
        return {
            "name": dep.name,
            "version": dep.version,
            "ecosystem": dep.ecosystem,
            "license": dep.license,
            "licensePolicy": dep.license_policy.value,
            "vulnerabilities": [self._vuln_to_dict(v) for v in dep.vulnerabilities],
            "isDirect": dep.is_direct,
            "dependencies": [self._dep_to_dict(d) for d in dep.dependencies],
        }

    def _vuln_to_dict(self, vuln: Vulnerability) -> dict[str, Any]:
        return {
            "id": vuln.id,
            "source": vuln.source,
            "summary": vuln.summary,
            "severity": vuln.severity.value,
            "affectedPackage": vuln.affected_package,
            "affectedVersion": vuln.affected_version,
            "fixedVersion": vuln.fixed_version,
            "references": vuln.references,
            "publishedAt": vuln.published_at,
            "modifiedAt": vuln.modified_at,
            "cvssScore": vuln.cvss_score,
            "cvssVector": vuln.cvss_vector,
        }


@dataclass
class ScanResult:
    """扫描结果"""

    project_path: str
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
    dependencies: list[Dependency] = field(default_factory=list)
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    license_issues: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    @property
    def total_vulns(self) -> int:
        return len(self.vulnerabilities)
