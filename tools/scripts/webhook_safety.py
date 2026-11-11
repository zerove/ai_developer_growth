"""Webhook URL safety checks (SSRF mitigation).

策略：允许 http/https；拒绝明显的内网/本机/元数据目标与非法 scheme。
不做 DNS 解析（避免副作用与耗时），对字面量 IP 与常见主机名做保守拦截。
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_METADATA_HOSTS = {
    "metadata.google.internal",
    "metadata",
    "instance-data",
}
_LOCAL_HOSTS = {"localhost", "localhost.localdomain"}


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def is_safe_webhook_url(url: str) -> bool:
    """Return True if URL is acceptable for outbound webhook delivery."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in _LOCAL_HOSTS or host in _METADATA_HOSTS:
        return False
    if host.endswith(".local"):
        return False

    # Bracketed IPv6 in hostname is normalized by urlparse; handle literals.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        return not _is_disallowed_ip(ip)

    # Best-effort: if host is a numeric-ish form socket parses oddly, try getaddrinfo-free check only for literals.
    # Domain names (e.g. hook.test, hooks.slack.com) are allowed here; callers may add allowlists.
    return True


def validate_webhook_url(url: str) -> str | None:
    """Return None if safe, else a short rejection reason."""
    if is_safe_webhook_url(url):
        return None
    return "unsafe webhook URL (blocked scheme/host)"
