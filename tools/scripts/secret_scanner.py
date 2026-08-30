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
        """运行 gitleaks

        V2.21 P5-3 拆分: 抽 _build_gitleaks_cmd 收口 cmd 构造 (3 scan_type 守卫 + allowlist),
        _parse_gitleaks_output 收口 stdout 解析 + 9 字段 SecretFinding 构造,
        主函数仅 try/except + 委托.
        """
        cmd = self._build_gitleaks_cmd(path, scan_type)
        findings: list[SecretFinding] = []
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.stdout:
                findings = self._parse_gitleaks_output(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"gitleaks failed: {e}")
        return findings

    def _build_gitleaks_cmd(self, path: Path, scan_type: str) -> list[str]:
        """构造 gitleaks 命令行 (实例级 helper).

        Args:
            path: 扫描路径
            scan_type: workspace/git-history/pr-diff

        Returns:
            完整 cmd 列表
        """
        cmd = ["gitleaks", "detect", "--source", str(path), "--report-format", "json", "--verbose"]

        if scan_type == "workspace":
            cmd.extend(["--no-git"])
        elif scan_type == "pr-diff":
            cmd.extend(["--staged"])
        # git-history: 默认扫描历史, 无额外参数

        if self.allowlist:
            allowlist_path = self._write_allowlist_file()
            if allowlist_path is not None:
                cmd.extend(["--config", allowlist_path])

        return cmd

    def _write_allowlist_file(self) -> str | None:
        """写入 gitleaks allowlist 临时文件 (实例级 helper).

        Returns:
            临时文件路径 (None if 写入失败)
        """
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
                f.write("[allowlist]\n")
                for pattern in self.allowlist:
                    f.write(f'  paths = ["{pattern}"]\n')
                return f.name
        except OSError as e:
            logger.warning(f"Failed to write allowlist file: {e}")
            return None

    def _parse_gitleaks_output(self, stdout: str) -> list[SecretFinding]:
        """解析 gitleaks JSON 输出 (实例级 helper).

        Args:
            stdout: gitleaks 原始输出

        Returns:
            SecretFinding 列表
        """
        findings: list[SecretFinding] = []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("gitleaks output not valid JSON")
            return findings

        for item in data:
            findings.append(self._build_gitleaks_finding(item))
        return findings

    def _build_gitleaks_finding(self, item: dict[str, Any]) -> SecretFinding:
        """从 gitleaks item 构造 SecretFinding (实例级 helper).

        Args:
            item: gitleaks JSON item

        Returns:
            SecretFinding 对象
        """
        entropy = item.get("Entropy", 0)
        return SecretFinding(
            tool="gitleaks",
            rule_id=item.get("RuleID", "unknown"),
            file=item.get("File", ""),
            line=item.get("StartLine", 0),
            column=item.get("StartColumn"),
            secret=item.get("Secret", "")[:100],  # 截断
            entropy=entropy,
            commit=item.get("Commit"),
            severity="high" if entropy > self.entropy_threshold else "medium",
        )

    def _run_trufflehog(self, path: Path, scan_type: str) -> list[SecretFinding]:
        """运行 trufflehog (V2.21 P5-9 拆分: 抽 _build_trufflehog_cmd + _parse_trufflehog_finding)."""
        findings: list[SecretFinding] = []
        cmd = self._build_trufflehog_cmd(path, scan_type)
        if not cmd:
            return findings
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    findings.append(self._parse_trufflehog_finding(item))
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"trufflehog failed: {e}")

        return findings

    def _build_trufflehog_cmd(self, path: Path, scan_type: str) -> list[str] | None:
        """构造 trufflehog 命令 (模块级 helper, 4 档 scan_type → cmd).

        Args:
            path: 扫描根路径
            scan_type: workspace/git-history/pr-diff

        Returns:
            cmd 列表, 未知 scan_type 返回 None
        """
        cmd_map: dict[str, list[str]] = {
            "workspace": ["trufflehog", "filesystem", "--directory", str(path), "--json", "--no-verification"],
            "git-history": ["trufflehog", "git", "--repo", str(path), "--json", "--no-verification"],
            "pr-diff": [
                "trufflehog",
                "git",
                "--repo",
                str(path),
                "--json",
                "--no-verification",
                "--since-commit",
                "HEAD~1",
            ],
        }
        cmd = cmd_map.get(scan_type)
        if cmd is None:
            return None
        if not self.verify_active:
            cmd.append("--no-verification")
        return cmd

    def _parse_trufflehog_finding(self, item: dict[str, Any]) -> SecretFinding:
        """解析单条 trufflehog JSON finding (trufflehog 输出结构 嵌套较深).

        Args:
            item: trufflehog JSON 字典

        Returns:
            SecretFinding 实例
        """
        sm = item.get("SourceMetadata", {}).get("Data", {})
        fs = sm.get("Filesystem", {})
        git = sm.get("Git", {})
        return SecretFinding(
            tool="trufflehog",
            rule_id=item.get("DetectorType", "unknown"),
            file=fs.get("file", ""),
            line=fs.get("line", 0),
            secret=item.get("Raw", "")[:100],
            entropy=None,
            commit=git.get("commit", ""),
            severity="high",
        )

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
        """执行扫描

        V2.21 P5-2 拆分: 抽 _run_tool 收口单 tool × scan_types 调度,
        _deduplicate_findings 收口 4 元组去重 for,
        主函数仅 scan_types 构造 + 调度 + 去重 + 组装.
        """
        import time

        start = time.time()

        all_findings: list[SecretFinding] = []
        tools_used: list[str] = []
        errors: list[str] = []

        scan_types = self._build_scan_types(scan_workspace, scan_git_history, scan_pr_diff)

        for tool in self.tools:
            _run_tool(self, tool, path, scan_types, all_findings, tools_used, errors)

        unique_findings = _deduplicate_findings(all_findings)

        return SecretScanResult(
            findings=unique_findings,
            scanned_files=0,  # TODO: 统计
            scan_duration_ms=int((time.time() - start) * 1000),
            tools_used=tools_used,
            errors=errors,
        )

    def _build_scan_types(self, scan_workspace: bool, scan_git_history: bool, scan_pr_diff: bool) -> list[str]:
        """构造 scan_types 列表 (实例级 helper).

        Args:
            scan_workspace: 是否扫描 workspace
            scan_git_history: 是否扫描 git 历史
            scan_pr_diff: 是否扫描 PR diff

        Returns:
            scan_types 列表
        """
        scan_types: list[str] = []
        if scan_workspace:
            scan_types.append("workspace")
        if scan_git_history:
            scan_types.append("git-history")
        if scan_pr_diff:
            scan_types.append("pr-diff")
        return scan_types


