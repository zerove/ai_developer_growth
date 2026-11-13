"""license_review 处置状态流转与周期盘点清单测试。

从 test_supply_license_review.py 拆分以满足测试文件 500 行上限守卫。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tools.scripts.hooks import supply_runner as sr


def make_dep(name: str, ecosystem: str = "pypi", license_: str | None = None):
    from tools.scripts.supply_chain import Dependency

    return Dependency(name=name, version="1.0.0", ecosystem=ecosystem, license=license_)


def _summary_with_attribution(**extra: int) -> dict[str, int]:
    base = {
        "total_dependencies": 2,
        "direct_dependencies": 2,
        "vulnerabilities": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "license_issues": 0,
        "license_review": 2,
        "license_review_unreachable": 1,
        "license_review_unknown": 1,
    }
    base.update(extra)
    return base


class TestLicenseReviewDispositionFlow:
    def test_merge_dispositions_updates_status_and_summary(self, tmp_path: Path) -> None:
        """处置记录应合并到台账项并生成状态/成因摘要。"""
        disp = tmp_path / "disp.json"
        disp.write_text(
            json.dumps(
                {
                    "dispositions": [
                        {
                            "ecosystem": "pypi",
                            "name": "flaky-pkg",
                            "version": "1.0.0",
                            "status": "in_progress",
                            "disposition": "retry metadata / confirm license",
                            "owner": "secops",
                            "note": "network flaky",
                            "ticket": "SEC-1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        summary = {
            "license_review": 1,
            "license_review_items": [
                {
                    "ecosystem": "pypi",
                    "name": "flaky-pkg",
                    "version": "1.0.0",
                    "license": None,
                    "cause": "unreachable",
                    "policy": "review",
                    "message": "REVIEW needed: flaky-pkg@1.0.0 (None)",
                }
            ],
        }
        args = SimpleNamespace(review_dispositions=disp)
        sr._merge_review_dispositions(args, summary)
        item = summary["license_review_items"][0]
        assert item["review_status"] == "in_progress"
        assert item["owner"] == "secops"
        assert item["ticket"] == "SEC-1"
        assert summary["license_review_status_summary"] == {"in_progress": 1}

    def test_write_review_checklist_outputs_markdown(self, tmp_path: Path) -> None:
        """--review-checklist 应输出可用于周期盘点的 Markdown 清单。"""
        checklist = tmp_path / "license-review-checklist.md"
        ledger = tmp_path / "ledger.json"
        args = SimpleNamespace(review_checklist=checklist, review_ledger=ledger, review_dispositions=None)
        summary = _summary_with_attribution()
        summary["license_review_items"] = [
            {
                "ecosystem": "pypi",
                "name": "flaky-pkg",
                "version": "1.0.0",
                "license": None,
                "cause": "unreachable",
                "policy": "review",
                "message": "REVIEW needed: flaky-pkg@1.0.0 (None)",
            }
        ]
        sr._finalize_review_outputs(args, tmp_path, "2026-11-13T00:00:00", summary)

        assert checklist.exists()
        text = checklist.read_text(encoding="utf-8")
        assert "# License Review Checklist" in text
        assert "Pending review items: **1**" in text
        assert "pypi:flaky-pkg@1.0.0" in text
        assert "status: `pending`" in text
        assert "cause: `unreachable`" in text
        data = json.loads(ledger.read_text(encoding="utf-8"))
        assert data["summary"]["status"] == {"pending": 1}
        assert data["items"][0]["review_status"] == "pending"

    def test_checklist_includes_disposition_and_diff(self, tmp_path: Path) -> None:
        """盘点清单应包含处置记录与基线差异摘要。"""
        disp = tmp_path / "disp.json"
        disp.write_text(
            json.dumps(
                {
                    "dispositions": [
                        {
                            "ecosystem": "pypi",
                            "name": "copyleft-pkg",
                            "version": "2.0.0",
                            "status": "waived",
                            "disposition": "legal approved for internal use",
                            "owner": "legal",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        checklist = tmp_path / "checklist.md"
        args = SimpleNamespace(review_checklist=checklist, review_ledger=None, review_dispositions=disp)
        summary = {
            "license_review": 1,
            "license_review_items": [
                {
                    "ecosystem": "pypi",
                    "name": "copyleft-pkg",
                    "version": "2.0.0",
                    "license": "GPL-3.0",
                    "cause": "policy_review",
                    "policy": "review",
                    "message": "REVIEW needed: copyleft-pkg@2.0.0 (GPL-3.0)",
                }
            ],
        }
        diff = {"summary": {"added": 1, "removed": 0, "changed": 0, "unchanged": 0}}
        sr._finalize_review_outputs(args, tmp_path, "2026-11-13T00:00:00", summary, diff)
        text = checklist.read_text(encoding="utf-8")
        assert "status: `waived`" in text
        assert "owner: legal" in text
        assert "## Baseline Diff" in text
        assert "added: 1" in text
