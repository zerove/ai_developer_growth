from dataclasses import dataclass, field
from typing import List, Dict
import os

@dataclass
class LanguageProfile:
    name: str
    default_ignore: List[str]
    recommended_prompt_extension: str

# Predefined profiles for common tech stacks
LANGUAGE_PROFILES: Dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        name="Python",
        default_ignore=["__pycache__", "*.pyc", ".venv", "venv", ".pytest_cache", ".mypy_cache", "build/", "dist/"],
        recommended_prompt_extension="Pay special attention to type hints, docstrings, and Pythonic idioms (PEP 8). Ensure that the context updates reflect changes in dependency management (e.g., requirements.txt, pyproject.toml)."
    ),
    "javascript": LanguageProfile(
        name="JavaScript/TypeScript",
        default_ignore=["node_modules", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "dist/", ".next/", ".nuxt/"],
        recommended_prompt_extension="Focus on component hierarchy, state management changes, and TypeScript type definitions. Ensure that changes to package.json are synthesized into high-level dependency updates."
    ),
    "rust": LanguageProfile(
        name="Rust",
        default_ignore=["target/", "Cargo.lock"],
        recommended_prompt_extension="Highlight changes in ownership, lifetimes, and trait implementations. Focus on safety-critical refactors and performance optimizations."
    ),
    "go": LanguageProfile(
        name="Go",
        default_ignore=["vendor/", "go.sum"],
        recommended_prompt_extension="Focus on concurrency patterns (channels, goroutines) and interface implementations. Ensure that the context reflects changes in the project's module structure."
    ),
    "generic": LanguageProfile(
        name="Generic",
        default_ignore=[".git/", ".idea/", ".vscode/", "node_modules/"],
        recommended_prompt_extension="Provide a concise summary of the semantic changes, focusing on the 'what' and 'why' rather than the 'how'."
    )
}

class LanguageDetector:
    """
    Detects the primary language of a project based on signature files.
    """
    SIGNATURES = {
        "python": ["requirements.txt", "pyproject.toml", "setup.py", "manage.py"],
        "javascript": ["package.json", "tsconfig.json", "next.config.js", "tailwind.config.js"],
        "rust": ["Cargo.toml", "Cargo.lock"],
        "go": ["go.mod", "go.sum"],
    }

    @staticmethod
    def detect(root_path: str) -> str:
        for lang, files in LanguageDetector.SIGNATURES.items():
            for file in files:
                if os.path.exists(os.path.join(root_path, file)):
                    return lang
        return "generic"
