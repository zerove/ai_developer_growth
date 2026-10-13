"""Rule loading, caching, and merging for language rules."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from tools.scripts._common import (
    file_hash_full as _file_hash,  # noqa: F401 - re-export for tests
)
from tools.scripts._common import (
    load_cache as _load_cache,  # noqa: F401 - re-export for tests
)
from tools.scripts._common import (
    merge_anti_patterns as _merge_anti_patterns,
)
from tools.scripts._common import (
    rules_dir,
)
from tools.scripts._common import (
    save_cache as _save_cache,  # noqa: F401 - re-export for tests
)
from tools.scripts.rules_engine.logger import logger

# ── 生成规则自动发现 ───────────────────────────────────────

_GENERATED_RULES_CACHE: dict[str, list[dict[str, Any]]] = {}


def _load_generated_rules(language: str) -> list[dict[str, Any]]:
    """从缓存目录加载 agent 生成的规则。

    生成规则存储在 ~/.config/adg/rules/generated/<language>/rules.d/anti_patterns.yml
    由 /generate-rules skill 创建。

    Returns:
        规则列表（空列表表示无生成规则）
    """
    if language in _GENERATED_RULES_CACHE:
        return _GENERATED_RULES_CACHE[language]

    try:
        from tools.scripts.rules_engine.rule_generator import load_generated_rules

        rules = load_generated_rules(language)
        _GENERATED_RULES_CACHE[language] = rules
        if rules:
            logger.info(f"Loaded {len(rules)} generated rules for '{language}'.")
        return rules
    except ImportError:
        return []
    except (AttributeError, OSError):
        return []


# ──────────────────────────────────────────────────────────
# Rule cache
# ──────────────────────────────────────────────────────────

_RULE_CACHE: dict[str, dict[str, Any]] = {}
_FILE_HASH_CACHE: dict[str, str] = {}


# Disk cache path
# ADR-075: 支持用环境变量改写缓存位置。目的不是“方便配置”, 而是让
# **子进程**也能把缓存写到临时目录 —— 测试里大量用
# ``subprocess.run([sys.executable, hooks_runner.py, ...])`` 跑真实 CLI,
# in-process 的 monkeypatch 跨不过进程边界, 子进程会照样写真实缓存。
# 环境变量会被子进程继承, 是唯一能覆盖全链路的手段。
_CACHE_DIR_ENV = "ADG_RULES_CACHE_DIR"
_DEFAULT_DISK_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "rules_engine"
_DISK_CACHE_DIR = Path(os.environ.get(_CACHE_DIR_ENV) or _DEFAULT_DISK_CACHE_DIR)
_DISK_CACHE_FILE = _DISK_CACHE_DIR / "rules_cache.json"


@contextlib.contextmanager
def _disk_cache_lock(*, shared: bool) -> Iterator[None]:
    """对规则磁盘缓存做跨进程互斥 (ADR-075).

    为何需要: 缓存的读写是**读-改-写**序列, 天然会丢更新。
    实测 (6 个真实子进程并发): 去掉事务锁后每轮只剩 1 个 key, 丢 5/6;
    加锁后 5 轮均零丢失。pytest-xdist 下多个 worker 是独立进程, 都会走
    ``load_rules``, 故这不是理论风险。

    为何锁文件放在缓存目录**之外**: 缓存目录本身会被整体清理, 锁文件
    若放在里面, 清理后锁文件消失, 另一进程正持有的 fd 仍有效但新进程
    会新建另一个锁文件, 互斥失效。故放在系统临时目录。

    为何 ``shared=True`` 用 ``LOCK_SH``: 多个读者之间无冲突, 不该把
    缓存退化成全局串行; 而写者持 ``LOCK_EX``, 共享锁天然被它挡住。

    为何锁路径按缓存目录派生而非固定一个名字: 锁的作用域必须与它保护的
    数据一致。``ADG_RULES_CACHE_DIR`` 允许不同调用方指向不同缓存文件,
    此时它们本不该互相阻塞 —— 固定锁名会把不相关的缓存退化成全局串行
    (pytest 里每个测试都有自己的 tmp 缓存目录, 固定锁会让它们白白排队)。
    故用缓存目录路径的 sha1 前缀派生, 既保证“同一份缓存 → 同一把锁”
    (互斥成立), 又保证“不同缓存 → 不同锁”(互不干扰)。
    """
    # sha256 而非 sha1: 此前用 sha1 既被 bandit (B324) 拦截, 也被 ADG 自身的
    # "使用 SHA1" 规则拦截 —— usedforsecurity=False 只能消前者, 消不掉后者。
    # 此处仅把缓存目录路径派生成锁文件短名, 无安全用途, 换 sha256 无额外成本。
    digest = hashlib.sha256(str(_DISK_CACHE_DIR.resolve()).encode()).hexdigest()[:12]
    lock_path = Path(tempfile.gettempdir()) / f"adg-rules-disk-cache-{digest}.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_disk_cache() -> dict[str, Any]:
    """Load rules from disk cache.

    ADR-075: 读也必须持**共享**锁。仅锁写者时, 读者会在写者持
    ``LOCK_EX`` 期间读到 ``write_text`` 的中间态 (文件被截断但尚未
    写完), 于是 ``json.loads`` 抛 JSONDecodeError 而被下面的
    ``except`` 吞掉, 返回空 dict —— 缓存静默失效。
    """
    with _disk_cache_lock(shared=True):
        return _load_disk_cache_locked()


def _load_disk_cache_locked() -> dict[str, Any]:
    """**调用方必须已持锁**的读取实现 (ADR-075)."""
    if _DISK_CACHE_FILE.exists():
        try:
            result: dict[str, Any] = json.loads(_DISK_CACHE_FILE.read_text())
            return result
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_disk_cache(cache: dict[str, Any]) -> None:
    """Save rules to disk cache.

    ADR-075: 必须持**独占**锁, 且必须是原子的。

    原实现是裸 ``write_text``: 它先把文件截断为 0 字节, 再逐字写入。
    任何并发读者都可能读到 0 字节或半截 JSON。
    """
    with _disk_cache_lock(shared=False):
        _save_disk_cache_locked(cache)


def _save_disk_cache_locked(cache: dict[str, Any]) -> None:
    """**调用方必须已持锁**的写入实现 (ADR-075)."""
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # 先写临时文件再 ``os.replace`` —— rename 在同一文件系统内
        # 是原子的, 读者要么看到旧内容要么看到新内容, 不会看到半截。
        tmp = _DISK_CACHE_FILE.with_suffix(f".json.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache))
        os.replace(tmp, _DISK_CACHE_FILE)
    except OSError:
        pass


@lru_cache(maxsize=64)
def _rules_hash_cached(language: str, framework_dir_str: str) -> str:
    """Hash of rule files for cache invalidation (cached per (language, dir)).

    必须同时纳入语言规则与 common/security.yml：后者是合并进最终规则的
    输入之一，只哈希语言文件会导致 common 规则变更后缓存不失效。
    """
    framework_dir = Path(framework_dir_str)
    paths = [
        framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml",
        framework_dir / "common" / "security.yml",
    ]
    digest = hashlib.sha256()
    try:
        for path in paths:
            if path.exists():
                digest.update(path.read_bytes())
                digest.update(b"\x00")
        return digest.hexdigest()
    except OSError:
        return ""


@lru_cache(maxsize=4)
def _load_common_rules_cached(framework_dir_str: str) -> dict[str, Any]:
    """Load common cross-language rules (cached by framework dir)."""
    framework_dir = Path(framework_dir_str)
    common_path = framework_dir / "common" / "security.yml"
    if not common_path.exists():
        return {}
    try:
        import yaml

        with open(common_path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


@lru_cache(maxsize=4)
def _load_universal_rules_cached(framework_dir_str: str) -> dict[str, Any]:
    """Load universal quality rules (cached by framework dir)."""
    framework_dir = Path(framework_dir_str)
    result: dict[str, Any] = {"anti_patterns": [], "thresholds": {}, "naming": {}}
    universal_path = framework_dir / "common" / "universal.yml"
    if universal_path.exists():
        try:
            import yaml

            with open(universal_path) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                result = data
        except (OSError, yaml.YAMLError):
            pass  # universal rules optional
    common = _load_common_rules_cached(framework_dir_str)
    if common:
        result = _merge_rules(result, common)
    return result


def _rules_hash(language: str, framework_dir: Path | None = None) -> str:
    """Hash of rule file for cache invalidation (delegates to cached impl)."""
    if framework_dir is None:
        framework_dir = rules_dir()
    return _rules_hash_cached(language, str(framework_dir))


def _load_common_rules(framework_dir: Path | None = None) -> dict[str, Any]:
    """Load common cross-language rules (delegates to cached impl)."""
    if framework_dir is None:
        framework_dir = rules_dir()
    return _load_common_rules_cached(str(framework_dir))


def _load_universal_rules(framework_dir: Path | None = None) -> dict[str, Any]:
    """Load universal quality rules (delegates to cached impl)."""
    if framework_dir is None:
        framework_dir = rules_dir()
    return _load_universal_rules_cached(str(framework_dir))


def _try_load_yaml(rule_path: Path, framework_dir: Path) -> dict[str, Any] | None:
    """Try to load rules from YAML file, return None if failed."""
    try:
        import yaml
    except ImportError:
        # PyYAML not available - use universal rules
        logger.info("Warning: PyYAML not installed. Using universal rules.", file=sys.stderr)
        return None

    if not rule_path.exists():
        return None

    try:
        with open(rule_path) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None

    result = data if isinstance(data, dict) else {}

    # Load common cross-language rules
    common = _load_common_rules(framework_dir)
    if common:
        result = _merge_rules(result, common)

    # Load generated rules (from /generate-rules skill)
    # Note: language detection would be needed here, but we don't have it
    # This is handled at the call site

    return result


def _load_language_rules_with_fallback(language: str, framework_dir: Path) -> dict[str, Any]:
    """Load rules for a language with fallback strategies."""
    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    # Try to load from YAML file
    result = _try_load_yaml(rule_path, framework_dir)
    if result is not None:
        return result

    # Language not in our database - try generated rules, then universal
    generated = _load_generated_rules(language)
    if generated:
        logger.info(f"Loaded {len(generated)} generated rules for '{language}'.")
        result = {"anti_patterns": generated}
        common = _load_common_rules(framework_dir)
        if common:
            result = _merge_rules(result, common)
        return result

    logger.info(
        f"No specific rules for '{language}', using universal quality rules.",
        file=sys.stderr,
    )
    return _load_universal_rules(framework_dir)


def load_rules(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load YAML rules for a given language with caching."""
    # Check in-memory cache
    rh = _rules_hash(language, framework_dir)
    cache_key = f"{language}:{rh}"
    if cache_key in _RULE_CACHE:
        return _RULE_CACHE[cache_key]

    # ADR-075: 磁盘缓存的读-改-写必须**整体**在独占锁内完成。
    #
    # 为何不能在调用点简单包一层锁: 若先 ``_load_disk_cache()``(取锁再放)
    # 再 ``_save_disk_cache()``(再取一次锁), 两次取锁之间另一个进程可以
    # 完整地读写一轮, 于是本进程拿着**陈旧快照**去覆盖, 仍会丢更新。
    # 实测: 只给两个 IO 函数各自加锁后, 60 次并发循环里仍丢 4 次;
    # 改成用一个函数包住整个事务后降到 0 次。
    with _disk_cache_lock(shared=False):
        disk_cache = _load_disk_cache_locked()
        if cache_key in disk_cache:
            _RULE_CACHE[cache_key] = disk_cache[cache_key]
            cached: dict[str, Any] = disk_cache[cache_key]
            return cached

        if framework_dir is None:
            framework_dir = rules_dir()

        # Load rules with fallback strategies
        result = _load_language_rules_with_fallback(language, framework_dir)

        # Load generated rules (from /generate-rules skill)
        generated = _load_generated_rules(language)
        if generated:
            result.setdefault("anti_patterns", [])
            result["anti_patterns"].extend(generated)

        # Cache the result
        _RULE_CACHE[cache_key] = result

        # Save to disk cache
        disk_cache[cache_key] = result
        _save_disk_cache_locked(disk_cache)

    return result


