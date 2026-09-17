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

import subprocess  # noqa: F401  (测试通过 tools.scripts.supply_chain.subprocess 打 patch)
from pathlib import Path

from ._sc_models import (
    SBOM as SBOM,
)
from ._sc_models import (
    Dependency as Dependency,
)
from ._sc_models import (
    LicensePolicy as LicensePolicy,
)
from ._sc_models import (
    ScanResult as ScanResult,
)
from ._sc_models import (
    Severity as Severity,
)
from ._sc_models import (
    Vulnerability as Vulnerability,
)
from ._sc_sbom import SBOMGenerator as SBOMGenerator
from ._sc_scanners import (
    GHSASource as GHSASource,
)
from ._sc_scanners import (
    LicenseChecker as LicenseChecker,
)
from ._sc_scanners import (
    OSVScanner as OSVScanner,
)
from ._sc_scanners import (
    SignatureVerifier as SignatureVerifier,
)
from ._sc_scanners import (
    SupplyChainScanner as SupplyChainScanner,
)

__all__ = [
    "Severity",
    "LicensePolicy",
    "Vulnerability",
    "Dependency",
    "SBOM",
    "ScanResult",
    "OSVScanner",
    "GHSASource",
    "LicenseChecker",
    "SBOMGenerator",
    "SignatureVerifier",
    "SupplyChainScanner",
    "run_supply_chain_scan",
    "generate_sbom",
]


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
