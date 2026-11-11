#!/usr/bin/env python3
"""校验治理文档里引用的**仓库代码路径**是否仍然存在（D-02）。

## 为什么需要

`link_auditor` 只校验 markdown **链接**可达, 不校验正文里以文本形式出现的
代码路径（``tools/scripts/foo.py``）。于是文档改名/删除脚本后, 正文仍指向
旧路径 —— 读者按图索骥找不到东西, 而门禁毫无反应（静默失真）。

实测（2026-11-12）: 治理类文档 157 篇里, 有 17 处指向已不存在的路径, 例如
``tools/scripts/adr-generator.py``（实际为 ``adr_generator.py``）、
``tools/scripts/cicd_dashboard.py``（实际为 ``adg cicd` 子命令）。

## 检查范围

默认只扫**当前状态**文档 —— 历史性文档（ADR、报告、路线图、版本快照）本就会
引用当时不存在的路径, 强查只会制造噪音:

    docs/api, docs/specs, docs/governance, docs/analysis, CONTEXT.md, README.md

## 用法

    python tools/scripts/check_doc_code_refs.py                 # 文本报告
    python tools/scripts/check_doc_code_refs.py --json          # JSON 输出
    python tools/scripts/check_doc_code_refs.py --path docs/api  # 自定义范围
    python tools/scripts/check_doc_code_refs.py --warn-only      # 只报告不失败

退出码: 0 无问题 / 1 发现失效引用（或 JSON 模式下有 findings）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # python -m tools.scripts.check_doc_code_refs (根已在 path)
    from tools.scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # python tools/scripts/check_doc_code_refs.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 只认这些顶层目录开头的路径 —— 其它（main.py / index.ts 之类）是示例文件名,
# 不是仓库路径, 强查只会误报。
REPO_PATH_PREFIXES = (
    "tools/",
    "ai-dev-framework/",
    "examples/",
    ".jcode/",
    "agents/",
    "scripts/",
    ".adg/",
    "tests/",
)

_CODE_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:" + "|".join(re.escape(p) for p in REPO_PATH_PREFIXES) + r")[\w./-]*"
    r"\.(?:py|ts|tsx|js|yml|yaml|md|toml|json|sh))(?![\w])"
)

# 明显是占位符的路径（X.py / foo.py / your_module.py ...）
_PLACEHOLDER_RE = re.compile(r"(^|/)(X|foo|bar|baz|ghost|your_[a-z_]+|example|sample|dummy|placeholder)[._-]", re.I)

DEFAULT_PATHS = (
    "docs/api",
    "docs/specs",
    "docs/governance",
    "docs/analysis",
    "CONTEXT.md",
    "README.md",
)

DEFAULT_ALLOWLIST = ".jcode/doc-ref-allowlist.json"


@dataclass
class Finding:
    """一条失效的代码路径引用。"""

    doc: str
    line: int
    ref: str

    def to_dict(self) -> dict[str, object]:
        return {"doc": self.doc, "line": self.line, "ref": self.ref}


def _iter_docs(paths: list[str], root: Path = REPO_ROOT) -> list[Path]:
    """展开检查范围为 markdown 文件列表（去重且保持顺序）。"""
    docs: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        target = Path(raw)
        if not target.is_absolute():
            target = root / target
        candidates = sorted(target.rglob("*.md")) if target.is_dir() else [target]
        for candidate in candidates:
            if candidate.is_file() and candidate not in seen:
                seen.add(candidate)
                docs.append(candidate)
    return docs


def _load_allowlist(path: Path) -> dict[str, str]:
    """读取豁免清单: {路径: 原因}。文件缺失时返回空（不 fail-open 到"全忽略"）。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: 豁免清单读取失败, 按空清单处理: {path} ({exc})", file=sys.stderr)
        return {}
    entries = data.get("allowlist") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}
    allowlist: dict[str, str] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            allowlist[entry["path"]] = str(entry.get("reason", ""))
    return allowlist


def scan_docs(docs: list[Path], allowlist: dict[str, str], root: Path = REPO_ROOT) -> list[Finding]:
    """扫描文档, 返回失效引用列表。"""
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for doc in docs:
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        doc_key = str(doc)
        try:
            doc_key = str(doc.relative_to(root))
        except ValueError:
            pass
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in _CODE_PATH_RE.finditer(line):
                ref = match.group(1)
                if ref in allowlist:
                    continue
                if _PLACEHOLDER_RE.search(ref):
                    continue
                if (root / ref).exists():
                    continue
                key = (doc_key, lineno, ref)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(Finding(doc=doc_key, line=lineno, ref=ref))
    return findings


def _report_text(findings: list[Finding], allowlist: dict[str, str]) -> str:
    lines = [f"文档代码路径检查: {len(findings)} 处失效引用"]
    for finding in findings:
        lines.append(f"  {finding.doc}:{finding.line} → {finding.ref}")
    if allowlist:
        lines.append(f"（已豁免 {len(allowlist)} 条）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验治理文档引用的仓库代码路径是否仍存在")
    parser.add_argument("--path", action="append", dest="paths", help="检查范围（可重复）")
    parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="豁免清单路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--warn-only", action="store_true", help="只报告, 不以非零码退出")
    args = parser.parse_args(argv)

    paths = args.paths or list(DEFAULT_PATHS)
    docs = _iter_docs(paths, REPO_ROOT)
    allowlist_path = REPO_ROOT / args.allowlist if not Path(args.allowlist).is_absolute() else Path(args.allowlist)
    allowlist = _load_allowlist(allowlist_path)
    findings = scan_docs(docs, allowlist, REPO_ROOT)

    if args.json:
        print(
            json.dumps(
                {
                    "checked_docs": len(docs),
                    "findings": [f.to_dict() for f in findings],
                    "allowlisted": len(allowlist),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(_report_text(findings, allowlist))

    return 0 if (args.warn_only or not findings) else 1


if __name__ == "__main__":
    sys.exit(main())
