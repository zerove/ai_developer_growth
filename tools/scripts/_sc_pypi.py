"""PyPI 元数据补齐: 依赖许可证与可安装版本解析。

供应链扫描只能从项目清单文件 (pyproject.toml / requirements.txt 等) 读到依赖
声明, 但这两类文件都不含依赖自身的许可证, 声明的版本约束 (如 `>=0.23`) 也不是
可安装的确切版本号。直接拿去做判定必然误判:

- 许可证恒为 None → 全部落到 REVIEW 分支, 合规检查失去判别力;
- 版本 `0.23` 在 PyPI 上不存在 (真实版本是 0.23.0) → 存在性校验必然失败。

本模块通过 PyPI JSON API 补齐这两项信息, 并做进程内缓存, 供 compliance /
verify 两个供应链动作复用。网络不可用时返回 None (许可证保持未知 / 版本保持
未验证), 由调用方按"未知即待复核"处理, 不做静默放行。
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"

# Trove classifier 末段 → SPDX 许可证标识符。
# classifier 形如 "License :: OSI Approved :: MIT License", 末段是许可证名称。
CLASSIFIER_TO_SPDX: dict[str, str] = {
    "mit license": "MIT",
    "apache software license": "Apache-2.0",
    "bsd license": "BSD-3-Clause",
    "isc license (iscl)": "ISC",
    "isc license": "ISC",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "mozilla public license 1.1 (mpl 1.1)": "MPL-1.1",
    "gnu general public license v3 or later (gplv3+)": "GPL-3.0",
    "gnu general public license v2 or later (gplv2+)": "GPL-2.0",
    "gnu lesser general public license v3 or later (lgplv3+)": "LGPL-3.0",
    "gnu lesser general public license v2 or later (lgplv2+)": "LGPL-2.1",
    "python software foundation license": "Python-2.0",
    "zlib/libpng license": "Zlib",
    "the unlicense (unlicense)": "Unlicense",
    "zope public license": "ZPL-2.1",
}

# 许可证纯文本兜底: 关键词 → SPDX 标识符 (info.license 字段常见写法)
TEXT_KEYWORD_TO_SPDX: dict[str, str] = {
    "mit": "MIT",
    "apache": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "isc": "ISC",
    "mozilla public license": "MPL-2.0",
    "gnu general public license": "GPL-3.0",
    "gnu lesser general public license": "LGPL-3.0",
}


def version_key(version: str) -> tuple[int, ...]:
    """把版本串转成可比较的元组 (非数字片段按 0 处理)。

    Args:
        version: 版本字符串, 如 "0.23.0"

    Returns:
        逐段整数元组, 如 (0, 23, 0)
    """
    parts: list[int] = []
    for chunk in version.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def version_at_least(candidate: str, minimum: str) -> bool:
    """判断 candidate 是否 >= minimum (逐段数字比较)。

    Args:
        candidate: 候选版本, 如 "0.23.1"
        minimum: 下界版本, 如 "0.23"

    Returns:
        True 表示 candidate 不低于 minimum
    """
    return version_key(candidate) >= version_key(minimum)


def normalize_license_expression(expression: str | None) -> str | None:
    """归一化 PEP 639 许可证表达式 (如 "MIT OR Apache-2.0")。

    Args:
        expression: PyPI 元数据的 license_expression 字段

    Returns:
        归一化后的表达式; 为空时返回 None
    """
    if not expression:
        return None
    normalized = " ".join(expression.split())
    return normalized or None


def normalize_license_text(text: str | None) -> str | None:
    """把许可证自由文本归一化为 SPDX 标识符。

    Args:
        text: PyPI 元数据里的许可证文本

    Returns:
        SPDX 标识符; 无法归一化时返回 None
    """
    if not text:
        return None
    lowered = text.lower()
    for keyword, spdx in TEXT_KEYWORD_TO_SPDX.items():
        if keyword in lowered:
            return spdx
    return None


def license_from_classifiers(classifiers: list[str]) -> str | None:
    """从 Trove classifier 中提取许可证并归一化。

    Args:
        classifiers: PyPI 元数据的 classifiers 列表

    Returns:
        SPDX 标识符; 无许可证 classifier 时返回 None
    """
    for classifier in classifiers:
        parts = [part.strip() for part in classifier.split("::")]
        if len(parts) < 2 or parts[0] != "License":
            continue
        name = parts[-1]
        mapped = CLASSIFIER_TO_SPDX.get(name.lower())
        if mapped:
            return mapped
        return name
    return None


class PyPIMetadataClient:
    """PyPI 包元数据客户端 (进程内按包名缓存)。"""

    def __init__(self, timeout: int = 15) -> None:
        """初始化客户端。

        Args:
            timeout: 单次 HTTP 请求超时秒数
        """
        self.timeout = timeout
        self._cache: dict[str, dict[str, Any] | None] = {}
        self._missing: set[str] = set()

    def metadata(self, name: str) -> dict[str, Any] | None:
        """取包元数据 (带缓存)。

        Args:
            name: 包名

        Returns:
            PyPI JSON 元数据; 包不存在或网络失败时返回 None
        """
        if name not in self._cache:
            self._cache[name] = self._fetch(name)
        return self._cache[name]

    def package_missing(self, name: str) -> bool:
        """包是否确实不存在于 PyPI (HTTP 404)。

        与"网络不可达"区分开: 前者是依赖声明有错, 后者只是查不到。

        Args:
            name: 包名

        Returns:
            True 表示 PyPI 上没有这个包
        """
        self.metadata(name)
        return name in self._missing

    def _fetch(self, name: str) -> dict[str, Any] | None:
        """执行 PyPI JSON 查询（对瞬时网络错误做有限重试）。"""
        url = PYPI_JSON_URL.format(name=name)
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310 - 固定 https 主机
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    self._missing.add(name)
                    logger.warning("PyPI metadata lookup failed for %s: %s", name, exc)
                    return None
                if exc.code >= 500 and attempt < attempts:
                    time.sleep(0.5 * attempt)
                    continue
                logger.warning("PyPI metadata lookup failed for %s: %s", name, exc)
                return None
            except Exception as exc:  # noqa: BLE001 - 元数据缺失不应中断扫描
                if attempt < attempts:
                    time.sleep(0.5 * attempt)
                    continue
                logger.warning("PyPI metadata lookup failed for %s: %s", name, exc)
                return None
        return None

    def license_of(self, name: str) -> str | None:
        """解析包的许可证 (SPDX 标识符或 PEP 639 表达式)。

        取值优先级: PEP 639 的 license_expression → Trove license classifier →
        license 自由文本。PyPI 已对多数包停止下发 classifier 并改用表达式字段。

        Args:
            name: 包名

        Returns:
            SPDX 标识符 / 表达式; 解析不出时返回 None
        """
        data = self.metadata(name)
        if not data:
            return None
        info = data.get("info") or {}
        expression = normalize_license_expression(info.get("license_expression"))
        if expression:
            return expression
        classifiers = info.get("classifiers") or []
        resolved = license_from_classifiers(list(classifiers))
        if resolved:
            return resolved
        return normalize_license_text(info.get("license"))

    def release_versions(self, name: str) -> list[str]:
        """列出包已发布的版本号。

        Args:
            name: 包名

        Returns:
            版本号列表; 包不存在或网络失败时返回空列表
        """
        data = self.metadata(name)
        if not data:
            return []
        releases = data.get("releases") or {}
        return [version for version in releases if isinstance(version, str)]

    def resolve_version(self, name: str, version: str, specifier: str | None = None) -> str | None:
        """按声明的版本约束解析出真实存在的发布版本。

        Args:
            name: 包名
            version: 清单文件里声明的版本 (可能只是下界)
            specifier: 版本约束符 (">=" / "==" / None 等)

        Returns:
            满足约束的发布版本; 无匹配时返回 None
        """
        versions = self.release_versions(name)
        if not versions:
            return None
        if version and version in versions:
            return version
        if specifier == "~=":
            return self._first_compatible(versions, version)
        if specifier in (None, "", ">=", "~>", ">", "==="):
            return self._first_at_least(versions, version)
        # "==" 表示精确锁定: 该版本未发布就不能满足约束
        return None

    @staticmethod
    def _first_at_least(versions: list[str], minimum: str) -> str | None:
        """找出版本号不低于下界的最小发布版本。"""
        if not minimum:
            return None
        candidates = [v for v in versions if version_at_least(v, minimum)]
        if not candidates:
            return None
        return min(candidates, key=version_key)

    @staticmethod
    def _first_compatible(versions: list[str], version: str) -> str | None:
        """按 ~= 语义查找兼容版本 (同前缀且不低于声明版本)。

        PEP 440 的 ~=1.2 允许 1.x 内升级, ~=1.2.3 只允许 1.2.x ——
        可升级的上界由声明版本自身的段数决定。
        """
        if not version:
            return None
        prefix = version_key(version)[:-1]
        for candidate in sorted(versions, key=version_key, reverse=True):
            if version_key(candidate)[: len(prefix)] != prefix:
                continue
            if version_at_least(candidate, version):
                return candidate
        return None
