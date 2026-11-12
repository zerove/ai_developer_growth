"""例外清单 → Policy as Code 输入链路的契约测试。

背景（真实失效形态）:
    例外到期时间在清单里常写成 "2026-08-24" / "2026-08-24T09:00:00"（无时区），
    而 OPA 的 `time.parse_rfc3339_ns` 只接受带时区偏移的 RFC3339：解析失败时
    规则体未定义 → 例外到期规则**永远不触发**，门禁静默失效且不报错。

    另外 GitOps 同步器把仓库级例外清单里的条目一律按 APPROVED 处理，因此
    清单里留着已过期的条目 = 策略作业必然报违规。

这里锁住三件事：到期时间必须归一化为 RFC3339；仓库级清单不得留已过期条目；
归一化后策略确实能识别过期例外（用 OPA 跑真实策略，本地无 opa 时跳过）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from tools.scripts.hooks.misc_runner import _to_rfc3339

ROOT = Path(__file__).resolve().parent.parent
TRACKED_EXCEPTIONS = ROOT / ".jcode" / "exceptions.yaml"
POLICY_DIR = ROOT / ".jcode" / "policies"


class TestRfc3339Normalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-08-24", "2026-08-24T00:00:00Z"),
            ("2026-08-24T09:00:00", "2026-08-24T09:00:00Z"),
            ("2026-08-24T09:00:00Z", "2026-08-24T09:00:00Z"),
            ("2026-08-24T09:00:00+02:00", "2026-08-24T07:00:00Z"),
        ],
    )
    def test_normalized_to_utc(self, raw: str, expected: str) -> None:
        assert _to_rfc3339(raw) == expected

    def test_empty_stays_empty(self) -> None:
        assert _to_rfc3339(None) == ""
        assert _to_rfc3339("") == ""

    def test_unparsable_kept_verbatim(self) -> None:
        assert _to_rfc3339("not-a-date") == "not-a-date"

    def test_result_is_rfc3339(self) -> None:
        """归一化结果必须能被 RFC3339 解析器接受。"""
        assert datetime.fromisoformat(_to_rfc3339("2026-08-24").replace("Z", "+00:00")).tzinfo is not None


class TestTrackedExceptionsFile:
    def test_no_expired_entries(self) -> None:
        """仓库级清单按 APPROVED 处理 → 已过期条目会让策略作业必然报违规。"""
        data = yaml.safe_load(TRACKED_EXCEPTIONS.read_text(encoding="utf-8")) or {}
        now = datetime.now(timezone.utc)
        expired: list[str] = []
        for entry in data.get("exceptions", []):
            raw_expires = entry.get("expires")
            if not raw_expires:
                continue
            expires = datetime.fromisoformat(str(raw_expires).replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < now:
                expired.append(f"{entry.get('id')}({raw_expires})")
        assert not expired, f"仓库级例外清单里有过期条目: {expired}"


@pytest.mark.skipif(shutil.which("opa") is None, reason="本地无 opa 可执行文件")
class TestPolicyDetectsExpiredException:
    def test_expired_exception_is_reported(self, tmp_path: Path) -> None:
        """归一化后策略必须真的能识别过期例外（否则门禁形同虚设）。"""
        payload = {
            "exceptions": [
                {
                    "id": "expired-1",
                    "status": "approved",
                    "expires_at": "2026-01-01T00:00:00Z",
                    "cve_id": "GHSA-1",
                }
            ]
        }
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            [
                "opa",
                "eval",
                "--data",
                str(POLICY_DIR),
                "--input",
                str(input_file),
                "--format",
                "json",
                "data.jcode.governance",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        violations = json.loads(result.stdout)["result"][0]["expressions"][0]["value"]["violations"]
        rules = {v["rule"] for v in violations}
        assert "exception-expiration" in rules, f"过期例外未被识别: {violations}"