def _run_tool(
    scanner: SecretScanner,
    tool: str,
    path: Path,
    scan_types: list[str],
    all_findings: list[SecretFinding],
    tools_used: list[str],
    errors: list[str],
) -> None:
    """执行单 tool 扫描 (模块级 helper, in-place 修改 3 列表).

    Args:
        scanner: SecretScanner 实例
        tool: 工具名 (gitleaks/trufflehog/detect-secrets)
        path: 扫描路径
        scan_types: 扫描类型列表
        all_findings: 累积 findings (in-place)
        tools_used: 工具名累积 (in-place)
        errors: 错误累积 (in-place)
    """
    tool_runners = {
        "gitleaks": scanner._run_gitleaks,
        "trufflehog": scanner._run_trufflehog,
    }
    if tool in tool_runners:
        tools_used.append(tool)
        runner = tool_runners[tool]
        for st in scan_types:
            try:
                findings = runner(path, st)
                all_findings.extend(findings)
            except Exception as e:
                errors.append(f"{tool} {st}: {e}")
    elif tool == "detect-secrets":
        tools_used.append(tool)
        try:
            findings = scanner._run_detect_secrets(path, "workspace")
            all_findings.extend(findings)
        except Exception as e:
            errors.append(f"detect-secrets: {e}")


def _deduplicate_findings(findings: list[SecretFinding]) -> list[SecretFinding]:
    """按 (tool, rule_id, file, line) 4 元组去重 (模块级 helper).

    Args:
        findings: 候选 findings 列表

    Returns:
        去重后 findings 列表
    """
    seen: set[tuple[str, str, str, int]] = set()
    unique: list[SecretFinding] = []
    for f in findings:
        key = (f.tool, f.rule_id, f.file, f.line)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


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
