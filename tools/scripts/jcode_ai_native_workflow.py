"""Master JCode AI-Native Workflow Orchestrator

Integrates all 11 pillars and capabilities into a single seamless JCode workflow pipeline:
1. Intent Ingestion & Routing (Intent Delivery & Multi-LLM Router)
2. Semantic Graph & Architecture Guard (Semantic Graph & Drift Guard)
3. Autonomous Swarm Execution & Self-Healing (Swarm & Self-Healing CI)
4. Adversarial Review & Slop Scanning (Red-Team Debate & Slop Scanner)
5. Runtime Verification & Telemetry (Runtime Verifier & Metrics Telemetry)
6. Self-Evolution & Case Study Generation (Self-Evolving Engine & Case Pipeline)
"""

from __future__ import annotations

import sys

from _common import get_project_root

# Insert orchestration path at the very beginning of sys.path using get_project_root()
sys.path.insert(0, str(get_project_root() / "examples" / "multi-agent-orch" / "src" / "orchestration"))


class JCodeAINativeWorkflow:
    def __init__(self):
        self.root_dir = get_project_root()

    def run_full_pipeline(self, intent: str = "Feature Delivery via AI-Native SDLC") -> bool:
        print("=" * 70)
        print(" 🚀 JCODE MASTER AI-NATIVE WORKFLOW ORCHESTRATION PIPELINE ")
        print("=" * 70)

        # Step 1: Intent & Multi-LLM Routing
        print("\n[Step 1/6] 🎯 Processing Intent & Multi-LLM Routing...")
        from intent_delivery import IntentDeliveryEngine
        from multi_llm_router import MultiLLMRouter
        IntentDeliveryEngine(intent).process_intent()
        MultiLLMRouter(self.root_dir).route_task("architecture_design")

        # Step 2: Semantic Graph & Architecture Guard
        print("\n[Step 2/6] 🕸️ Building Semantic Graph & Checking Architecture Guard...")
        from architecture_drift_guard import ArchitectureDriftGuard
        from semantic_code_graph import SemanticCodeGraph
        SemanticCodeGraph(self.root_dir).build_graph()
        violations = ArchitectureDriftGuard(self.root_dir).check_layering()
        if violations:
            print(f"⚠️ Architecture Guard warnings: {violations}")

        # Step 3: Autonomous Swarm & Self-Healing
        print("\n[Step 3/6] 🐝 Executing Autonomous Swarm & Self-Healing CI...")
        from autonomous_swarm_engine import AutonomousSwarmOrchestrator
        from self_healing_ci import SelfHealingCILoop
        AutonomousSwarmOrchestrator(self.root_dir).execute_swarm_cycle(intent)
        SelfHealingCILoop().execute_with_healing()

        # Step 4: Adversarial Review & Slop Scanning
        print("\n[Step 4/6] 🏛️ Running Red-Team Debate & AI Slop Scan...")
        from adversarial_debate import RedBlueDebateOrchestrator
        from ai_slop_scanner import AISlopScanner
        RedBlueDebateOrchestrator(intent).run_debate()
        AISlopScanner(self.root_dir).scan_codebase()

        # Step 5: Runtime Verification & Telemetry
        print("\n[Step 5/6] 📊 Running Runtime Verification & Telemetry Collection...")
        from metrics_telemetry import MetricsTelemetry
        from runtime_verifier import RuntimeVerifier
        RuntimeVerifier(self.root_dir).run_tests()
        MetricsTelemetry(self.root_dir).collect_metrics()

        # Step 6: Self-Evolution & Case Study Generation
        print("\n[Step 6/6] 🧬 Triggering Self-Evolution & Case Study Generation...")
        from case_study_pipeline import CaseStudyPipeline
        from self_evolving_engine import SelfEvolvingEngine
        SelfEvolvingEngine(self.root_dir).evolve()
        CaseStudyPipeline(self.root_dir).generate_case_study(intent, "Full JCode AI-Native Pipeline Execution", "12x")

        print("=" * 70)
        print(" ✅ JCODE MASTER AI-NATIVE WORKFLOW COMPLETED SUCCESSFULLY! ")
        print("=" * 70)
        return True


if __name__ == "__main__":
    intent_text = sys.argv[1] if len(sys.argv) > 1 else "Complete AI-Native Feature Delivery"
    workflow = JCodeAINativeWorkflow()
    success = workflow.run_full_pipeline(intent_text)
    sys.exit(0 if success else 1)
