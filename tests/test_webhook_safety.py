"""Tests for webhook URL safety validation."""

from __future__ import annotations

from tools.scripts.webhook_safety import is_safe_webhook_url, validate_webhook_url


class TestWebhookSafety:
    def test_allows_https_public_host(self) -> None:
        assert is_safe_webhook_url("https://hooks.slack.com/services/T/B/x")
        assert is_safe_webhook_url("https://oapi.dingtalk.com/robot/send?access_token=abc")

    def test_allows_http_non_local_test_host(self) -> None:
        # 测试环境常用占位域名，非字面量私网 IP，不应被 SSRF 规则误杀
        assert is_safe_webhook_url("http://hook.test/path")

    def test_rejects_non_http_schemes(self) -> None:
        assert not is_safe_webhook_url("file:///etc/passwd")
        assert not is_safe_webhook_url("ftp://example.com/x")
        assert not is_safe_webhook_url("slack://T/B/x")  # scheme 需由上层展开

    def test_rejects_localhost_and_loopback(self) -> None:
        assert not is_safe_webhook_url("http://localhost:8080/hook")
        assert not is_safe_webhook_url("http://127.0.0.1/hook")
        assert not is_safe_webhook_url("http://[::1]/hook")

    def test_rejects_private_and_link_local_literals(self) -> None:
        assert not is_safe_webhook_url("http://10.0.0.5/hook")
        assert not is_safe_webhook_url("http://192.168.1.2/hook")
        assert not is_safe_webhook_url("http://169.254.169.254/latest/meta-data/")
        assert not is_safe_webhook_url("http://172.16.0.1/hook")

    def test_rejects_metadata_hosts(self) -> None:
        assert not is_safe_webhook_url("http://metadata.google.internal/computeMetadata/v1/")
        assert not is_safe_webhook_url("http://instance-data/latest/meta-data/")

    def test_validate_returns_reason(self) -> None:
        assert validate_webhook_url("https://example.com/hook") is None
        assert validate_webhook_url("http://127.0.0.1/hook") is not None
