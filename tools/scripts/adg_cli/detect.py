"""Language and framework detection for ADG CLI."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.scripts._common import EXTENSION_MAP
from tools.scripts.adg_cli._paths import (
    MAX_FILES,
    is_skipped_dir,
)

CONFIG_MARKERS: dict[str, str | None] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "package.json": None,  # could be JS or TS
    "tsconfig.json": "typescript",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "Gemfile": "ruby",
    "composer.json": "php",
    "CMakeLists.txt": "cpp",
    "build.sbt": "scala",
}

FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    # JavaScript/TypeScript frameworks (order matters for detection)
    "nextjs": ["next", "nextjs"],
    "react": ["react", "react-dom"],
    "vue": ["vue", "nuxt"],
    "angular": ["@angular/core"],
    "express": ["express"],
    "nestjs": ["@nestjs/core"],
    # Python frameworks
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    # Go frameworks
    "gin": ["github.com/gin-gonic/gin"],
    # Rust frameworks
    "actix": ["actix-web"],
    "axum": ["axum"],
    # Java frameworks
    "spring-boot": ["spring-boot"],
    "spring": ["spring"],
}


def detect_language(dirpath: Path) -> dict[str, Any]:
    """Detect primary language and framework (V2.21 P5-24 拆分: 抽 _check_config_markers + _count_extension_languages)."""
    result: dict[str, Any] = {
        "language": "unknown",
        "framework": None,
        "confidence": 0.0,
    }

    # 1. Check config files
    config_result = _check_config_markers(dirpath)
    if config_result is not None:
        return config_result

    # 2. Count file extensions
    counter = _count_extension_languages(dirpath)
    if not counter:
        return result

    total = sum(counter.values())
    primary, primary_count = counter.most_common(1)[0]
    result["language"] = primary
    result["confidence"] = round(primary_count / total, 2)
    result["framework"] = _detect_framework(dirpath, primary)
    return result


def _check_config_markers(dirpath: Path) -> dict[str, Any] | None:
    """检查 CONFIG_MARKERS 配置文件 (package.json 特殊处理 ts/js 区分, 模块级 helper).

    Args:
        dirpath: 扫描根目录

    Returns:
        result 字典, 无配置命中返回 None
    """
    for config_file, lang in CONFIG_MARKERS.items():
        if not (dirpath / config_file).exists():
            continue
        if config_file == "package.json":
            lang = "typescript" if (dirpath / "tsconfig.json").exists() else "javascript"
        return {
            "language": lang or "unknown",
            "framework": _detect_framework(dirpath, lang),
            "confidence": 0.9,
        }
    return None


def _count_extension_languages(dirpath: Path) -> Counter[str]:
    """按文件扩展名统计语言 (跳过 SKIP_DIRS, 模块级 helper).

    Args:
        dirpath: 扫描根目录

    Returns:
        Counter[language] = count
    """
    counter: Counter[str] = Counter()
    count = 0
    for filepath in dirpath.rglob("*"):
        if count >= MAX_FILES:
            break
        if not filepath.is_file():
            continue
        try:
            rel_parts = filepath.relative_to(dirpath).parts[:-1]
        except ValueError:
            rel_parts = ()
        if any(is_skipped_dir(part) for part in rel_parts):
            continue
        suffix = filepath.suffix.lower()
        if suffix in EXTENSION_MAP:
            counter[EXTENSION_MAP[suffix]] += 1
            count += 1
    return counter


def _detect_framework_from_package_json(dirpath: Path) -> str | None:
    """Detect framework from package.json."""
    pkg_path = dirpath / "package.json"
    if not pkg_path.exists():
        return None
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        all_deps: dict[str, str] = {}
        for key in ("dependencies", "devDependencies"):
            if key in pkg and isinstance(pkg[key], dict):
                all_deps.update(pkg[key])
        for framework, signatures in FRAMEWORK_SIGNATURES.items():
            if any(sig in all_deps for sig in signatures):
                return framework
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _detect_framework_from_python_reqs(dirpath: Path) -> str | None:
    """Detect framework from Python requirements files."""
    for req_file in ("requirements.txt", "pyproject.toml"):
        req_path = dirpath / req_file
        if not req_path.exists():
            continue
        try:
            content = req_path.read_text(encoding="utf-8").lower()
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig.lower() in content for sig in signatures):
                    return framework
        except OSError:
            pass
    return None


def _detect_framework_from_django(dirpath: Path) -> str | None:
    """Detect Django framework."""
    # Check for manage.py
    manage_py = dirpath / "manage.py"
    if manage_py.exists():
        try:
            content = manage_py.read_text(encoding="utf-8")
            if "django" in content.lower():
                return "django"
        except OSError:
            pass

    # Check for settings.py in common locations
    for settings_path in ["settings.py", "config/settings.py", "myproject/settings.py"]:
        if (dirpath / settings_path).exists():
            return "django"
    return None


def _detect_framework_from_go_mod(dirpath: Path) -> str | None:
    """Detect framework from go.mod."""
    go_mod = dirpath / "go.mod"
    if not go_mod.exists():
        return None
    try:
        content = go_mod.read_text(encoding="utf-8")
        for framework, signatures in FRAMEWORK_SIGNATURES.items():
            if any(sig in content for sig in signatures):
                return framework
    except OSError:
        pass
    return None


def _detect_framework_from_java_build(dirpath: Path) -> str | None:
    """Detect framework from Java build files."""
    for build_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
        build_path = dirpath / build_file
        if not build_path.exists():
            continue
        try:
            content = build_path.read_text(encoding="utf-8")
            if "spring" in content.lower():
                return "spring"
        except OSError:
            pass
    return None


def _detect_framework_from_cargo_toml(dirpath: Path) -> str | None:
    """Detect framework from Cargo.toml."""
    cargo_toml = dirpath / "Cargo.toml"
    if not cargo_toml.exists():
        return None
    try:
        content = cargo_toml.read_text(encoding="utf-8").lower()
        for framework, signatures in FRAMEWORK_SIGNATURES.items():
            if any(sig.lower() in content for sig in signatures):
                return framework
    except OSError:
        pass
    return None


def _detect_framework(dirpath: Path, language: str | None) -> str | None:
    """Detect framework from project config files."""
    # Check package.json (Node.js/TypeScript)
    result = _detect_framework_from_package_json(dirpath)
    if result:
        return result

    # Check Python requirements
    result = _detect_framework_from_python_reqs(dirpath)
    if result:
        return result

    # Check Django
    result = _detect_framework_from_django(dirpath)
    if result:
        return result

    # Check go.mod
    result = _detect_framework_from_go_mod(dirpath)
    if result:
        return result

    # Check Java build files
    result = _detect_framework_from_java_build(dirpath)
    if result:
        return result

    # Check Rust Cargo.toml
    result = _detect_framework_from_cargo_toml(dirpath)
    if result:
        return result

    return None


def _detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from a single file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file. Tries PyYAML first, falls back to simple parser."""
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        return _simple_yaml_parse(path)
    except Exception:
        return {}


