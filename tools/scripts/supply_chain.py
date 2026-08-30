"""
Supply Chain Security Module

核心功能:
- OSV/GHSA 漏洞扫描
- 许可证合规检查
- SBOM (Software Bill of Materials) 生成
- 签名验证
- 依赖图分析
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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


@dataclass
class SBOM:
    """Software Bill of Materials"""

    spec_version: str = "1.5"
    spdx_version: str = "SPDX-2.3"
    name: str = ""
    version: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
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
    scanned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
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
        """批量扫描依赖漏洞"""
        # 按生态系统分组
        queries = []
        for dep in dependencies:
            ecosystem = self.ECOSYSTEM_MAP.get(dep.ecosystem.lower(), dep.ecosystem)
            queries.append(
                {
                    "package": {"name": dep.name, "ecosystem": ecosystem},
                    "version": dep.version,
                }
            )

        if not queries:
            return []

        # 批量查询 OSV API
        try:
            payload = json.dumps({"queries": queries}).encode()
            req = urllib.request.Request(
                self.OSV_API,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:  # nosec B310
                data = json.loads(response.read().decode())

            vulns = []
            for i, result in enumerate(data.get("results", [])):
                dep = dependencies[i]
                for vuln_data in result.get("vulns", []):
                    vulns.append(self._parse_osv_vuln(vuln_data, dep))
            return vulns

        except Exception as e:
            logger.warning(f"OSV scan failed: {e}")
            return []

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


class GHSASource:
    """GHSA (GitHub Security Advisories) 数据源"""

    def __init__(self, github_token: str | None = None):
        self.github_token = github_token

    def fetch_advisories(self, ecosystem: str, package: str) -> list[Vulnerability]:
        """获取 GHSA 公告 (需要 GitHub API)"""
        # 简化实现：实际需要调用 GitHub GraphQL API
        # 这里返回空列表，实际使用时需集成 GitHub API
        return []


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
        """检查单个许可证"""
        if not license_str:
            return LicensePolicy.REVIEW

        # 标准化许可证字符串
        license_str = license_str.strip()

        # 直接策略匹配
        if license_str in self.policy:
            return self.policy[license_str]

        # 基于分类的默认策略
        if license_str in self.PERMISSIVE_LICENSES:
            return LicensePolicy.ALLOW
        elif license_str in self.COPYLEFT_LICENSES:
            return LicensePolicy.REVIEW  # 需要人工评估
        elif license_str in self.PROPRIETARY_LICENSES:
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


class SBOMGenerator:
    """SBOM 生成器"""

    def __init__(self) -> None:
        pass

    def generate_from_python(self, project_root: Path) -> SBOM:
        """从 Python 项目生成 SBOM"""
        sbom = SBOM()
        sbom.name = project_root.name

        # 读取 pyproject.toml 或 requirements.txt
        deps = self._parse_python_deps(project_root)
        for dep in deps:
            sbom.packages.append(dep)

        # 添加关系
        for i, dep in enumerate(sbom.packages):
            sbom.relationships.append(
                {
                    "spdxElementId": f"SPDXRef-Package-{i}",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-Package-ROOT",
                }
            )

        return sbom

    def _collect_all_dependencies(self, project_root: Path) -> list[Dependency]:
        """收集全部生态的依赖声明。"""
        all_deps: list[Dependency] = []
        parsers = [
            self._parse_python_deps,
            self._parse_npm_deps,
            self._parse_cargo_deps,
            self._parse_go_deps,
            self._parse_maven_deps,
            self._parse_gradle_deps,
            self._parse_gemfile_deps,
            self._parse_composer_deps,
            self._parse_nuget_deps,
        ]
        for parser in parsers:
            all_deps.extend(parser(project_root))
        return all_deps

    @staticmethod
    def _dedupe_dependencies(deps: list[Dependency]) -> list[Dependency]:
        """按 name+version+ecosystem 去重。"""
        seen: set[tuple[str, str, str]] = set()
        unique: list[Dependency] = []
        for dep in deps:
            key = (dep.name, dep.version, dep.ecosystem)
            if key not in seen:
                seen.add(key)
                unique.append(dep)
        return unique

    def generate_from_project(self, project_root: Path) -> SBOM:
        """自动检测项目语言并生成完整 SBOM"""
        sbom = SBOM()
        sbom.name = project_root.name

        sbom.packages = self._dedupe_dependencies(self._collect_all_dependencies(project_root))

        # 添加关系
        for i in range(len(sbom.packages)):
            sbom.relationships.append(
                {
                    "spdxElementId": f"SPDXRef-Package-{i}",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-Package-ROOT",
                }
            )

        return sbom

    def _parse_python_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Python 依赖"""
        deps = []

        # 尝试解析 pyproject.toml
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            deps.extend(self._parse_pyproject(pyproject))

        # 尝试解析 requirements.txt
        req_file = project_root / "requirements.txt"
        if req_file.exists():
            deps.extend(self._parse_requirements(req_file))

        # 尝试解析 poetry.lock
        poetry_lock = project_root / "poetry.lock"
        if poetry_lock.exists():
            deps.extend(self._parse_poetry_lock(poetry_lock))

        # 尝试解析 pipenv.lock
        pipenv_lock = project_root / "Pipfile.lock"
        if pipenv_lock.exists():
            deps.extend(self._parse_pipenv_lock(pipenv_lock))

        return deps

    def _parse_pyproject(self, path: Path) -> list[Dependency]:
        """解析 pyproject.toml 依赖 (project.dependencies + tool.poetry.dependencies).

        V2.20 P4-42 拆分: 抽 _parse_project_dependencies + _parse_poetry_dependencies
        收口两个 dep 块解析, 主函数仅 try/except + 调用.
        """
        deps: list[Dependency] = []
        try:
            import tomllib

            with open(path, "rb") as f:
                data = tomllib.load(f)
            deps.extend(self._parse_project_dependencies(data))
            deps.extend(self._parse_poetry_dependencies(data))
        except Exception as e:
            logger.warning(f"Failed to parse pyproject.toml: {e}")
        return deps

    def _parse_project_dependencies(self, data: dict[str, object]) -> list[Dependency]:
        """解析 [project] dependencies 块.

        Args:
            data: tomllib 解析后的字典

        Returns:
            dependency 列表
        """
        project = data.get("project", {})
        deps: list[Dependency] = []
        for dep_spec in project.get("dependencies", []):  # type: ignore[attr-defined]
            dep = self._parse_dep_spec(dep_spec)
            if dep:
                deps.append(dep)
        return deps

    def _parse_poetry_dependencies(self, data: dict[str, object]) -> list[Dependency]:
        """解析 [tool.poetry] dependencies 块 (排除 python).

        Args:
            data: tomllib 解析后的字典

        Returns:
            dependency 列表
        """
        poetry = data.get("tool", {}).get("poetry", {})  # type: ignore[attr-defined]
        deps: list[Dependency] = []
        for name, spec in poetry.get("dependencies", {}).items():
            if name == "python":
                continue
            dep = self._parse_poetry_dep(name, spec)
            if dep:
                deps.append(dep)
        return deps

    def _parse_requirements(self, path: Path) -> list[Dependency]:
        deps = []
        try:
            content = path.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    dep = self._parse_dep_spec(line)
                    if dep:
                        deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse requirements.txt: {e}")
        return deps

    def _parse_poetry_lock(self, path: Path) -> list[Dependency]:
        deps = []
        try:
            import tomllib

            with open(path, "rb") as f:
                data = tomllib.load(f)

            for pkg in data.get("package", []):
                dep = Dependency(
                    name=pkg.get("name", ""),
                    version=pkg.get("version", ""),
                    ecosystem="pypi",
                    is_direct=True,
                )
                deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse poetry.lock: {e}")
        return deps

    def _parse_pipenv_lock(self, path: Path) -> list[Dependency]:
        deps = []
        try:
            with open(path) as f:
                data = json.load(f)

            for name, info in data.get("default", {}).items():
                version = info.get("version", "").lstrip("==")
                dep = Dependency(
                    name=name,
                    version=version,
                    ecosystem="pypi",
                    is_direct=True,
                )
                deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse Pipfile.lock: {e}")
        return deps

    @staticmethod
    def _parse_package_json(project_root: Path) -> list[Dependency]:
        """解析 package.json 的直接依赖。"""
        deps: list[Dependency] = []
        package_json = project_root / "package.json"
        if not package_json.exists():
            return deps
        try:
            with open(package_json) as f:
                data = json.load(f)
            for dep_type in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
                for name, version in data.get(dep_type, {}).items():
                    deps.append(Dependency(name=name, version=version.lstrip("^~>="), ecosystem="npm", is_direct=True))
        except Exception as e:
            logger.warning(f"Failed to parse package.json: {e}")
        return deps

    @staticmethod
    def _parse_package_lock(project_root: Path) -> list[Dependency]:
        """解析 package-lock.json 获取准确版本和传递依赖 (v2 packages 格式)。"""
        deps: list[Dependency] = []
        lock_file = project_root / "package-lock.json"
        if not lock_file.exists():
            return deps
        try:
            with open(lock_file) as f:
                data = json.load(f)
            for path, info in data.get("packages", {}).items():
                if path == "":
                    continue
                name = path.split("node_modules/")[-1]
                deps.append(
                    Dependency(
                        name=name,
                        version=info.get("version", ""),
                        ecosystem="npm",
                        is_direct=not info.get("dev", False),
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to parse package-lock.json: {e}")
        return deps

    def _parse_npm_deps(self, project_root: Path) -> list[Dependency]:
        """解析 npm 依赖 (package.json + package-lock.json)"""
        return self._parse_package_json(project_root) + self._parse_package_lock(project_root)

    @staticmethod
    def _load_toml(path: Path) -> dict[str, Any]:
        """加载 TOML 文件; 失败返回空字典。"""
        import tomllib

        with open(path, "rb") as f:
            return tomllib.load(f)

    def _parse_cargo_toml(self, project_root: Path) -> list[Dependency]:
        """解析 Cargo.toml 的直接依赖声明.

        V2.20 P4-43 拆分: 抽 _extract_cargo_version 收口 spec 字符串/字典类型判断,
        主函数仅 3 类 dep 遍历 + Dependency 构造.
        """
        deps: list[Dependency] = []
        cargo_toml = project_root / "Cargo.toml"
        if not cargo_toml.exists():
            return deps
        try:
            data = self._load_toml(cargo_toml)
            for dep_type in ["dependencies", "dev-dependencies", "build-dependencies"]:
                for name, spec in data.get(dep_type, {}).items():
                    version = self._extract_cargo_version(spec)
                    deps.append(Dependency(name=name, version=version, ecosystem="cargo", is_direct=True))
        except Exception as e:
            logger.warning(f"Failed to parse Cargo.toml: {e}")
        return deps

    @staticmethod
    def _extract_cargo_version(spec: object) -> str:
        """从 Cargo.toml spec 提取版本字符串.

        Args:
            spec: TOML spec (str 直接为版本 / dict 含 version 键 / 其他空字符串)

        Returns:
            version 字符串
        """
        if isinstance(spec, str):
            return spec
        if isinstance(spec, dict):
            return spec.get("version", "")
        return ""

    def _parse_cargo_lock(self, project_root: Path) -> list[Dependency]:
        """解析 Cargo.lock 的全部传递依赖。"""
        deps: list[Dependency] = []
        cargo_lock = project_root / "Cargo.lock"
        if not cargo_lock.exists():
            return deps
        try:
            data = self._load_toml(cargo_lock)
            for pkg in data.get("package", []):
                deps.append(
                    Dependency(
                        name=pkg.get("name", ""),
                        version=pkg.get("version", ""),
                        ecosystem="cargo",
                        is_direct=False,  # Cargo.lock 包含所有传递依赖
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to parse Cargo.lock: {e}")
        return deps

    def _parse_cargo_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Cargo 依赖 (Cargo.toml + Cargo.lock)"""
        return self._parse_cargo_toml(project_root) + self._parse_cargo_lock(project_root)

    def _parse_go_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Go 依赖 (go.mod + go.sum).

        V2.20 P4-39 拆分: 抽 _parse_go_require_line 收口单行解析,
        主函数仅 try/except 包裹 + state machine 遍历.
        """
        deps: list[Dependency] = []
        go_mod = project_root / "go.mod"
        if not go_mod.exists():
            return deps
        try:
            content = go_mod.read_text()
            in_require = False
            for line in content.splitlines():
                dep, in_require = self._parse_go_require_line(line.strip(), in_require)
                if dep is not None:
                    deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse go.mod: {e}")
        return deps

    def _parse_go_require_line(self, line: str, in_require: bool) -> tuple[Dependency | None, bool]:
        """解析单行 go.mod, 返回 (dep_or_None, new_in_require).

        Args:
            line: 已 strip 的行
            in_require: 当前是否在 require () 块内

        Returns:
            (Dependency 或 None, 更新后的 in_require 状态)
        """
        if line.startswith("require ("):
            return None, True
        if in_require and line == ")":
            return None, False
        if not (in_require or line.startswith("require ")):
            return None, in_require

        parts = line.replace("require ", "").split()
        if len(parts) < 2:
            return None, in_require
        return (
            Dependency(
                name=parts[0],
                version=parts[1],
                ecosystem="go",
                is_direct=True,
            ),
            in_require,
        )

    def _parse_maven_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Maven 依赖 (pom.xml).

        V2.20 P4-40 拆分: 抽 _extract_maven_dep 收口单 dep XML 解析,
        _parse_pom_xml 收口 XML 加载 + 遍历, 主函数仅文件存在 + try/except.
        """
        deps: list[Dependency] = []
        pom_xml = project_root / "pom.xml"
        if not pom_xml.exists():
            return deps
        try:
            deps = self._parse_pom_xml(pom_xml)
        except Exception as e:
            logger.warning(f"Failed to parse pom.xml: {e}")
        return deps

    def _parse_pom_xml(self, pom_xml: Path) -> list[Dependency]:
        """解析 pom.xml 文件, 提取所有 dependencies.

        Args:
            pom_xml: pom.xml 路径

        Returns:
            dependency 列表
        """
        import xml.etree.ElementTree as ET

        tree = ET.parse(pom_xml)  # nosec B320 - parsing local trusted pom.xml
        root = tree.getroot()
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        deps: list[Dependency] = []
        for dep_elem in root.findall(".//m:dependency", ns):
            dep = self._extract_maven_dep(dep_elem, ns)
            if dep is not None:
                deps.append(dep)
        return deps

    def _extract_maven_dep(self, dep_elem: object, ns: dict[str, str]) -> Dependency | None:
        """从 XML dependency 元素提取 Dependency 对象.

        Args:
            dep_elem: XML dependency 元素
            ns: Maven 命名空间

        Returns:
            Dependency 对象 (None if groupId/artifactId 缺失)
        """
        group_id = dep_elem.find("m:groupId", ns)  # type: ignore[attr-defined]
        artifact_id = dep_elem.find("m:artifactId", ns)  # type: ignore[attr-defined]
        version_elem = dep_elem.find("m:version", ns)  # type: ignore[attr-defined]
        scope_elem = dep_elem.find("m:scope", ns)  # type: ignore[attr-defined]

        if group_id is None or artifact_id is None:
            return None

        version = version_elem.text if version_elem is not None else ""
        scope = scope_elem.text if scope_elem is not None else "compile"
        return Dependency(
            name=f"{group_id.text}:{artifact_id.text}",
            version=version or "",
            ecosystem="maven",
            is_direct=scope == "compile",
        )

    def _parse_gradle_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Gradle 依赖 (build.gradle / build.gradle.kts)。"""
        deps: list[Dependency] = []
        for gradle_name in ("build.gradle", "build.gradle.kts"):
            gradle_file = project_root / gradle_name
            if not gradle_file.exists():
                continue
            try:
                content = gradle_file.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                logger.warning(f"Failed to parse {gradle_name}: {e}")
                continue
            # 匹配 implementation/api/testImplementation 'group:artifact:version' 两种引号风格
            import re

            pattern = re.compile(
                r"""(?:implementation|api|compile|runtimeOnly|testImplementation)\s+['"]([^'":]+):([^'":]+):([^'"]+)['"]"""
            )
            for match in pattern.finditer(content):
                group, artifact, version = match.group(1), match.group(2), match.group(3)
                deps.append(
                    Dependency(
                        name=f"{group}:{artifact}",
                        version=version.strip(),
                        ecosystem="maven",
                        is_direct=True,
                    )
                )
        return deps

    def _parse_gemfile_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Ruby 依赖 (Gemfile + Gemfile.lock)。"""
        deps: list[Dependency] = []
        gemfile = project_root / "Gemfile"
        if not gemfile.exists():
            return deps
        try:
            content = gemfile.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logger.warning(f"Failed to parse Gemfile: {e}")
            return deps
        import re

        # 匹配 gem "rails", "~> 7.0" 与 gem 'sinatra', '4.0'
        for match in re.compile(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", re.M).finditer(content):
            name = match.group(1)
            version = (match.group(2) or "").lstrip("~><= ")
            deps.append(Dependency(name=name, version=version, ecosystem="rubygems", is_direct=True))
        return deps

    def _parse_composer_deps(self, project_root: Path) -> list[Dependency]:
        """解析 PHP 依赖 (composer.json require 段)。"""
        composer_json = project_root / "composer.json"
        if not composer_json.exists():
            return []
        try:
            with open(composer_json, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to parse composer.json: {e}")
            return []
        deps = []
        for name, constraint in (data.get("require") or {}).items():
            if name == "php":
                continue
            version = constraint.lstrip("v^~>=< ")
            deps.append(Dependency(name=name, version=version, ecosystem="packagist", is_direct=True))
        return deps

    def _parse_nuget_deps(self, project_root: Path) -> list[Dependency]:
        """解析 .NET 依赖 (csproj 的 PackageReference)。"""
        deps: list[Dependency] = []
        csproj_files = list(project_root.rglob("*.csproj"))
        if not csproj_files:
            return deps
        import re

        for csproj in csproj_files[:20]:  # 防御超大仓库
            try:
                content = csproj.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                logger.warning(f"Failed to parse {csproj.name}: {e}")
                continue
            for match in re.compile(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"').finditer(content):
                deps.append(
                    Dependency(
                        name=match.group(1),
                        version=match.group(2),
                        ecosystem="nuget",
                        is_direct=True,
                    )
                )
        return deps

    def _parse_dep_spec(self, spec: str) -> Dependency | None:
        """解析依赖规格"""
        # 简化解析: package>=1.0, package==1.0, package~=1.0
        import re

        match = re.match(r"^([A-Za-z0-9_.-]+)([=<>!~]+.*)?$", spec.strip())
        if match:
            name = match.group(1)
            version = match.group(2).lstrip("=<>~!") if match.group(2) else ""
            return Dependency(name=name, version=version, ecosystem="pypi")
        return None

    def _parse_poetry_dep(self, name: str, spec: str | dict[str, Any]) -> Dependency | None:
        if isinstance(spec, str):
            return Dependency(name=name, version=spec, ecosystem="pypi")
        elif isinstance(spec, dict):
            return Dependency(name=name, version=spec.get("version", ""), ecosystem="pypi")
        return None


class SignatureVerifier:
    """签名验证器"""

    def __init__(self) -> None:
        pass

    def verify_pypi_package(self, name: str, version: str) -> dict[str, Any]:
        """验证 PyPI 包签名 (需要 PyPI API)"""
        # 简化实现
        return {"verified": False, "message": "Not implemented"}

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
        """验证 SLSA provenance"""
        # 简化实现
        return {"verified": False, "message": "Not implemented"}


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


def run_supply_chain_scan(
    project_root: Path,
    osv_timeout: int = 30,
    license_policy: dict[str, LicensePolicy] | None = None,
) -> ScanResult:
    """便捷函数: 运行供应链扫描"""
    scanner = SupplyChainScanner(osv_timeout=osv_timeout, license_policy=license_policy)
    return scanner.scan_project(project_root)


def generate_sbom(
    project_root: Path,
    output: Path | None = None,
) -> SBOM:
    """便捷函数: 生成 SBOM"""
    scanner = SupplyChainScanner()
    return scanner.generate_sbom(project_root, output)
