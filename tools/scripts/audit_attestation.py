"""Cryptographic Chained Hash Log Audit Attestation

Provides tamper-evident audit logging for AI-Native workflow executions,
linking each execution trace cryptographically to the previous entry (Chained Hash Log).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.scripts._common import get_project_root


class AuditAttestationLedger:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.ledger_file = self.root_dir / ".quality-trends" / "audit_ledger.jsonl"

    def record_trace(self, event_type: str, details: dict[str, Any]) -> dict[str, Any]:
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)

        # Read last hash
        prev_hash = "0" * 64
        if self.ledger_file.exists():
            lines = self.ledger_file.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    last_entry = json.loads(lines[-1])
                    prev_hash = last_entry.get("current_hash", prev_hash)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).debug(f"Failed to parse last ledger entry: {e}")

        payload = {
            "event_type": event_type,
            "details": details,
            "prev_hash": prev_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        serialized = json.dumps(payload, sort_keys=True)
        current_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        entry = {**payload, "current_hash": current_hash}

        with self.ledger_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def generate_report(self) -> str:
        """Generate a human-readable audit report."""
        if not self.ledger_file.exists():
            return "📋 Audit Ledger: No entries recorded yet."

        lines = self.ledger_file.read_text(encoding="utf-8").splitlines()
        entries = [json.loads(line) for line in lines if line.strip()]

        report = ["=" * 60, " 🔒 AUDIT ATTESTATION REPORT ", "=" * 60]
        report.append(f"\nTotal Entries: {len(entries)}")
        report.append(f"Ledger File: {self.ledger_file}")
        report.append("\n📜 Recent Entries:")

        for entry in entries[-10:]:
            event_type = entry.get("event_type", "UNKNOWN")
            current_hash = entry.get("current_hash", "")[:16]
            prev_hash = entry.get("prev_hash", "")[:16]
            details = entry.get("details", {})
            report.append(f"  • {event_type} | hash={current_hash}... | prev={prev_hash}...")
            if isinstance(details, dict):
                for k, v in details.items():
                    report.append(f"    - {k}: {v}")

        # Verify chain integrity
        valid = True
        prev_hash = "0" * 64
        for entry in entries:
            payload = {
                "event_type": entry.get("event_type"),
                "details": entry.get("details"),
                "prev_hash": entry.get("prev_hash"),
            }
            serialized = json.dumps(payload, sort_keys=True)
            current_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            if current_hash != entry.get("current_hash"):
                valid = False
                break
            prev_hash = current_hash

        report.append(f"\n✅ Chain Integrity: {'VALID' if valid else 'BROKEN'}")
        report.append("=" * 60)

        return "\n".join(report)


if __name__ == "__main__":
    ledger = AuditAttestationLedger()
    entry = ledger.record_trace("WORKFLOW_EXECUTION", {"status": "success", "agent": "Sisyphus"})
    print(f"🔒 Recorded chained audit entry: {entry['current_hash']}")
    print(ledger.generate_report())