# 规则型 section: 这两类 key 下的 `- key: value` 列表项是一条条规则
_RULE_SECTIONS = ("anti_patterns", "custom_rules")


def _simple_yaml_parse(path: Path) -> dict[str, Any]:
    """Minimal YAML parser for anti_patterns.yml and config files (no PyYAML needed).

    支持 `.adg/rules.yml` 的 canonical key `custom_rules` (legacy 别名
    `anti_patterns` 同样保留), 与 PyYAML 解析结果结构对齐。
    """
    content = path.read_text(encoding="utf-8")
    result: dict[str, Any] = {"anti_patterns": []}
    current_rule: dict[str, Any] | None = None
    current_section: str | None = None

    for line in content.splitlines():
        current_rule, current_section = _process_line(line, result, current_rule, current_section)

    # Append last rule if any (按所属 section 收尾, 防止串到 anti_patterns)
    if current_rule is not None:
        if current_section in _RULE_SECTIONS:
            result[current_section].append(current_rule)
        current_rule = None

    return result


def _finalize_rule(
    result: dict[str, Any],
    current_rule: dict[str, Any] | None,
    current_section: str | None,
) -> None:
    """把待收尾的规则落盘到所属 section (中文: 跨 section 前必须调用)."""
    if current_rule is None:
        return
    if current_section in _RULE_SECTIONS:
        result[current_section].append(current_rule)


