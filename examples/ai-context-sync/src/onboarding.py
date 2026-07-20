import os
import subprocess
import sys
from typing import List

from .llm_client import LLMClient
from .logger import logger
from .slicer import ContextSlicer


class OnboardingSession:
    """
    Interactive session to guide a new developer through the project architecture.
    """
    def __init__(self, llm_client: LLMClient, root_dir: str = "."):
        self.llm_client = llm_client
        self.slicer = ContextSlicer(root_dir)
        self.root_dir = root_dir
        self.history: list[dict[str, str]] = []
        self.current_focus = "Global"

    def start(self) -> None:
        logger.info("🚀 Welcome to the Project Architecture Tour!")
        logger.info("I will help you understand how this project is structured and how it works.")

        global_context = self.slicer.slice([])
        if not global_context:
            logger.error("❌ Error: No global CONTEXT.md found. Please initialize the project first.")
            return

        initial_prompt = (
            f"You are an expert project mentor. Based on the following global context, "
            f"provide a high-level overview of the project (3-5 bullet points) and "
            f"suggest 3 key areas for the user to explore further.\n\n"
            f"Global Context:\n{global_context}\n\n"
            "Response format: \n"
            "Overview: [your overview]\n"
            "Suggested Areas: [Area 1], [Area 2], [Area 3]"
        )

        response = self.llm_client.generate(initial_prompt)
        logger.info(f"\n{response}")

        # Offer capability radar assessment
        self._offer_capability_assessment()

        while True:
            user_input = input("\nWhat would you like to explore? (Enter an area name, or 'exit' to finish): ")
            if user_input.lower() in ["exit", "quit", "q"]:
                logger.info("👋 Tour completed! You're now ready to dive into the code.")
                break

            self.current_focus = user_input
            relevant_files = self._find_files_for_area(user_input)
            sliced_context = self.slicer.slice(relevant_files)

            explore_prompt = (
                f"You are a project mentor. The user wants to explore the area: '{user_input}'.\n"
                f"Here is the relevant context for this area:\n{sliced_context}\n\n"
                "Please explain how this part of the system works, its key responsibilities, "
                "and how it interacts with other modules. Keep it concise and technical.\n\n"
                "After your explanation, suggest 2-3 next steps or related areas to explore."
            )

            response = self.llm_client.generate(explore_prompt)
            logger.info(f"\n{response}")

    def _offer_capability_assessment(self) -> None:
        """Offer to run the capability radar self-assessment."""
        logger.info("\n" + "=" * 60)
        logger.info("🎯 Before we continue: Would you like to run the AI Era Developer Capability Radar?")
        logger.info("   This 3-minute self-assessment maps your skills across 5 dimensions:")
        logger.info("   1. 问题定义与产品思维  2. 架构决策与系统设计  3. AI 协作与提示工程")
        logger.info("   4. 工程严谨性与质量文化  5. 学习与知识内化")
        logger.info("   Result: Your current level (L0-L4), radar chart, and personalized growth plan.")
        logger.info("=" * 60)

        choice = input("\nRun capability radar now? (y/n, default n): ").strip().lower()
        if choice == 'y':
            self._run_capability_radar()

    def _run_capability_radar(self) -> None:
        """Run the capability radar CLI tool."""
        radar_path = os.path.join(self.root_dir, "examples", "capability-radar")
        if not os.path.exists(radar_path):
            logger.warning("⚠️ Capability radar not found at examples/capability-radar")
            return

        try:
            logger.info("\n🚀 Starting capability radar assessment...")
            # Run the radar in interactive mode
            result = subprocess.run(
                [sys.executable, "-m", "src.cli"],
                cwd=radar_path,
                capture_output=False,  # Show output directly
            )
            if result.returncode == 0:
                logger.info("\n✅ Capability assessment completed!")
                logger.info("💡 Tip: Run it again next quarter to track your growth.")
            else:
                logger.warning("⚠️ Capability radar exited with errors")
        except (OSError, subprocess.CalledProcessError) as e:
            logger.error(f"❌ Failed to run capability radar: {e}")

    def _find_files_for_area(self, area: str) -> List[str]:
        """
        Tries to map a user-provided area name to a set of files/directories.
        """
        # Simple heuristic: search for directories matching the area name
        matches = []
        for root, dirs, files in os.walk(self.root_dir):
            for d in dirs:
                if area.lower() in d.lower():
                    matches.append(os.path.join(root, d, "CONTEXT.md"))
            for f in files:
                if area.lower() in f.lower():
                    matches.append(os.path.join(root, f))

        return matches if matches else ["CONTEXT.md"]
