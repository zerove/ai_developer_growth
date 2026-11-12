#!/usr/bin/env python3
"""MkDocs 增量构建（安全子集）：按内容指纹判断文档是否需要重建。

## 为什么

`mkdocs build --strict` 每次都会把全部 391 篇文档重新渲染一遍（> 30s）。
本项目反复出现的诉求是"只重建改动过的部分"。

## 为什么不直接做页面级增量

MkDocs **没有**提供"跳过未变更页面"的官方钩子：

- `on_page_markdown` 只能改写 markdown，改写后仍要经过 markdown 扩展转换
  （本项目启用了 pymdownx 等扩展），省不下主要成本；
- `on_post_page` 注入缓存 HTML 会让 **material search 插件**在
  `on_page_content` 阶段索引到空内容 → 站内搜索失效；
- `mkdocstrings` 需要真实导入 Python 模块取 docstring，页面级缓存与
  "源码变了要重新生成 API 文档"天然冲突。

因此本实现只做**可验证的安全子集**：用**内容指纹清单**（docs + mkdocs.yml +
templates + mkdocstrings 引用的源码模块）判断"文档输入是否变化"：

- 输入未变且 `site/` 已存在 → **跳过构建**（退出码 0，明确输出"已是最新"）；
- 输入有变或 `site/` 缺失 → 调 `mkdocs build --strict` 全量重建（正确性优先）。

清单落盘在 `.cache/mkdocs-incremental.json`（`.cache/` 已在 `.gitignore` 中），
指纹用 **内容 sha256**（不用 mtime —— mtime 在 checkout/clone 后不可靠）。

## 用法

    python tools/scripts/mkdocs_incremental.py            # 构建（未变则跳过）
    python tools/scripts/mkdocs_incremental.py --force    # 强制重建
    python tools/scripts/mkdocs_incremental.py --check    # 只判断是否需要重建
    python tools/scripts/mkdocs_incremental.py --json     # 机器可读输出

退出码: 0 构建成功/无需构建（`--check` 且无需重建）/ 1 构建失败或（`--check` 且）需要重建。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:  # python -m tools.scripts.mkdocs_incremental (根已在 path)
    from tools.scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # python tools/scripts/mkdocs_incremental.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: 构建输入的匹配模式（相对仓库根）。
INPUT_PATTERNS = (
    "docs/**/*.md",
    "mkdocs.yml",
    "templates/**/*",
)

#: 清单文件路径（相对仓库根）。
MANIFEST_PATH = Path(".cache/mkdocs-incremental.json")

#: 默认构建命令。
DEFAULT_BUILD_COMMAND = ("mkdocs", "build", "--strict")


def _hash_file(path: Path) -> str:
    """文件内容 sha256（内容指纹，不用 mtime）。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdocstrings_modules(root: Path) -> list[str]:
    """解析文档里的 `::: module.path` 指令，返回被引用的模块名。"""
    modules: set[str] = set()
    for doc in sorted((root / "docs").rglob("*.md")):
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith(":::"):
                continue
            target = stripped[3:].strip().split()
            if target and target[0]:
                modules.add(target[0])
    return sorted(modules)


def _module_source_paths(root: Path, modules: list[str]) -> list[Path]:
    """模块名 → 可能的源码文件（包目录取 `__init__.py`）。"""
    paths: list[Path] = []
    for module in modules:
        relative = module.replace(".", "/")
        for candidate in (root / f"{relative}.py", root / relative / "__init__.py"):
            if candidate.is_file():
                paths.append(candidate)
                break
    return paths


def compute_manifest(root: Path = REPO_ROOT) -> dict[str, str]:
    """计算构建输入的内容指纹清单: {相对路径: sha256}。

    覆盖：全部文档、mkdocs.yml、templates/、以及 mkdocstrings 指令引用的源码模块
    （源码变了 API 文档必须重建，不能只看 .md）。
    """
    manifest: dict[str, str] = {}

    for pattern in INPUT_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            manifest[str(path.relative_to(root))] = _hash_file(path)

    for module in _mkdocstrings_modules(root):
        for path in _module_source_paths(root, [module]):
            manifest[str(path.relative_to(root))] = _hash_file(path)

    return manifest


