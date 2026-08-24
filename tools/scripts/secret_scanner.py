"""
Secret 扫描模块

集成 gitleaks, trufflehog, detect-secrets
支持工作区、Git 历史、PR diff、容器镜像扫描
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SecretFinding:
    """单个秘钥发现"""

    tool: str  # gitleaks, trufflehog, detect-secrets
    rule_id: str
    file: str
    line: int
    column: int | None = None
    secret: str = ""
    entropy: float | None = None
    commit: str | None = None
    severity: str = "high"  # critical, high, medium, low
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_sarif(self) -> dict[str, Any]:
        """转换为 SARIF 格式"""
        return {
            "ruleId": self.rule_id,
            "level": "error" if self.severity in ("critical", "high") else "warning",
            "message": {"text": f"Secret detected: {self.rule_id}"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": self.file},
                        "region": {
                            "startLine": self.line,
                            "startColumn": self.column or 1,
                        },
                    }
                }
            ],
            "properties": {
                "tool": self.tool,
                "entropy": self.entropy,
                "commit": self.commit,
                "secretPreview": self.secret[:8] + "..." if self.secret else "",
            },
        }


@dataclass
class SecretScanResult:
    """扫描结果"""

    findings: list[SecretFinding] = field(default_factory=list)
    scanned_files: int = 0
    scan_duration_ms: int = 0
    tools_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(f.severity == "critical" for f in self.findings)

    @property
    def has_high(self) -> bool:
        return any(f.severity == "high" for f in self.findings)

    def to_sarif(self) -> dict[str, Any]:
        """转换为 SARIF 报告"""
        return {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {"driver": {"name": "jcode-secret-scan", "version": "1.0.0", "rules": []}},
                    "results": [f.to_sarif() for f in self.findings],
                }
            ],
        }

    def to_json(self) -> str:
        return json.dumps(
            {
                "findings": [f.__dict__ for f in self.findings],
                "scanned_files": self.scanned_files,
                "scan_duration_ms": self.scan_duration_ms,
                "tools_used": self.tools_used,
                "errors": self.errors,
            },
            indent=2,
            ensure_ascii=False,
        )


class SecretScanner:
    """秘钥扫描器"""

    def __init__(
        self,
        tools: list[str] | None = None,
        allowlist: list[str] | None = None,
        verify_active: bool = False,
        entropy_threshold: float = 4.5,
    ):
        self.tools = tools or ["gitleaks", "trufflehog"]
        self.allowlist = allowlist or []
        self.verify_active = verify_active
        self.entropy_threshold = entropy_threshold

    def _run_gitleaks(self, path: Path, scan_type: str) -> list[SecretFinding]:
        """运行 gitleaks"""
        findings = []
        cmd = ["gitleaks", "detect", "--source", str(path), "--report-format", "json", "--verbose"]

        if scan_type == "workspace":
            cmd.extend(["--no-git"])
        elif scan_type == "git-history":
            pass  # 默认扫描历史
        elif scan_type == "pr-diff":
            # gitleaks 支持 --staged 或 git diff
            cmd.extend(["--staged"])

        # 添加允许列表
        if self.allowlist:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
                f.write("[allowlist]\n")
                for pattern in self.allowlist:
                    f.write(f'  paths = ["{pattern}"]\n')
                allowlist_path = f.name
            cmd.extend(["--config", allowlist_path])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        findings.append(
                            SecretFinding(
                                tool="gitleaks",
                                rule_id=item.get("RuleID", "unknown"),
                                file=item.get("File", ""),
                                line=item.get("StartLine", 0),
                                column=item.get("StartColumn"),
                                secret=item.get("Secret", "")[:100],  # 截断
                                entropy=item.get("Entropy"),
                                commit=item.get("Commit"),
                                severity="high" if item.get("Entropy", 0) > self.entropy_threshold else "medium",
                            )
                        )
                except json.JSONDecodeError:
                    logger.warning("gitleaks output not valid JSON")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"gitleaks failed: {e}")

        return findings

    def _run_trufflehog(self, path: Path, scan_type: str) -> list[SecretFinding]:
        """运行 trufflehog"""
        findings: list[SecretFinding] = []

        if scan_type == "workspace":
            cmd = ["trufflehog", "filesystem", "--directory", str(path), "--json", "--no-verification"]
        elif scan_type == "git-history":
            cmd = ["trufflehog", "git", "--repo", str(path), "--json", "--no-verification"]
        elif scan_type == "pr-diff":
            cmd = ["trufflehog", "git", "--repo", str(path), "--json", "--no-verification", "--since-commit", "HEAD~1"]
        else:
            return findings

        if not self.verify_active:
            cmd.append("--no-verification")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    # trufflehog 输出结构
                    findings.append(
                        SecretFinding(
                            tool="trufflehog",
                            rule_id=item.get("DetectorType", "unknown"),
                            file=item.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file", ""),
                            line=item.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("line", 0),
                            secret=item.get("Raw", "")[:100],
                            entropy=None,
                            commit=item.get("SourceMetadata", {}).get("Data", {}).get("Git", {}).get("commit", ""),
                            severity="high",
                        )
                    )
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"trufflehog failed: {e}")

        return findings

    def _run_detect_secrets(self, path: Path, scan_type: str) -> list[SecretFinding]:
        """运行 detect-secrets (基线模式)"""
        findings: list[SecretFinding] = []

        if scan_type != "workspace":
            return findings  # detect-secrets 主要用于工作区

        # 生成/更新基线
        baseline_path = path / ".secrets.baseline"
        cmd = ["detect-secrets", "scan", "--baseline", str(baseline_path)]

        try:
            subprocess.run(cmd, cwd=path, capture_output=True, text=True, timeout=120)
            if baseline_path.exists():
                with open(baseline_path) as f:
                    baseline = json.load(f)
                for file_path, secrets in baseline.get("results", {}).items():
                    for secret in secrets:
                        findings.append(
                            SecretFinding(
                                tool="detect-secrets",
                                rule_id=secret.get("type", "unknown"),
                                file=file_path,
                                line=secret.get("line_number", 0),
                                column=None,
                                secret=secret.get("hashed_secret", "")[:20],
                                entropy=None,
                                commit=None,
                                severity="medium",
                            )
                        )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"detect-secrets failed: {e}")

        return findings

    def scan(
        self,
        path: Path,
        scan_workspace: bool = True,
        scan_git_history: bool = True,
        scan_pr_diff: bool = False,
    ) -> SecretScanResult:
        """执行扫描"""
        import time

        start = time.time()

        all_findings = []
        tools_used = []
        errors = []

        scan_types = []
        if scan_workspace:
            scan_types.append("workspace")
        if scan_git_history:
            scan_types.append("git-history")
        if scan_pr_diff:
            scan_types.append("pr-diff")

        for tool in self.tools:
            if tool == "gitleaks":
                tools_used.append("gitleaks")
                for st in scan_types:
                    try:
                        findings = self._run_gitleaks(path, st)
                        all_findings.extend(findings)
                    except Exception as e:
                        errors.append(f"gitleaks {st}: {e}")

            elif tool == "trufflehog":
                tools_used.append("trufflehog")
                for st in scan_types:
                    try:
                        findings = self._run_trufflehog(path, st)
                        all_findings.extend(findings)
                    except Exception as e:
                        errors.append(f"trufflehog {st}: {e}")

            elif tool == "detect-secrets":
                tools_used.append("detect-secrets")
                try:
                    findings = self._run_detect_secrets(path, "workspace")
                    all_findings.extend(findings)
                except Exception as e:
                    errors.append(f"detect-secrets: {e}")

        # 去重 (同文件同行同规则)
        seen = set()
        unique_findings = []
        for f in all_findings:
            key = (f.tool, f.rule_id, f.file, f.line)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        return SecretScanResult(
            findings=unique_findings,
            scanned_files=0,  # TODO: 统计
            scan_duration_ms=int((time.time() - start) * 1000),
            tools_used=tools_used,
            errors=errors,
        )


def scan_secrets(
    path: Path,
    tools: list[str] | None = None,
    allowlist: list[str] | None = None,
    scan_workspace: bool = True,
    scan_git_history: bool = True,
    scan_pr_diff: bool = False,
    verify_active: bool = False,
    entropy_threshold: float = 4.5,
    output_format: str = "text",
    output_file: Path | None = None,
) -> SecretScanResult:
    """便捷函数: 执行秘钥扫描"""
    scanner = SecretScanner(
        tools=tools,
        allowlist=allowlist,
        verify_active=verify_active,
        entropy_threshold=entropy_threshold,
    )

    result = scanner.scan(
        path,
        scan_workspace=scan_workspace,
        scan_git_history=scan_git_history,
        scan_pr_diff=scan_pr_diff,
    )

    # 输出
    if output_format == "sarif" and output_file:
        output_file.write_text(json.dumps(result.to_sarif(), indent=2))
    elif output_format == "json" and output_file:
        output_file.write_text(result.to_json())

    return result
