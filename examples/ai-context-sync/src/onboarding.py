import os
from typing import List, Optional
from .llm_client import LLMClient
from .slicer import ContextSlicer
from .logger import logger

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
