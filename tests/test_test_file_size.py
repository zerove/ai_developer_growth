"""测试文件大小门禁：单个测试文件不得超过 500 行。"""

from pathlib import Path

MAX_LINES = 500
TESTS_DIR = Path(__file__).parent


def test_test_files_do_not_exceed_line_limit() -> None:
    oversized: dict[str, int] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            oversized[path.name] = line_count
    assert not oversized, f"测试文件超过 {MAX_LINES} 行: {oversized}"
