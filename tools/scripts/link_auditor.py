#!/usr/bin/env python3
import os
import re
import sys


def _build_index(directory: str) -> dict[str, str]:
    """Build a lookup map of all .md files in the vault.

    Keys:
      - basename without .ext (e.g. "MOC" → path/to/MOC.md)
      - relative path without leading ./
      - relative dir path (for directory wikilinks)
    """
    index: dict[str, str] = {}
    for root, _, files in os.walk(directory):
        for f in files:
            if not f.endswith(".md"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, directory)

            name = os.path.splitext(f)[0]
            # First-encountered wins
            if name not in index:
                index[name] = rel

            if rel not in index:
                index[rel] = rel
    return index


def _check_target(target: str, index: dict[str, str], directory: str, file_dir: str) -> bool:
    """Check if a wikilink target resolves to an existing file."""
    target = target.rstrip("\\")

    # Exact path (relative to vault root)
    if target in index:
        return True
    if target + ".md" in index:
        return True

    # Path relative to file's directory
    rel = os.path.relpath(os.path.join(file_dir, target), directory)
    if rel in index:
        return True
    if rel + ".md" in index:
        return True

    # Check absolute path on filesystem (for links outside scanned directory)
    abs_path = os.path.join(file_dir, target)
    if os.path.exists(abs_path):
        return True
    if os.path.exists(abs_path + ".md"):
        return True

    # Basename match (Obsidian searches all subdirs)
    name = os.path.splitext(os.path.basename(target))[0]
    if name in index:
        return True

    # Directory wikilink: [[dirname]] → dirname.md or dirname/README.md
    dir_readme = os.path.join(target, "README.md")
    if dir_readme in index:
        return True

    return False


def find_broken_links(directory: str) -> list[tuple[str, str]]:
    """Scan directory for .md files, extract [[wikilinks]], report broken ones."""
    broken: list[tuple[str, str]] = []
    # Support both | and \| as display text separators
    link_pattern = re.compile(r"\[\[([^\[\]]+?)(?:\\?\|[^\[\]]*)?\]\]")
    index = _build_index(directory)

    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(".md"):
                continue
            file_path = os.path.join(root, file)
            with open(file_path) as f:
                content = f.read()
            for match in link_pattern.finditer(content):
                target_path = match.group(1).strip()
                if target_path.startswith(("http://", "https://", "#")):
                    continue
                if not _check_target(target_path, index, directory, root):
                    broken.append((file_path, match.group(1)))
    return broken


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python link_auditor.py <directory>")
        sys.exit(1)

    broken = find_broken_links(sys.argv[1])
    if broken:
        print("Broken links found:")
        for file, link in broken:
            print(f"  {file}: [[{link}]]")
        sys.exit(1)
    else:
        print("All links are valid.")
        sys.exit(0)
