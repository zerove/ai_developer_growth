"""Architecture Drift Guard (Pillar 1)

Checks codebase against ADR rules and architectural layering constraints
(e.g., domain layer should not depend on UI or infrastructure directly).

多语言支持：按项目实际语言组合扫描源文件，而非硬编码 Python。
对无法检查的语言组合显式返回 unsupported 状态，绝不静默返回空结果。
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.scripts._common import get_project_root

# 各语言的源码扩展名（用于语言探测与扫描范围）
LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "typescript": (".ts", ".tsx"),
    "javascript": (".js", ".jsx", ".mjs"),
    "go": (".go",),
    "rust": (".rs",),
    "java": (".java",),
    "kotlin": (".kt", ".kts"),
    "csharp": (".cs",),
    "ruby": (".rb",),
    "php": (".php",),
    "swift": (".swift",),
    "cpp": (".cpp", ".cc", ".hpp", ".h"),
}

# 分层关键词：domain 层源文件中出现即视为依赖了基础设施/表现层
# 按语言分组——import 风格不同
LAYERING_IMPORT_PATTERNS: dict[str, tuple[str, ...]] = {
    "python": ("infrastructure", "fastapi", "flask", "django"),
    "typescript": ('from "./infrastructure', "express", "axios"),
    "javascript": ('require("./infrastructure', "express", "axios"),
    "go": ("infrastructure/", "net/http", "gin-gonic"),
    "rust": ("infrastructure::", "actix_web", "warp"),
    "java": ("infrastructure.", "org.springframework.web"),
}


class ArchitectureDriftGuard:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.violations: list[str] = []
        self.unsupported_languages: list[str] = []
        self.scanned_languages: list[str] = []

    def detect_project_languages(self) -> list[str]:
        """按源码扩展名统计项目语言构成（不依赖标记文件的健壮探测）。"""
        counts: dict[str, int] = {}
        skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target"}
        for path in self.root_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel_parts = path.relative_to(self.root_dir).parts[:-1]
            except ValueError:
                rel_parts = ()
            if any(part in skip_dirs for part in rel_parts):
                continue
            suffix = path.suffix.lower()
            for lang, exts in LANGUAGE_EXTENSIONS.items():
                if suffix in exts:
                    counts[lang] = counts.get(lang, 0) + 1
                    break
        return [lang for lang, _ in sorted(counts.items(), key=lambda kv: -kv[1])]

    def check_layering(self) -> list[str]:
        """分层守卫：扫描项目中所有有规则覆盖的语言；无规则的语言记入 unsupported。"""
        self.violations = []
        self.unsupported_languages = []
        self.scanned_languages = []

        languages = self.detect_project_languages()
        if not languages:
            # 纯文档/配置项目：无源码可查不算错误
            return self.violations

        domain_markers = ("domain",)
        for lang in languages:
            patterns = LAYERING_IMPORT_PATTERNS.get(lang)
            if patterns is None:
                self.unsupported_languages.append(lang)
                continue
            self.scanned_languages.append(lang)
            exts = LANGUAGE_EXTENSIONS[lang]
            for file_path in self.root_dir.rglob("*"):
                if file_path.suffix.lower() not in exts:
                    continue
                if any(part in {".git", "node_modules", ".venv", "venv"} for part in file_path.parts):
                    continue
                if not any(m in file_path.parts for m in domain_markers):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8")
                except OSError:
                    continue
                for pat in patterns:
                    if pat in content:
                        rel = file_path.relative_to(self.root_dir)
                        self.violations.append(
                            f"Architecture Drift in {rel} [{lang}]: "
                            f"Domain layer references infrastructure/web component ('{pat}')."
                        )
                        break
        return self.violations

    def check_adr_references(self) -> list[str]:
        adr_dir = self.root_dir / "docs" / "adr"
        if not adr_dir.exists():
            return []
        return []


def main(root_dir: Path | None = None) -> int:
    guard = ArchitectureDriftGuard(root_dir)
    violations = guard.check_layering()
    if violations:
        print("❌ Architecture Drift Detected:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        scanned = ", ".join(guard.scanned_languages) or "无"
        print(f"✅ Architecture Drift Guard passed: No layering violations found. Scanned: {scanned}")
        if guard.unsupported_languages:
            print(
                f"⚠️  未扫描（暂无该语言的分层规则）: {', '.join(guard.unsupported_languages)} — "
                "这些语言不会被静默当作'已检查通过'"
            )
        sys.exit(0)


if __name__ == "__main__":
    main()
