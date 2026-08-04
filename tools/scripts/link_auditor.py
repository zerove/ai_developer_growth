#!/usr/bin/env python3
import argparse
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


def _strip_code_blocks(content: str) -> str:
    """Remove content inside fenced code blocks to avoid false positives."""
    # Remove ``` blocks (```...```)
    content = re.sub(r"```[\s\S]*?```", "", content)
    # Remove ~~~ blocks (~~~...~~~)
    content = re.sub(r"~~~[\s\S]*?~~~", "", content)
    # Remove inline code (`...`)
    content = re.sub(r"`[^`]+`", "", content)
    return content


def find_broken_links(directory: str) -> list[tuple[str, str]]:
    """Scan directory for .md files, extract [[wikilinks]], report broken ones."""
    broken: list[tuple[str, str]] = []
    # Support both | and \| as display text separators
    link_pattern = re.compile(r"\[\[([^\[\]]+?)(?:\\?\|[^\[\]]*)?\]\]")
    index = _build_index(directory)

    # Skip template directories and files with template-like patterns
    skip_dirs = {".github/PULL_REQUEST_TEMPLATE"}
    placeholder_pattern = re.compile(r"^[\{\.\\/]+|[\{\.]{2,}")

    for root, _, files in os.walk(directory):
        # Skip template directories
        rel_root = os.path.relpath(root, directory)
        if any(rel_root.startswith(skip) for skip in skip_dirs):
            continue

        for file in files:
            if not file.endswith(".md"):
                continue
            file_path = os.path.join(root, file)
            with open(file_path) as f:
                content = f.read()
            # Strip code blocks to avoid false positives (e.g. TOML [[rules]])
            cleaned = _strip_code_blocks(content)
            for match in link_pattern.finditer(cleaned):
                target_path = match.group(1).strip()
                # Skip external links, anchors, and template placeholders
                if target_path.startswith(("http://", "https://", "#")):
                    continue
                if placeholder_pattern.match(target_path):
                    continue
                if not _check_target(target_path, index, directory, root):
                    broken.append((file_path, match.group(1)))
    return broken


def find_broken_links_with_index(directory: str, index: dict[str, str]) -> list[tuple[str, str]]:
    """Like find_broken_links, but accepts an externally-built index.

    Used by check_all_links() to scan subdirectories with a project-wide
    index so cross-directory wikilinks resolve correctly.
    """
    broken: list[tuple[str, str]] = []
    link_pattern = re.compile(r"\[\[([^\[\]]+?)(?:\\?\|[^\[\]]*)?\]\]")
    skip_dirs = {".github/PULL_REQUEST_TEMPLATE"}
    placeholder_pattern = re.compile(r"^[\{\.\\/]+|[\{\.]{2,}")

    for root, _, files in os.walk(directory):
        rel_root = os.path.relpath(root, directory)
        if any(rel_root.startswith(skip) for skip in skip_dirs):
            continue

        for file in files:
            if not file.endswith(".md"):
                continue
            file_path = os.path.join(root, file)
            with open(file_path) as f:
                content = f.read()
            cleaned = _strip_code_blocks(content)
            for match in link_pattern.finditer(cleaned):
                target_path = match.group(1).strip()
                if target_path.startswith(("http://", "https://", "#")):
                    continue
                if placeholder_pattern.match(target_path):
                    continue
                if not _check_target(target_path, index, directory, root):
                    broken.append((file_path, match.group(1)))
    return broken


def check_all_links() -> bool:
    """Check all markdown files in the project for broken links."""
    # Build a single global index from the project root so cross-directory
    # wikilinks (e.g. examples/ referencing docs/) resolve correctly.
    project_root = "."
    global_index = _build_index(project_root)

    dirs_to_check = ["docs", ".", "case-studies", "examples"]
    all_broken = []

    for d in dirs_to_check:
        if os.path.exists(d):
            broken = find_broken_links_with_index(d, global_index)
            for file, link in broken:
                all_broken.append((file, link))

    if all_broken:
        print("Broken links found:")
        for file, link in all_broken:
            print(f"  {file}: [[{link}]]")
        return False
    else:
        print("All links are valid.")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit markdown links")
    parser.add_argument("directory", nargs="?", help="Directory to scan")
    parser.add_argument("--check-all", action="store_true", help="Check all project directories")
    parser.add_argument("--fail-on-broken", action="store_true", help="Exit with error code if broken links found")
    parser.add_argument("--internal-only", action="store_true", help="Only check internal links (skip external)")
    args = parser.parse_args()

    if args.check_all:
        success = check_all_links()
    elif args.directory:
        broken = find_broken_links(args.directory)
        if broken:
            print("Broken links found:")
            for file, link in broken:
                print(f"  {file}: [[{link}]]")
            success = False
        else:
            print("All links are valid.")
            success = True
    else:
        print("Usage: python link_auditor.py <directory> [--check-all] [--fail-on-broken]")
        sys.exit(1)

    if args.fail_on_broken and not success:
        sys.exit(1)
    elif not success:
        sys.exit(1)
    else:
        sys.exit(0)
