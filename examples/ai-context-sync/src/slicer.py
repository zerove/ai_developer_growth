import os
from typing import List, Set

from .logger import logger


class ContextSlicer:
    """
    ContextSlicer extracts a minimal, relevant slice of project documentation
    (CONTEXT.md files) based on the files being modified.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir

    def _find_context_files(self, file_path: str) -> List[str]:
        """
        Finds all CONTEXT.md files in the hierarchy leading to the given file.
        """
        contexts = []
        # Start from the root and go down to the file's directory

        # Normalize path
        abs_file_path = os.path.abspath(os.path.join(self.root_dir, file_path))
        abs_root_dir = os.path.abspath(self.root_dir)

        # Get the list of directories from root to the file
        relative_path = os.path.relpath(abs_file_path, abs_root_dir)
        path_parts = relative_path.split(os.sep)

        # Check root first
        root_context = os.path.join(self.root_dir, "CONTEXT.md")
        if os.path.exists(root_context):
            contexts.append(root_context)

        # Check each directory level
        current_path = abs_root_dir
        for part in path_parts[:-1]:  # exclude the filename itself
            current_path = os.path.join(current_path, part)
            context_file = os.path.join(current_path, "CONTEXT.md")
            if os.path.exists(context_file):
                contexts.append(context_file)

        return contexts

    def slice(self, target_files: List[str]) -> str:
        """
        Slices the project context based on the target files.
        """
        if not target_files:
            # Fallback to global context if no files are specified
            root_context = os.path.join(self.root_dir, "CONTEXT.md")
            if os.path.exists(root_context):
                with open(root_context, "r", encoding="utf-8") as f:
                    return f.read()
            return ""

        all_context_files: Set[str] = set()
        for target in target_files:
            all_context_files.update(self._find_context_files(target))

        # Sort files to maintain a consistent order (Root -> Module -> Component)
        sorted_contexts = sorted(list(all_context_files), key=len)

        slices = []
        for ctx_file in sorted_contexts:
            try:
                with open(ctx_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Add a header to distinguish the source of the context
                    rel_path = os.path.relpath(ctx_file, self.root_dir)
                    slices.append(f"--- Context from {rel_path} ---\n{content}")
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error reading context file {ctx_file}: {e}")

        return "\n\n".join(slices)
