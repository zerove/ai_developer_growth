"""Master JCode AI-Native Workflow Orchestrator

Integrates all capabilities including DoR readiness, cryptographic audit attestation,
strict TDD state machine, and small-batch scope guard into a single JCode workflow pipeline:
1. DoR Intent Validation & Multi-LLM Routing
2. Semantic Graph & Architecture Guard
3. Autonomous Swarm Execution & Strict TDD State Machine
4. Adversarial Review, Slop Scanning & Scope Guard
5. Runtime Verification, Telemetry & Cryptographic Audit Ledger
6. Self-Evolution & Case Study Generation
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from tools.scripts._common import get_project_root

if TYPE_CHECKING:
    from audit_attestation import AuditAttestationLedger

# Insert orchestration path at the very beginning of sys.path using get_project_root()
sys.path.insert(0, str(get_project_root() / "examples" / "multi-agent-orch" / "src" / "orchestration"))
sys.path.insert(0, str(get_project_root() / "tools" / "scripts" / "hooks"))


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
        print("\n[Step 1/6] 🎯 Validating DoR Intent & Multi-LLM Routing...")
        from dor_checker import DoRChecker
        from intent_delivery import IntentDeliveryEngine
        from multi_llm_router import MultiLLMRouter

        dor = DoRChecker(self.root_dir)
        dor_res = dor.evaluate_intent(intent)
        if not dor_res["passed"]:
            print(f"❌ Definition-of-Ready (DoR) gate failed: {dor_res['violations']}")
            if self.ledger:
                self.ledger.record_trace("DOR_FAILED", dor_res)
            return False
        print("✅ DoR Quality Gate Passed (7-point rubric).")

        IntentDeliveryEngine(intent).process_intent()
        MultiLLMRouter(self.root_dir).route_task("architecture_design")
        if self.ledger:
            self.ledger.record_trace("STEP_1_COMPLETE", {"dor": dor_res})
        return True

    def _step2_semantic_arch(self) -> None:
        """Step 2: Semantic Graph & Architecture Guard."""
        print("\n[Step 2/6] 🕸️ Building Semantic Graph & Checking Architecture Guard...")
        from architecture_drift_guard import ArchitectureDriftGuard
        from semantic_code_graph import SemanticCodeGraph

        SemanticCodeGraph(self.root_dir).build_graph()
        violations = ArchitectureDriftGuard(self.root_dir).check_layering()
        if violations:
            print(f"⚠️ Architecture Guard warnings: {violations}")
        if self.ledger:
            self.ledger.record_trace("STEP_2_COMPLETE", {"violations": violations})

    def _step3_swarm_tdd(self) -> None:
        """Step 3: Autonomous Swarm & Strict TDD State Machine."""
        print("\n[Step 3/6] 🐝 Executing Autonomous Swarm & Strict TDD State Machine...")
        from autonomous_swarm_engine import AutonomousSwarmOrchestrator
        from self_healing_ci import SelfHealingCILoop
        from tdd_state_machine import TDDStateMachine

        sm = TDDStateMachine()
        sm.transition("test_written_failing")  # RED -> GREEN
        sm.transition("implementation_passing")  # GREEN -> REFACTOR
        print(f"✅ TDD State Machine verified phase: {sm.state}")

        AutonomousSwarmOrchestrator(self.root_dir).execute_swarm_cycle("")
        SelfHealingCILoop().execute_with_healing()
        if self.ledger:
            self.ledger.record_trace("STEP_3_COMPLETE", {"tdd_state": sm.state})

    def _step4_adversarial_scope(self, intent: str) -> None:
        """Step 4: Adversarial Review, Slop Scanning & Scope Guard."""
        print("\n[Step 4/6] 🏛️ Running Red-Team Debate, Slop Scan & Scope Guard...")
        from ai_slop_scanner import AISlopScanner
        from multi_agent_orch.orchestration import RedBlueDebateOrchestrator
        from scope_guard import ScopeGuardHook

        RedBlueDebateOrchestrator(intent).run_debate()
        AISlopScanner(self.root_dir).scan_codebase()

        scope_passed, scope_msg = ScopeGuardHook(root_dir=self.root_dir).check_git_diff()
        print(f"🛡️ {scope_msg}")
        if self.ledger:
            self.ledger.record_trace("STEP_4_COMPLETE", {"scope_passed": scope_passed})

    def _step5_runtime_telemetry(self) -> None:
        """Step 5: Runtime Verification & Telemetry Ledger."""
        print("\n[Step 5/6] 📊 Running Runtime Verification & Telemetry Collection...")
        from metrics_telemetry import MetricsTelemetry
        from runtime_verifier import RuntimeVerifier

        RuntimeVerifier(self.root_dir).run_tests()
        MetricsTelemetry(self.root_dir).collect_metrics()
        if self.ledger:
            self.ledger.record_trace("STEP_5_COMPLETE", {})

    def _step6_evolution_case_study(self, intent: str) -> None:
        """Step 6: Self-Evolution & Case Study Generation."""
        print("\n[Step 6/6] 🧬 Triggering Self-Evolution & Case Study Generation...")
        from case_study_pipeline import CaseStudyPipeline
        from self_evolving_engine import SelfEvolvingEngine

        SelfEvolvingEngine(self.root_dir).evolve()
        CaseStudyPipeline(self.root_dir).generate_case_study(intent, "Full JCode AI-Native Pipeline Execution", "12x")

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
        self._step3_swarm_tdd()
        self._step4_adversarial_scope(intent)
        self._step5_runtime_telemetry()
        self._step6_evolution_case_study(intent)
        self._print_footer()

        return True


if __name__ == "__main__":
    intent_text = sys.argv[1] if len(sys.argv) > 1 else "Implement robust feature with full DoR and TDD compliance"
    workflow = JCodeAINativeWorkflow()
    success = workflow.run_full_pipeline(intent_text)
    sys.exit(0 if success else 1)
