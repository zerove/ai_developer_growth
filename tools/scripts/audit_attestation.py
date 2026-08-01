"""Cryptographic Chained Hash Log Audit Attestation

Provides tamper-evident audit logging for AI-Native workflow executions,
linking each execution trace cryptographically to the previous entry (Chained Hash Log).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from _common import get_project_root


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
                except Exception:
                    pass

        payload = {
            "event_type": event_type,
            "details": details,
            "prev_hash": prev_hash,
        }
        
        serialized = json.dumps(payload, sort_keys=True)
        current_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        
        entry = {**payload, "current_hash": current_hash}
        
        with self.ledger_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        return entry


if __name__ == "__main__":
    ledger = AuditAttestationLedger()
    entry = ledger.record_trace("WORKFLOW_EXECUTION", {"status": "success", "agent": "Sisyphus"})
    print(f"🔒 Recorded chained audit entry: {entry['current_hash']}")
