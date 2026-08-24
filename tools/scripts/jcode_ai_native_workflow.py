"""Master JCode AI-Native Workflow Orchestrator

Integrates real capabilities into a single JCode workflow pipeline:
1. DoR Intent Validation & Multi-LLM Routing
2. Semantic Graph & Architecture Guard
3. Adversarial Review & Scope Guard
4. Telemetry Collection & Cryptographic Audit Ledger
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from tools.scripts._common import get_project_root

if TYPE_CHECKING:
    from audit_attestation import AuditAttestationLedger

# 使无包前缀 import（dor_checker/multi_llm_router 等）与 multi_agent_orch 包可用
sys.path.insert(0, str(get_project_root() / "tools" / "scripts"))
sys.path.insert(0, str(get_project_root() / "tools" / "scripts" / "hooks"))
sys.path.insert(0, str(get_project_root() / "examples" / "multi-agent-orch"))


class JCodeAINativeWorkflow:
    def __init__(self) -> None:
        self.root_dir = get_project_root()
        self.ledger: AuditAttestationLedger | None = None

    def _init_ledger(self, intent: str) -> None:
        from audit_attestation import AuditAttestationLedger

        self.ledger = AuditAttestationLedger(self.root_dir)
        self.ledger.record_trace("PIPELINE_START", {"intent": intent})

    def _print_header(self) -> None:
        print("=" * 70)
        print(" 🚀 JCODE MASTER AI-NATIVE WORKFLOW ORCHESTRATION PIPELINE ")
        print("=" * 70)

    def _step1_dor_routing(self, intent: str) -> bool:
        """Step 1: DoR Intent Validation & Multi-LLM Routing."""
        print("\n[Step 1/4] 🎯 Validating DoR Intent & Multi-LLM Routing...")
        from dor_checker import DoRChecker
        from multi_llm_router import MultiLLMRouter

        dor = DoRChecker(self.root_dir)
        dor_res = dor.evaluate_intent(intent)
        if not dor_res["passed"]:
            print(f"❌ Definition-of-Ready (DoR) gate failed: {dor_res['violations']}")
            if self.ledger:
                self.ledger.record_trace("DOR_FAILED", dor_res)
            return False
        print("✅ DoR Quality Gate Passed (7-point rubric).")

        MultiLLMRouter(self.root_dir).route_task("architecture_design")
        if self.ledger:
            self.ledger.record_trace("STEP_1_COMPLETE", {"dor": dor_res})
        return True

    def _step2_semantic_arch(self) -> None:
        """Step 2: Semantic Graph & Architecture Guard."""
        print("\n[Step 2/4] 🕸️ Building Semantic Graph & Checking Architecture Guard...")
        from architecture_drift_guard import ArchitectureDriftGuard
        from semantic_code_graph import SemanticCodeGraph

        SemanticCodeGraph(self.root_dir).build_graph()
        violations = ArchitectureDriftGuard(self.root_dir).check_layering()
        if violations:
            print(f"⚠️ Architecture Guard warnings: {violations}")
        if self.ledger:
            self.ledger.record_trace("STEP_2_COMPLETE", {"violations": violations})

    def _step3_adversarial_scope(self, intent: str) -> None:
        """Step 3: Adversarial Review & Scope Guard."""
        print("\n[Step 3/4] 🏛️ Running Red-Team Debate & Scope Guard...")
        from multi_agent_orch.orchestration import RedBlueDebateOrchestrator
        from scope_guard import ScopeGuardHook

        RedBlueDebateOrchestrator(intent).run_debate()

        scope_passed, scope_msg = ScopeGuardHook(root_dir=self.root_dir).check_git_diff()
        print(f"🛡️ {scope_msg}")
        if self.ledger:
            self.ledger.record_trace("STEP_3_COMPLETE", {"scope_passed": scope_passed})

    def _step4_telemetry(self) -> None:
        """Step 4: Telemetry Collection & Audit Ledger."""
        print("\n[Step 4/4] 📊 Collecting Telemetry & Recording Audit Ledger...")
        from metrics_telemetry import MetricsTelemetry

        MetricsTelemetry(self.root_dir).collect_metrics()
        if self.ledger:
            self.ledger.record_trace("STEP_4_COMPLETE", {})

    def _print_footer(self) -> None:
        if self.ledger:
            self.ledger.record_trace("PIPELINE_COMPLETE", {"status": "success"})

        print("=" * 70)
        print(" ✅ JCODE MASTER AI-NATIVE WORKFLOW COMPLETED SUCCESSFULLY! ")
        print("=" * 70)

    def run_full_pipeline(self, intent: str = "Feature Delivery via AI-Native SDLC") -> bool:
        self._print_header()
        self._init_ledger(intent)

        if not self._step1_dor_routing(intent):
            return False

        self._step2_semantic_arch()
        self._step3_adversarial_scope(intent)
        self._step4_telemetry()
        self._print_footer()

        return True


if __name__ == "__main__":
    intent_text = sys.argv[1] if len(sys.argv) > 1 else "Implement robust feature with full DoR and TDD compliance"
    workflow = JCodeAINativeWorkflow()
    success = workflow.run_full_pipeline(intent_text)
    sys.exit(0 if success else 1)