def _process_line(
    line: str,
    result: dict[str, Any],
    current_rule: dict[str, Any] | None,
    current_section: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Process a single line in YAML content."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return current_rule, current_section

    # 列表项 (check BEFORE top-level keys): "- key: value" 在规则 section 内
    # 开启一条新规则 —— 首字段不限于 id (`.adg/rules.yml` 以 `- category:` 开头)
    if stripped.startswith("- "):
        item_body = stripped[2:].strip()
        if current_section in _RULE_SECTIONS:
            if ":" in item_body:
                if current_rule is not None:
                    result[current_section].append(current_rule)
                current_rule = {}
                _apply_rule_field(current_rule, item_body)
            # 裸标量列表项 (无 key: value) 无法构成规则, 忽略
            return current_rule, current_section
        if current_section == "installed_packs":
            # installed_packs 是标量列表 (如 `- security-essentials`),
            # 必须在规则 section 之外, 否则会被误捕获为规则字段
            if item_body:
                result.setdefault("installed_packs", []).append(item_body.strip("'\""))
            return current_rule, current_section
        if current_section == "skip_patterns":
            _handle_skip_patterns_line(result, stripped)
        # 其他/未知 section 下的列表项: 不跨 section 捕获, 直接忽略
        return current_rule, current_section

    # Top-level keys (only lines NOT starting with space and NOT starting with -)
    if not line.startswith(" ") and not line.startswith("-") and ":" in stripped:
        # 任何顶层 key (含未知 key, 例如 installed_packs:) 都先收尾当前规则并
        # 重置 section, 防止后续列表项被误并入上一个 section
        if current_rule is not None:
            _finalize_rule(result, current_rule, current_section)
            current_rule = None
        current_rule, current_section = _process_top_level_key(line, stripped, result, current_rule, current_section)
        return current_rule, current_section

    # Handle section-specific content
    current_rule = _process_section_content(line, stripped, result, current_rule, current_section)
    return current_rule, current_section


def _process_top_level_key(
    line: str,
    stripped: str,
    result: dict[str, Any],
    current_rule: dict[str, Any] | None,
    current_section: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Process top-level key:value pairs."""
    key, _, val = stripped.partition(":")
    key = key.strip()
    val = val.strip().strip("'\"")

    # 默认重置 section: 未知顶层 key 之后的 `- item` 行不属于上一个 section
    current_section = None

    if key == "language":
        result["language"] = val
    elif key == "version":
        result["version"] = val
    elif key == "skip_patterns":
        current_section = "skip_patterns"
        result["skip_patterns"] = []
    elif key == "severity_overrides":
        current_section = "severity_overrides"
        result["severity_overrides"] = {}
    elif key == "framework_hints":
        current_section = "framework_hints"
        result["framework_hints"] = {}
    elif key in _RULE_SECTIONS:
        # custom_rules 为 canonical key, anti_patterns 为 legacy 别名
        current_section = key
        result.setdefault(key, [])
    elif key == "installed_packs":
        current_section = "installed_packs"
        result.setdefault(key, [])
    return current_rule, current_section


def _handle_skip_patterns_line(
    result: dict[str, Any],
    stripped: str,
) -> None:
    """处理 skip_patterns section 的列表项.

    V2.17 P2-4 拆分: 从 _process_section_content (D=21) 抽出.
    """
    if not stripped.startswith("- "):
        return
    pattern = stripped[2:].strip().strip("'\"")
    if pattern:
        result["skip_patterns"].append(pattern)


def _handle_kv_section_line(
    section_data: dict[str, str],
    stripped: str,
) -> None:
    """处理 severity_overrides / framework_hints section 的 key: value 行.

    V2.17 P2-4 拆分: 从 _process_section_content (D=21) 抽出.
    跳过 list 项 (以 - 开头), 只处理 k: v.
    """
    if ":" not in stripped or stripped.startswith("-"):
        return
    key, _, val = stripped.partition(":")
    key = key.strip()
    val = val.strip().strip("'\"")
    if key and val:
        section_data[key] = val


def _apply_rule_field(
    current_rule: dict[str, Any],
    stripped: str,
) -> None:
    """处理 rule 字段 (name/severity/.../ignore_case/multiline).

    V2.17 P2-4 拆分: 从 _process_section_content (D=21) 抽出.
    """
    if ":" not in stripped:
        return
    key, _, val = stripped.partition(":")
    key = key.strip()
    val = val.strip().strip("'\"")
    if key in (
        "id",
        "name",
        "language",
        "severity",
        "category",
        "pattern",
        "message",
        "fix_hint",
        "fix_replacement",
    ):
        current_rule[key] = val
    elif key == "ignore_case" and val == "true":
        current_rule["ignore_case"] = True
    elif key == "multiline" and val == "true":
        current_rule["multiline"] = True


def _process_section_content(
    line: str,
    stripped: str,
    result: dict[str, Any],
    current_rule: dict[str, Any] | None,
    current_section: str | None,
) -> dict[str, Any] | None:
    """Process content within a section (orchestrator).

    V2.17 P2-4 拆分: 从 D=21 / 53 行主函数拆出 3 个 section handler.
    主函数仅负责按 current_section 分发:
    - skip_patterns → _handle_skip_patterns_line
    - severity_overrides / framework_hints → _handle_kv_section_line
    - rule 字段 → _apply_rule_field
    """
    if current_section == "skip_patterns":
        _handle_skip_patterns_line(result, stripped)
    elif current_section in ("severity_overrides", "framework_hints"):
        _handle_kv_section_line(result[current_section], stripped)
    elif current_rule is not None:
        _apply_rule_field(current_rule, stripped)

    return current_rule