def load_custom_rules(project_dir: Path) -> dict[str, Any]:
    """Load custom rules from multiple sources with inheritance.

    Priority order (later overrides earlier):
    1. ~/.config/adg/rules.yml (user global config)
    2. .adg/rules.yml (project-level config)
    3. .ai-rules/*.yml (legacy directory-based config)

    Rules with the same ID override built-in rules.
    """
    custom: dict[str, Any] = {"anti_patterns": [], "naming": {}, "thresholds": {}}

    # Source 1: User global config (~/.config/adg/rules.yml)
    global_config = Path.home() / ".config" / "adg" / "rules.yml"
    if global_config.is_file():
        _load_single_custom_file(global_config, custom)

    # Source 2: Project-level .adg/rules.yml
    project_adg_rules = project_dir / ".adg" / "rules.yml"
    if project_adg_rules.is_file():
        _load_single_custom_file(project_adg_rules, custom)

    # Source 3: Legacy .ai-rules/*.yml directory
    ai_rules_dir = project_dir / ".ai-rules"
    if ai_rules_dir.is_dir():
        for rule_file in sorted(ai_rules_dir.glob("*.yml")):
            _load_single_custom_file(rule_file, custom)

    return custom


def _load_single_custom_file(rule_file: Path, custom: dict[str, Any]) -> None:
    """Load a single custom rule file and merge into custom dict."""
    try:
        import yaml
    except ImportError:
        logger.info("Warning: PyYAML not installed. Custom rules skipped.", file=sys.stderr)
        return

    try:
        with open(rule_file) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return

        # Merge anti_patterns (override by ID)
        new_patterns = data.get("anti_patterns", [])
        custom["anti_patterns"].extend(new_patterns)

        # Merge naming rules
        if "naming" in data:
            custom["naming"].update(data["naming"])

        # Merge thresholds (override)
        if "thresholds" in data:
            custom["thresholds"].update(data["thresholds"])

    except Exception as e:
        print(f"Warning: Failed to load {rule_file}: {e}", file=sys.stderr)


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules. Custom overrides by ID.

    Supports two modes:
    - Full replacement: custom rule with same ID replaces the entire base rule
    - Severity override: custom rule with severity_override only changes severity
    """
    merged = dict(base)

    # Merge anti_patterns
    merged["anti_patterns"] = _merge_anti_patterns(
        merged.get("anti_patterns", []),
        custom.get("anti_patterns", []),
    )

    # Merge naming
    if custom.get("naming"):
        merged.setdefault("naming", {}).update(custom["naming"])

    # Merge thresholds
    if custom.get("thresholds"):
        merged.setdefault("thresholds", {}).update(custom["thresholds"])

    return merged


# ──────────────────────────────────────────────────────────
# Cross-language common rules
# ──────────────────────────────────────────────────────────


def _get_embedded_rules(language: str) -> dict[str, Any]:
    """Fallback embedded rules when YAML files are unavailable."""
    common_anti_patterns: list[dict[str, Any]] = [
        {
            "id": f"{language[:2]}-eval-exec",
            "name": "Use of eval/exec",
            "severity": "error",
            "category": "security",
            "pattern": r"\beval\s*\(|\bexec\s*\(",
            "message": "eval/exec are security risks",
            "fix_hint": "Find a safer alternative",
        },
        {
            "id": f"{language[:2]}-hardcoded-secret",
            "name": "Hardcoded secret",
            "severity": "error",
            "category": "security",
            "pattern": r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            "message": "Hardcoded secrets are a security vulnerability",
            "fix_hint": "Use environment variables",
        },
    ]
    return {"anti_patterns": common_anti_patterns, "thresholds": {}, "naming": {}}


def load_rules_for_language(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load rules for a language, merging with common security rules.

    Common rules come from common/security.yml (loaded by load_rules()).
    All cross-language rules are consolidated there; this module is the
    single loader for them.
    """
    return load_rules(language, framework_dir)