def load_manifest(path: Path) -> dict[str, str]:
    """读取已存清单；缺失或损坏时返回空字典（按"需要重建"处理）。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return {}
    return {str(k): str(v) for k, v in files.items()}


def save_manifest(path: Path, manifest: dict[str, str]) -> None:
    """写入清单（原子替换，避免中断写坏文件）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "files": manifest}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def needs_rebuild(root: Path = REPO_ROOT, manifest_path: Path | None = None) -> tuple[bool, dict[str, str]]:
    """判断是否需要重建: (是否需要重建, 当前清单)。"""
    manifest = compute_manifest(root)
    stored = load_manifest(manifest_path or (root / MANIFEST_PATH))
    return stored != manifest, manifest


def site_exists(root: Path = REPO_ROOT) -> bool:
    """已构建产物是否存在（决定能否跳过）。"""
    return (root / "site" / "index.html").is_file()


def run_build(command: list[str], cwd: Path = REPO_ROOT) -> int:
    """执行构建命令，返回退出码。"""
    result = subprocess.run(command, cwd=cwd, check=False)  # noqa: S603 - 命令来自参数
    return result.returncode


def _report(payload: dict[str, Any], message: str, as_json: bool) -> None:
    """统一输出（JSON 或文本）。"""
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(message)


def _run_check_mode(root: Path, manifest: dict[str, str], changed: bool, as_json: bool) -> int:
    """`--check`：只判断是否需要重建。"""
    payload: dict[str, Any] = {
        "needs_rebuild": changed,
        "tracked_files": len(manifest),
        "site_exists": site_exists(root),
    }
    state = "需要重建" if changed else "无需重建"
    _report(payload, f"MkDocs 增量检查: {state}（跟踪 {len(manifest)} 个输入文件）", as_json)
    return 1 if changed else 0


def _run_build_mode(
    root: Path,
    manifest_path: Path,
    manifest: dict[str, str],
    changed: bool,
    command: list[str],
    force: bool,
    as_json: bool,
) -> int:
    """构建模式：未变且产物在 → 跳过；否则全量构建并（成功时）更新清单。"""
    if not force and not changed and site_exists(root):
        payload = {"skipped": True, "reason": "up_to_date", "tracked_files": len(manifest)}
        _report(
            payload,
            "MkDocs 增量构建: 输入未变化且 site/ 已存在 → 跳过构建（--force 可强制重建）",
            as_json,
        )
        return 0

    started = time.monotonic()
    code = run_build(command, root)
    duration = time.monotonic() - started

    if code == 0:
        save_manifest(manifest_path, manifest)

    payload = {
        "skipped": False,
        "exit_code": code,
        "duration_seconds": round(duration, 2),
        "tracked_files": len(manifest),
    }
    state = "构建成功" if code == 0 else "构建失败"
    _report(
        payload,
        f"MkDocs 增量构建: {state}（{duration:.1f}s，跟踪 {len(manifest)} 个输入文件）",
        as_json,
    )
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MkDocs 增量构建（内容指纹判断是否需要重建）")
    parser.add_argument("--force", action="store_true", help="忽略指纹，强制重建")
    parser.add_argument("--check", action="store_true", help="只判断是否需要重建，不执行构建")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument(
        "--build-command",
        default=" ".join(DEFAULT_BUILD_COMMAND),
        help="构建命令（空格分隔，默认: 'mkdocs build --strict'）",
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="仓库根目录（默认自动推断）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = root / MANIFEST_PATH
    changed, manifest = needs_rebuild(root, manifest_path)

    if args.check:
        return _run_check_mode(root, manifest, changed, args.json)

    return _run_build_mode(
        root,
        manifest_path,
        manifest,
        changed,
        args.build_command.split(),
        args.force,
        args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
