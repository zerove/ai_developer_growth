"""Rule catalog: pack definitions, search, install, validate, and export.

Core business logic extracted from rule_marketplace.py for reuse
by other tools (hooks_runner, quality-gate, etc.).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterator

import yaml

from tools.scripts._common import framework_dir

# ──────────────────────────────────────────────────────────
# Built-in pack definitions
# ──────────────────────────────────────────────────────────

BUILTIN_PACKS: dict[str, dict[str, Any]] = {
    "security": {
        "name": "Security Rules",
        "description": "Cross-language security anti-patterns",
        "source": "common/security.yml",
        "categories": ["security"],
        "rule_count": 8,
    },
    "python-pack": {
        "name": "Python Best Practices",
        "description": "Python anti-patterns, naming conventions, and complexity rules",
        "source": "languages/python/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 21,
    },
    "typescript-pack": {
        "name": "TypeScript Best Practices",
        "description": "TypeScript anti-patterns, naming conventions, and complexity rules",
        "source": "languages/typescript/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 17,
    },
    "react-pack": {
        "name": "React Anti-patterns",
        "description": "Common React anti-patterns and best practices",
        "source": "frameworks/react/rules.d/",
        "categories": ["anti_patterns"],
        "rule_count": 8,
    },
    "vue-pack": {
        "name": "Vue Anti-patterns",
        "description": "Common Vue anti-patterns and best practices",
        "source": "frameworks/vue/rules.d/",
        "categories": ["anti_patterns"],
        "rule_count": 8,
    },
    "django-pack": {
        "name": "Django Best Practices",
        "description": "Django security, naming, and anti-patterns",
        "source": "frameworks/django/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 22,
    },
    "fastapi-pack": {
        "name": "FastAPI Best Practices",
        "description": "FastAPI anti-patterns, naming, and complexity",
        "source": "frameworks/fastapi/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 18,
    },
    "spring-pack": {
        "name": "Spring Boot Best Practices",
        "description": "Spring Boot anti-patterns and naming conventions",
        "source": "frameworks/spring/rules.d/",
        "categories": ["anti_patterns", "naming_conventions"],
        "rule_count": 16,
    },
    "full": {
        "name": "All Rules",
        "description": "All rules for all languages and frameworks",
        "source": "./",
        "categories": ["anti_patterns", "naming_conventions", "complexity", "security"],
        "rule_count": 350,
    },
}


# ──────────────────────────────────────────────────────────
# Search / matching
# ──────────────────────────────────────────────────────────

_CATEGORIES = ["anti_patterns", "naming_conventions", "complexity"]


def matches(rule: dict[str, Any], query: str) -> bool:
    """Check if a rule matches a search query."""
    fields = [
        rule.get("id", ""),
        rule.get("message", ""),
        rule.get("pattern", ""),
        rule.get("fix_hint", ""),
        rule.get("category", ""),
        " ".join(rule.get("tags", [])),
    ]
    text = " ".join(fields).lower()
    return query in text


def _search_common_rules(query: str) -> list[dict[str, Any]]:
    """Search common rules (security)."""
    results: list[dict[str, Any]] = []
    fw = framework_dir()
    common_file = fw / "common" / "security.yml"
    if common_file.exists():
        with open(common_file) as f:
            data = yaml.safe_load(f) or {}
        for rule in data.get("anti_patterns", []):
            if matches(rule, query):
                results.append({"pack": "security", **rule})
    return results


def _search_language_rules(query: str) -> list[dict[str, Any]]:
    """Search language-specific rules.

    V2.20 P4-25 拆分: 复用 _iter_pack_rules 统一遍历 languages 子目录.
    """
    return _iter_pack_rules("languages", query)


def _search_framework_rules(query: str) -> list[dict[str, Any]]:
    """Search framework-specific rules.

    V2.20 P4-25 拆分: 复用 _iter_pack_rules 统一遍历 frameworks 子目录.
    """
    return _iter_pack_rules("frameworks", query)


def _iter_pack_rules(parent_subdir: str, query: str) -> list[dict[str, Any]]:
    """遍历指定子目录下所有 pack 的 yml rules, 匹配 query (V2.22 P6-2 拆分: 抽 _iter_pack_dirs + _collect_pack_rules).

    Args:
        parent_subdir: 父目录名 ('languages' / 'frameworks')
        query: 搜索关键字 (lowercase substring)

    Returns:
        [{pack, category, **rule}, ...]
    """
    results: list[dict[str, Any]] = []
    for pack_dir in _iter_pack_dirs(parent_subdir):
        results.extend(_collect_pack_rules(pack_dir, query))
    return results


def _iter_pack_dirs(parent_subdir: str) -> Iterator[Path]:
    """遍历有效 pack 目录 (有 rules.d 子目录, 模块级 generator).

    Args:
        parent_subdir: 父目录名 ('languages' / 'frameworks')

    Yields:
        pack_dir 路径
    """
    fw = framework_dir()
    parent_dir = fw / parent_subdir
    if not parent_dir.exists():
        return
    for pack_dir in sorted(parent_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        rules_dir = pack_dir / "rules.d"
        if not rules_dir.exists():
            continue
        yield pack_dir


def _collect_pack_rules(pack_dir: Path, query: str) -> list[dict[str, Any]]:
    """单 pack 目录内所有 yml rules 收集 (模块级 helper).

    Args:
        pack_dir: pack 目录路径
        query: 搜索关键字

    Returns:
        [{pack, category, **rule}, ...] 列表
    """
    results: list[dict[str, Any]] = []
    rules_dir = pack_dir / "rules.d"
    for yml in rules_dir.glob("*.yml"):
        data = _load_yaml_rules(yml)
        for category in _CATEGORIES:
            for rule in data.get(category, []):
                if matches(rule, query):
                    results.append({"pack": pack_dir.name, "category": category, **rule})
    return results


def _load_yaml_rules(yml: Path) -> dict[str, Any]:
    """加载 yaml 规则文件, 失败返空 dict.

    Args:
        yml: yaml 路径

    Returns:
        解析后的 dict (or {})
    """
    try:
        with open(yml) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def search_rules(query: str) -> list[dict[str, Any]]:
    """Search all rule sources for rules matching a query.

    Returns list of dicts with pack, category, and rule data.
    """
    results: list[dict[str, Any]] = []
    results.extend(_search_common_rules(query))
    results.extend(_search_language_rules(query))
    results.extend(_search_framework_rules(query))
    return results


# ──────────────────────────────────────────────────────────
# Pack operations
# ──────────────────────────────────────────────────────────


def get_pack_info(pack_id: str) -> dict[str, Any] | None:
    """Get info about a pack. Returns None if not found."""
    return BUILTIN_PACKS.get(pack_id)


def get_pack_source(pack_id: str) -> Path | None:
    """Get the resolved source path for a pack."""
    info = BUILTIN_PACKS.get(pack_id)
    if not info:
        return None
    path: Path = framework_dir() / info["source"]
    return path


def install_pack(pack_id: str, project_dir: Path, dry_run: bool = False) -> list[Path]:
    """Install a rule pack to .ai-rules/. Returns list of installed file paths.

    V2.20 P4-26 拆分: 抽 _install_pack_file / _install_pack_dir 收口 file/dir 模式,
    主函数仅守卫 + 委托.
    """
    info = BUILTIN_PACKS.get(pack_id)
    if not info:
        raise ValueError(f"Unknown pack: {pack_id}")

    if dry_run:
        return []

    target_dir = project_dir / ".ai-rules"
    target_dir.mkdir(parents=True, exist_ok=True)
    src = framework_dir() / info["source"]

    if src.is_file():
        return _install_pack_file(src, target_dir)
    if src.is_dir():
        return _install_pack_dir(src, target_dir, pack_id)
    return []


def _install_pack_file(src: Path, target_dir: Path) -> list[Path]:
    """安装单文件 pack 到 target_dir.

    Args:
        src: 源文件
        target_dir: 目标目录

    Returns:
        [dest_path]
    """
    dest = target_dir / src.name
    shutil.copy2(src, dest)
    return [dest]


def _install_pack_dir(src: Path, target_dir: Path, pack_id: str) -> list[Path]:
    """安装目录 pack 所有 .yml 到 target_dir (重命名加 pack_id 前缀).

    Args:
        src: 源目录
        target_dir: 目标目录
        pack_id: pack ID (用作文件名前缀)

    Returns:
        安装的 dest path 列表
    """
    installed: list[Path] = []
    for yml in src.glob("*.yml"):
        dest = target_dir / f"{pack_id}-{yml.name}"
        shutil.copy2(yml, dest)
        installed.append(dest)
    return installed


def _validate_single_rule(
    yml_name: str,
    rule: dict[str, Any],
    category: str,
) -> tuple[int, list[str]]:
    """校验单条 rule 的必填字段.

    V2.18 P3-6 拆分: 从 validate_rules (C=11) 抽出.
    返回 (rule_count, error_messages) - 即使校验失败, rule_count 仍 +1
    (因为该 rule 存在, 只是字段不全).
    """
    errors: list[str] = []
    if not rule.get("id"):
        errors.append(f"{yml_name}: rule missing 'id'")
    if not rule.get("pattern") and category in ["anti_patterns", "complexity"]:
        errors.append(f"{yml_name}/{rule.get('id', '?')}: missing 'pattern'")
    if not rule.get("message"):
        errors.append(f"{yml_name}/{rule.get('id', '?')}: missing 'message'")
    return 1, errors


def _validate_yaml_file(yml: Path) -> tuple[int, int, list[str]]:
    """校验单个 YAML 文件的所有 rules.

    V2.18 P3-6 拆分: 从 validate_rules (C=11) 抽出.
    返回 (total_rules, error_count, messages).
    """
    try:
        with open(yml) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return 0, 1, [f"{yml.name}: YAML parse error: {e}"]

    if not data:
        return 0, 1, [f"{yml.name}: empty or invalid YAML"]

    total_rules = 0
    errors = 0
    messages: list[str] = []
    for category in _CATEGORIES:
        for rule in data.get(category, []):
            count, rule_errors = _validate_single_rule(yml.name, rule, category)
            total_rules += count
            errors += len(rule_errors)
            messages.extend(rule_errors)

    return total_rules, errors, messages


def validate_rules(rules_dir: Path) -> tuple[int, int, list[str]]:
    """Validate all YAML rules in a directory (orchestrator).

    V2.18 P3-6 拆分: 从 C=11 / 53 行主函数拆出 2 个 helper.
    主函数仅负责: 目录检查 → 遍历 → 汇总.

    Returns (total_rules, error_count, error_messages).
    """
    if not rules_dir.exists():
        return 0, 0, [f"Directory not found: {rules_dir}"]

    total_rules = 0
    errors = 0
    messages: list[str] = []

    for yml in sorted(rules_dir.glob("*.yml")):
        t, e, m = _validate_yaml_file(yml)
        total_rules += t
        errors += e
        messages.extend(m)

    return total_rules, errors, messages


def export_rules(rules_dir: Path, output: Path) -> tuple[int, dict[str, Any]]:
    """Export rules from .ai-rules/ to a single YAML file.

    Returns (rule_count, combined_dict).
    """
    combined: dict[str, Any] = {
        "anti_patterns": [],
        "naming_conventions": [],
        "complexity": [],
    }

    for yml in sorted(rules_dir.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f) or {}
        for category in combined:
            combined[category].extend(data.get(category, []))

    total = sum(len(v) for v in combined.values())
    return total, combined
