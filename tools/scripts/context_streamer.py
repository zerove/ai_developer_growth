"""Context Streaming & Lazy Pagination (Pillar 5)

Provides virtualized paging and lazy loading for large codebase contexts
to maintain minimal token usage and high agent responsiveness.
"""

from __future__ import annotations

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import sys
from pathlib import Path

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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