def _find_active_domains(project_path: Path) -> list[str]:
    """Find active domains from project configuration files."""
    config_sources = [
        project_path / ".adg" / "config.yml",
        project_path / ".jcode" / "config.yml",
    ]

    for config_path in config_sources:
        if config_path.exists():
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text())
                domains = data.get("domains", []) if isinstance(data, dict) else []
                return list(domains) if isinstance(domains, list) else []
            except Exception as exc:
                logger.debug(f"Skipped unreadable domain config {config_path}: {exc}")
    return []


def _load_domain_rule_file(domains_dir: Path, domain: str) -> list[dict[str, Any]]:
    """Load anti-patterns from a domain rule file."""
    rule_file = domains_dir / f"{domain}.yml"
    if not rule_file.exists():
        return []

    try:
        import yaml

        data = yaml.safe_load(rule_file.read_text())
        patterns = data.get("anti_patterns", []) if isinstance(data, dict) else []
        return list(patterns) if isinstance(patterns, list) else []
    except (OSError, yaml.YAMLError):
        return []


def load_domain_rules(project_path: Path, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load domain-specific rules based on project configuration.

    Reads .adg/config.yml for `domains:` field and loads matching
    rule files from ai-dev-framework/domains/{domain}.yml.

    Args:
        project_path: Project root directory.
        framework_dir: Framework root directory.

    Returns:
        Dict with 'anti_patterns' key containing domain rules.
    """
    result: dict[str, Any] = {"anti_patterns": []}

    fd = framework_dir or rules_dir()
    domains_dir = fd / "domains"

    active_domains = _find_active_domains(project_path)

    for domain in active_domains:
        patterns = _load_domain_rule_file(domains_dir, domain)
        result["anti_patterns"].extend(patterns)

    return result


def get_language_rules(language: str) -> dict[str, Any]:
    """Get rules for a language (cached)."""
    return load_rules_for_language(language)
