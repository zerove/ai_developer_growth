import subprocess
from typing import List, Optional
from unidiff import PatchSet
from .logger import logger

class GitAnalyzer:
    """
    Handles Git interactions to extract and filter changes using professional parsing.
    """
    def __init__(self, ignore_patterns: Optional[List[str]] = None):
        self.ignore_patterns = ignore_patterns or []

    def get_last_commit_diff(self) -> str:
        """
        Gets the raw diff of the last commit.
        """
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"],
                capture_output=True, text=True, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error getting git diff: {e}")
            return ""

    def get_last_commit_message(self) -> str:
        """
        Gets the last commit message.
        """
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error getting commit message: {e}")
            return ""

    def filter_diff(self, diff_text: str) -> str:
        """
        Filters out changes in ignored files using unidiff for robust parsing.
        """
        if not diff_text:
            return ""
            
        try:
            patch = PatchSet(diff_text)
            filtered_diffs = []
            
            for patched_file in patch:
                # Extract the file path from the patched file object
                file_path = patched_file.path
                
                # Check if file should be ignored
                if any(pattern in file_path for pattern in self.ignore_patterns):
                    continue
                
                # Reconstruct the diff for the non-ignored file
                # We convert the patched_file object back to a string
                filtered_diffs.append(str(patched_file))
                
            return "".join(filtered_diffs)
        except (ValueError, IndexError) as e:
            logger.warning(f"Error parsing diff with unidiff: {e}. Falling back to basic filter.")
            return self._basic_filter(diff_text)

    def _basic_filter(self, diff: str) -> str:
        """
        Fallback basic filter if unidiff fails.
        """
        chunks = diff.split("diff --git")
        filtered_chunks = []
        for chunk in chunks:
            if not chunk: continue
            lines = chunk.splitlines()
            if not lines: continue
            parts = lines[0].split()
            if len(parts) >= 2:
                file_path = parts[0].replace("a/", "")
                if any(pattern in file_path for pattern in self.ignore_patterns):
                    continue
            filtered_chunks.append("diff --git" + chunk)
        return "".join(filtered_chunks)

# Test analyzer
if __name__ == "__main__":
    analyzer = GitAnalyzer(ignore_patterns=["package-lock.json", ".gitignore"])
    print("Commit Message:", analyzer.get_last_commit_message())
    print("Filtered Diff:", analyzer.filter_diff(analyzer.get_last_commit_diff()))
