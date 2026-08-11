#!/usr/bin/env python3
"""Session Memory Vectorizer: extracts debug history and architectural insights into a searchable local memory store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def vectorize_sessions(sessions_dir: Path, output_index: Path) -> dict[str, Any]:
    """Scan session logs/notes and build an institutional memory index."""
    index: dict[str, Any] = {"entries": []}
    if not sessions_dir.exists():
        return index

    for note_file in sessions_dir.rglob("*.md"):
        try:
            content = note_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            title = lines[0].lstrip("# ").strip() if lines else note_file.name
            index["entries"].append(
                {
                    "source": str(note_file),
                    "title": title,
                    "length": len(content),
                    "keywords": [w.lower() for w in title.split() if len(w) > 3],
                }
            )
        except OSError:
            continue

    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_index.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return index


def search_memory(output_index: Path, query: str) -> list[dict[str, Any]]:
    """Search institutional memory index."""
    if not output_index.exists():
        return []
    try:
        data = json.loads(output_index.read_text(encoding="utf-8"))
        q_lower = query.lower()
        results = []
        for entry in data.get("entries", []):
            if q_lower in entry["title"].lower() or any(q_lower in kw for kw in entry.get("keywords", [])):
                results.append(entry)
        return results
    except json.JSONDecodeError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Session Memory Vectorizer")
    parser.add_argument("--dir", type=Path, default=Path("docs"), help="Directory to index")
    parser.add_argument("--index", type=Path, default=Path(".jcode/memory/memory_index.json"), help="Output index file")
    parser.add_argument("--search", type=str, help="Search query against memory")
    args = parser.parse_args()

    if args.search:
        res = search_memory(args.index, args.search)
        print(f"🔍 Found {len(res)} memory matches for '{args.search}':")
        for r in res:
            print(f"  - [{r['title']}] ({r['source']})")
    else:
        index = vectorize_sessions(args.dir, args.index)
        print(f"✅ Indexed {len(index['entries'])} items into institutional memory at {args.index}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
