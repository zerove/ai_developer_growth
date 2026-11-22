"""_sc_pypi 变异杀伤补强（P1 后续：已识别 survivors 定向锁死行为）。

test_supply_chain_compliance_policy.py 原有限制（测试文件 ≤500 行）下，
新增的 mutation hardening 测试拆到独立文件：
- mut#71: 非 License classifier 前置 + 返回正常
- mut#92/103/108: _fetch 终态返回 None + 写警告 + 状态收敛
- mut#95: package_missing 状态一致性
- mut#98: license_of 回退 info["license"] 文本
- mut#111/113/114/115: resolve_version 的 specifier 分支
- mut#122/125: _first_compatible 前缀边界与排序
- mut#1313/1314: client 状态/缺失语义
- mut#1320/1321/1323/1324/1325/1326/1327/1328/1329/1330/1331/1332/1333/1334/1335: retry/404/5xx 分支
"""

from __future__ import annotations

import urllib.error
from typing import Any

import pytest

from tools.scripts._sc_pypi import PyPIMetadataClient, license_from_classifiers


class FakePyPI:
    """用假数据替身模拟 PyPI 元数据。"""

    def __init__(self, packages: dict[str, dict[str, Any]]) -> None:
        self.packages = packages

    def client(self) -> PyPIMetadataClient:
        client = PyPIMetadataClient()
        client._cache = {name: data for name, data in self.packages.items()}
        return client


class TestPyPIMutationHardening:
    def test_classifier_skips_non_license_then_matches(self) -> None:
        # 杀 mut#71: continue->break 会在非 License classifier 处提前退出
        assert (
            license_from_classifiers(
                [
                    "Programming Language :: Python :: 3",
                    "License :: OSI Approved :: MIT License",
                ]
            )
            == "MIT"
        )

    def test_pypi_client_default_timeout(self) -> None:
        client = PyPIMetadataClient()
        assert client.timeout == 15
        assert client._cache == {}
        assert client._missing == set()

    def test_license_of_falls_back_to_info_license_text(self) -> None:
        # 杀 mut#98: info.get("license") 被误改键名
        fake = FakePyPI({"pkg": {"info": {"license": "Apache Software License 2.0"}}})
        assert fake.client().license_of("pkg") == "Apache-2.0"

    def test_resolve_version_specifier_empty_string(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"0.23.0": [], "0.24.0": []}}})
        assert fake.client().resolve_version("pkg", "0.23", "") == "0.23.0"

    def test_resolve_version_specifier_tilde_arrow(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.2.0": [], "1.3.0": []}}})
        assert fake.client().resolve_version("pkg", "1.1", "~>") == "1.2.0"

    def test_resolve_version_specifier_gt(self) -> None:
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.2.0": [], "1.3.0": []}}})
        assert fake.client().resolve_version("pkg", "1.1", ">") == "1.2.0"

    def test_resolve_version_specifier_triple_eq(self) -> None:
        # === 走下界匹配分支（与 == 不同）；杀 mut#115
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.2.0": [], "1.3.0": []}}})
        assert fake.client().resolve_version("pkg", "1.1", "===") == "1.2.0"

    def test_compatible_prefix_uses_pep440_segment_boundary(self) -> None:
        # 杀 mut#122: ~=1.2.3 只允许 1.2.x，不能跨到 1.3.x
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.2.9": [], "1.3.0": []}}})
        assert fake.client().resolve_version("pkg", "1.2.3", "~=") == "1.2.9"

    def test_compatible_picks_highest_in_prefix(self) -> None:
        # 杀 mut#125: reverse=False 会选最低兼容版本
        fake = FakePyPI({"pkg": {"info": {}, "releases": {"1.2.3": [], "1.2.9": [], "1.3.0": []}}})
        assert fake.client().resolve_version("pkg", "1.2.0", "~=") == "1.2.9"

    def test_package_missing_true_for_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = PyPIMetadataClient()

        def fake_urlopen(request: Any, timeout: int = 0) -> Any:
            raise urllib.error.HTTPError(request.full_url, 404, "not found", hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert client.package_missing("nope") is True
        assert client.package_missing("nope") is True  # 缓存命中

    def test_package_missing_false_for_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = PyPIMetadataClient()

        def fake_urlopen(request: Any, timeout: int = 0) -> Any:
            raise urllib.error.HTTPError(request.full_url, 503, "down", hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        assert client.package_missing("pkg") is False

    def test_fetch_retries_on_5xx_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = PyPIMetadataClient()
        calls: list[int] = []
        sleeps: list[float] = []

        class Resp:
            def __enter__(self) -> Resp:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"info": {}, "releases": {"1.0.0": []}}'

        def fake_urlopen(request: Any, timeout: int = 0) -> Resp:
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError(request.full_url, 500, "err", hdrs=None, fp=None)
            return Resp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        data = client.metadata("pkg")
        assert data is not None
        assert len(calls) == 3
        assert sleeps == [0.5, 1.0]  # 0.5 * attempt

    def test_fetch_retries_on_exception_then_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = PyPIMetadataClient()
        calls: list[int] = []
        sleeps: list[float] = []

        def fake_urlopen(request: Any, timeout: int = 0) -> Any:
            calls.append(1)
            raise OSError("boom")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        assert client.metadata("pkg") is None
        assert len(calls) == 3
        assert sleeps == [0.5, 1.0]

    def test_fetch_404_does_not_retry(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        client = PyPIMetadataClient()
        calls: list[int] = []

        def fake_urlopen(request: Any, timeout: int = 0) -> Any:
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, 404, "not found", hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert client.metadata("missing") is None
        assert calls == [1]
        assert client.package_missing("missing") is True
        # mut#95: 状态为空时一律按存在处理
        assert client._missing == {"missing"}
        assert "PyPI metadata lookup failed" in caplog.text

    def test_fetch_warning_logged_on_terminal_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # mut#92: retry 循环试图再次成功 → 变异体存活。固化“正常失败+尝试次数有限”语义。
        client = PyPIMetadataClient()

        def fake_urlopen(request: Any, timeout: int = 0) -> Any:
            raise urllib.error.HTTPError(request.full_url, 503, "down", hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        assert client.metadata("pkg") is None
        # mut#103/108: 应回传 None 并写入警告（非silent）
        assert "PyPI metadata lookup failed" in caplog.text
        assert client.metadata("pkg") is None  # 重试：已记录警告

    def test_fetch_non_retryable_http_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = PyPIMetadataClient()
        calls: list[int] = []

        def fake_urlopen(request: Any, timeout: int = 0) -> Any:
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, 403, "forbidden", hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert client.metadata("pkg") is None
        assert calls == [1]
        assert client.package_missing("pkg") is False

    def test_fetch_sends_accept_json_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = PyPIMetadataClient()
        seen: dict[str, Any] = {}

        class Resp:
            def __enter__(self) -> Resp:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b"{}"

        def fake_urlopen(request: Any, timeout: int = 0) -> Resp:
            seen["url"] = request.full_url
            seen["accept"] = request.get_header("Accept")
            seen["timeout"] = timeout
            return Resp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        client.metadata("Pkg.Name")
        assert seen["url"] == "https://pypi.org/pypi/Pkg.Name/json"
        assert seen["accept"] == "application/json"
        assert seen["timeout"] == 15
