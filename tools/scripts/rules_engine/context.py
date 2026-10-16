"""上下文感知模块 — 根据文件角色调整规则严重度。

文件角色通过路径模式声明，规则根据角色自动升降严重度。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from tools.scripts.rules_engine.logger import logger

# ── 内置角色定义 ──────────────────────────────
# key: 角色名, value: (描述, 严重度调整值)
# 调整值: +1=升一级 error→更严格, -1=降一级, -2=降两级
ROLES: dict[str, tuple[str, int]] = {
    "test": ("测试文件,降低规则严格度", -1),
    "prototype": ("原型/一次性脚本,大幅降低严格度", -2),
    "legacy": ("遗留代码,可警告但不阻止", -1),
    "production": ("核心生产代码,提高严格度", +1),
    "config": ("配置/模板文件,跳过大部分检查", -2),
    "demo": ("示例/演示代码,降低严格度", -2),
}

# 默认路径 → 角色映射 (可通过 .adg/config.yml 覆盖)
DEFAULT_MARKERS: dict[str, str] = {
    # 测试
    "tests/": "test",
    "test/": "test",
    "__tests__/": "test",
    "spec/": "test",
    "*_test.go": "test",
    "*.test.ts": "test",
    "*.test.js": "test",
    "*_test.py": "test",
    # 原型/一次性
    "scripts/": "prototype",
    "bin/": "prototype",
    "tools/": "prototype",
    "archive/": "prototype",
    "scratch/": "prototype",
    "draft/": "prototype",
    # 遗留
    "legacy/": "legacy",
    "deprecated/": "legacy",
    "old/": "legacy",
    "v1/": "legacy",
    "backward/": "legacy",
    # 配置
    "config/": "config",
    "*.config.js": "config",
    "*.yml": "config",
    "*.yaml": "config",
    "*.json": "config",
    "Dockerfile": "config",
    # 演示
    "examples/": "demo",
    "demo/": "demo",
    "samples/": "demo",
}

# 严重度顺序
SEVERITY_ORDER = {"error": 3, "warning": 2, "info": 1, "off": 0}


def detect_file_role(filepath: Path, marker_overrides: dict[str, str] | None = None) -> str | None:
    """检测文件角色 (V2.22 P6-7 拆分: 抽 _match_pattern).

    Args:
        filepath: 文件路径。
        marker_overrides: 用户自定义覆盖默认路径映射。

    Returns:
        角色名, 如 'test', 'production'。
    """
    markers = dict(DEFAULT_MARKERS)
    if marker_overrides:
        markers.update(marker_overrides)

    rel_path_str = str(filepath.as_posix())
    filename = filepath.name

    for pattern, role in markers.items():
        if _match_pattern(pattern, rel_path_str, filename):
            return role

    return None


def _match_pattern(pattern: str, rel_path_str: str, filename: str) -> bool:
    """单 pattern 匹配 (glob 简化 / substring, 模块级 helper).

    Args:
        pattern: marker pattern (含 * 或纯字符串)
        rel_path_str: 相对路径字符串
        filename: 文件名

    Returns:
        True 表示匹配
    """
    if "*" in pattern:
        # 简单 glob 匹配
        parts = pattern.split("*")
        if len(parts) == 2:
            if rel_path_str.startswith(parts[0]) and rel_path_str.endswith(parts[1]):
                return True
            if filename.startswith(parts[0]) and filename.endswith(parts[1]):
                return True
        return False
    return pattern in rel_path_str


def adjust_severity(original_severity: str, file_role: str | None) -> str:
    """根据文件角色调整严重度。

    Args:
        original_severity: 原始严重度 (error/warning/info)
        file_role: 文件角色

    Returns:
        调整后的严重度
    """
    if not file_role or file_role not in ROLES:
        return original_severity

    _desc, adjustment = ROLES[file_role]
    current = SEVERITY_ORDER.get(original_severity, 2)
    new_level = max(1, min(3, current + adjustment))  # 下限为info(1), 不降到off

    # 映射数字回字符串
    reverse = {v: k for k, v in SEVERITY_ORDER.items()}
    adjusted = reverse.get(new_level, original_severity)

    # 不允许从 info 升级到 error (但可以从 error 降级)
    if adjusted == "error" and original_severity != "error":
        return original_severity

    return adjusted


@lru_cache(maxsize=16)
def _load_role_config_cached(path_str: str, mtime_ns: int) -> dict[str, str]:
    """解析 .adg/config.yml 的 context.markers（按 mtime 缓存）。

    mtime_ns 参与缓存键：配置文件被改写后自动失效，避免 LSP/dashboard 这类
    长驻进程读到过期结果。path_str/mtime_ns 只作缓存键，不参与逻辑判断。
    """
    import yaml

    config_path = Path(path_str)
    try:
        data = yaml.safe_load(config_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        logger.debug(f"角色标记配置读取失败: {exc}")
        return {}
    if not isinstance(data, dict):
        # 空文件或纯标量 YAML: safe_load 返回 None/str, 不是 dict
        return {}
    context = data.get("context")
    markers = context.get("markers") if isinstance(context, dict) else None
    return markers if isinstance(markers, dict) else {}


def load_role_config(config_path: Path) -> dict[str, str]:
    """从配置文件加载角色映射。

    配置文件格式: .adg/config.yml 中的 context.markers 字段。

    结果按 (路径, mtime) 缓存: 一次目录扫描里所有文件命中同一份配置，
    避免逐文件重复 yaml.safe_load（实测 60 文件重复解析 37 次）。
    返回副本，防止调用方就地修改污染缓存。
    """
    try:
        mtime_ns = config_path.stat().st_mtime_ns
    except OSError as exc:
        logger.debug(f"角色标记配置不存在: {exc}")
        return {}
    return dict(_load_role_config_cached(str(config_path), mtime_ns))
