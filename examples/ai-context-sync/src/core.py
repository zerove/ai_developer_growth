import os
from typing import List, Optional

from .analyzer import GitAnalyzer
from .auditor import FeedbackManager, SpecAuditor
from .config import AppConfig
from .evolution import EvolutionEngine
from .guard import ArchitectureGuard
from .llm_client import LLMClient
from .logger import logger
from .orchestrator import WorkflowManager
from .profiles import LANGUAGE_PROFILES, LanguageDetector
from .synthesizer import ContextSynthesizer


class AIContextSync:
    """AI-Context-Sync 核心协调器，负责初始化各组件并提供高层 API。

    支持依赖注入：所有组件均可从外部传入，未传入时自动创建默认实例。
    """

    def __init__(
        self,
        config_path: str,
        dry_run: bool = False,
        *,
        llm_client: Optional[LLMClient] = None,
        analyzer: Optional[GitAnalyzer] = None,
        synthesizer: Optional[ContextSynthesizer] = None,
        guard: Optional[ArchitectureGuard] = None,
        auditor: Optional[SpecAuditor] = None,
        feedback: Optional[FeedbackManager] = None,
        evolution: Optional[EvolutionEngine] = None,
        orchestrator: Optional[WorkflowManager] = None,
    ):
        self.config = AppConfig.load(config_path)
        self.dry_run = dry_run

        # Use injected dependencies or create defaults from config
        self.llm_client = llm_client or LLMClient(
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            api_base=self.config.llm.api_base,
        )
        self.analyzer = analyzer or GitAnalyzer(ignore_patterns=self.config.settings.ignore)

        if synthesizer is None:
            lang = LanguageDetector.detect(os.getcwd())
            profile = LANGUAGE_PROFILES.get(lang, LANGUAGE_PROFILES["generic"])
            self.synthesizer = ContextSynthesizer(self.llm_client, profile)
        else:
            self.synthesizer = synthesizer

        self.guard = guard or ArchitectureGuard(self.llm_client, self.config.settings.adr_dir)
        self.auditor = auditor or SpecAuditor(self.llm_client, specs_dir=self.config.settings.specs_dir)
        self.feedback = feedback or FeedbackManager()
        self.evolution = evolution or EvolutionEngine(self.llm_client, self.feedback, self.config.settings.specs_dir)
        self.orchestrator = orchestrator or WorkflowManager(
            self.llm_client,
            self.analyzer,
            self.synthesizer,
            self.guard,
            self.auditor,
            self.evolution,
            config_path=self.config.config_path,
        )

    def _get_context_for_path(self, file_path: str) -> List[str]:
        """Recursively finds all CONTEXT.md files from the file's directory up to the root."""
        contexts: List[str] = []
        current_dir = os.path.dirname(os.path.abspath(file_path))
        root_dir = os.path.abspath(os.getcwd())

        while current_dir.startswith(root_dir):
            context_file = os.path.join(current_dir, self.config.settings.context_file)
            if os.path.exists(context_file):
                with open(context_file, "r", encoding="utf-8") as f:
                    contexts.append(f.read())

            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir

        return contexts[::-1]

    def get_aggregated_context(self, affected_files: List[str]) -> str:
        """Aggregates context from all relevant directory levels for a set of changed files."""
        if not affected_files:
            return ""

        all_contexts: set[str] = set()
        for file in affected_files:
            abs_path = os.path.abspath(file)
            file_contexts = self._get_context_for_path(abs_path)
            all_contexts.update(file_contexts)

        return "\n\n--- Level Divider ---\n\n".join(list(all_contexts))

    def sync(self) -> None:
        logger.info("🚀 Starting AI-Context-Sync...")
        if self.dry_run:
            logger.info("🧪 Dry-run mode enabled. No files will be modified.")

        commit_msg = self.analyzer.get_last_commit_message()
        diff = self.analyzer.get_last_commit_diff()
        filtered_diff = self.analyzer.filter_diff(diff)

        if not filtered_diff:
            logger.info("✨ No relevant changes detected. Skipping sync.")
            return

        context_file = self.config.settings.context_file
        current_context = ""
        if os.path.exists(context_file):
            with open(context_file, "r", encoding="utf-8") as f:
                current_context = f.read()

        logger.info(f"📝 Synthesizing updates for {context_file}...")
        updated_context = self.synthesizer.synthesize_context_update(filtered_diff, commit_msg, current_context)

        if not self.dry_run:
            with open(context_file, "w", encoding="utf-8") as f:
                f.write(updated_context)
            logger.info(f"✅ {context_file} updated.")
        else:
            logger.info(f"🔍 [Dry-run] Would update {context_file} with new content.")

        if "#ADR" in commit_msg:
            logger.info("📌 ADR trigger detected. Generating architectural record...")
            adr_content = self.synthesizer.synthesize_adr(filtered_diff, commit_msg)
            adr_dir = self.config.settings.adr_dir

            if not self.dry_run:
                os.makedirs(adr_dir, exist_ok=True)
                import datetime

                filename = f"ADR-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
                with open(os.path.join(adr_dir, filename), "w", encoding="utf-8") as f:
                    f.write(adr_content)
                logger.info(f"✅ ADR created: {filename}")
            else:
                logger.info(f"🔍 [Dry-run] Would create a new ADR file in {adr_dir}")

    def guard_check(self) -> str:
        logger.info("🛡️ Running Architecture Guard check...")
        commit_msg = self.analyzer.get_last_commit_message()
        diff = self.analyzer.get_last_commit_diff()
        filtered_diff = self.analyzer.filter_diff(diff)

        if not filtered_diff:
            logger.info("✨ No changes to audit.")
            return "No changes to audit."

        report = self.guard.check_drift_json(filtered_diff, commit_msg)
        return str(report)

    def spec_audit(self) -> str:
        logger.info("⚖️ Starting Language Spec Audit...")
        commit_msg = self.analyzer.get_last_commit_message()
        diff = self.analyzer.get_last_commit_diff()
        filtered_diff = self.analyzer.filter_diff(diff)

        if not filtered_diff:
            logger.info("✨ No changes to audit.")
            return "No changes to audit."

        violations = self.auditor.audit(filtered_diff, commit_msg)

        if not violations:
            return "✅ All changes comply with specifications."

        for v in violations:
            self.feedback.save_violation(v)

        report = [f"Found {len(violations)} violation(s):"]
        for i, v in enumerate(violations, 1):
            report.append(f"{i}. [{v.severity}] {v.rule_id}: {v.message}")

        return "\n".join(report)
