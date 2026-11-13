"""Supply Chain 数据模型 (从 supply_chain.py 拆分).

Severity/LicensePolicy/Vulnerability/Dependency/SBOM/ScanResult.
供 _sc_sbom / _sc_scanners 复用, 由 supply_chain.py facade 统一 re-export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """漏洞严重性"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class LicensePolicy(str, Enum):
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
    # 清单文件里的版本约束符 (">=" / "==" 等)。version 只是约束的下界文本,
    # 不等于可安装版本 (如 ">=0.23" 的 version 是 "0.23", PyPI 上是 0.23.0),
    # 存在性校验必须结合约束符判断。
    specifier: str | None = None


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SBOM:
        """从字典还原 SBOM (与 to_dict 对称).

        供 `dep-graph --sbom <file>` 使用: 流水线里 SBOM 由上游作业生成,
        下游作业直接消费, 不必再扫一遍项目.

        Args:
            data: SBOM 字典 (SBOM.to_dict 的输出)

        Returns:
            还原后的 SBOM 对象
        """
        sbom = cls(
            spec_version=data.get("specVersion", "1.5"),
            spdx_version=data.get("spdxVersion", "SPDX-2.3"),
            name=data.get("name", ""),
            version=data.get("version", ""),
        )
        created_at = data.get("createdAt")
        if created_at:
            sbom.created_at = created_at
        sbom.packages = [cls._dep_from_dict(item) for item in data.get("packages", [])]
        sbom.relationships = list(data.get("relationships", []))
        return sbom

    @classmethod
    def _dep_from_dict(cls, data: dict[str, Any]) -> Dependency:
        """从字典还原依赖项 (含传递依赖)."""
        return Dependency(
            name=data.get("name", ""),
            version=data.get("version", ""),
            ecosystem=data.get("ecosystem", "pypi"),
            license=data.get("license"),
            is_direct=data.get("isDirect", True),
            vulnerabilities=[cls._vuln_from_dict(item) for item in data.get("vulnerabilities", []) if item],
            dependencies=[cls._dep_from_dict(item) for item in data.get("dependencies", [])],
        )

    @staticmethod
    def _vuln_from_dict(data: dict[str, Any]) -> Vulnerability:
        """从字典还原漏洞项 (SBOM 用 camelCase 字段名)."""
        severity = data.get("severity") or Severity.NONE.value
        try:
            severity_value = Severity(severity)
        except ValueError:
            severity_value = Severity.NONE
        return Vulnerability(
            id=data.get("id", ""),
            source=data.get("source", ""),
            summary=data.get("summary", ""),
            severity=severity_value,
            affected_package=data.get("affectedPackage", ""),
            affected_version=data.get("affectedVersion", ""),
            fixed_version=data.get("fixedVersion"),
            references=list(data.get("references", [])),
            published_at=data.get("publishedAt"),
            modified_at=data.get("modifiedAt"),
            cvss_score=data.get("cvssScore"),
            cvss_vector=data.get("cvssVector"),
        )

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
    # 待人工复核的许可证项 (未知许可证 / copyleft 等非阻断项)。
    # 与 license_issues (阻断项: 明确禁止的许可证) 分开存放。
    license_review: list[str] = field(default_factory=list)
    summary: dict[str, object] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    @property
    def total_vulns(self) -> int:
        return len(self.vulnerabilities)
