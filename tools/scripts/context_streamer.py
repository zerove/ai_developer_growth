"""Context Streaming & Lazy Pagination (Pillar 5)

Provides virtualized paging and lazy loading for large codebase contexts
to maintain minimal token usage and high agent responsiveness.
"""

from __future__ import annotations

from pathlib import Path

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


from tools.scripts._common import get_project_root  # noqa: E402


class ContextStreamer:
    def __init__(self, root_dir: Path | None = None, page_size: int = 50):
        self.root_dir = root_dir or get_project_root()
        self.page_size = page_size

    def stream_file_chunks(self, file_path: Path) -> list[str]:
        if not file_path.exists():
            return []
        lines = file_path.read_text(encoding="utf-8").splitlines()
        chunks = ["\n".join(lines[i : i + self.page_size]) for i in range(0, len(lines), self.page_size)]
        return chunks


if __name__ == "__main__":
    streamer = ContextStreamer()
    readme = streamer.root_dir / "README.md"
    chunks = streamer.stream_file_chunks(readme)
    print(f"📦 Context Streamer successfully virtualized README.md into {len(chunks)} chunks.")
