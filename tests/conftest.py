"""Shared test configuration for ai_developer_growth tests.

Contains project-wide fixtures and FutureWarning suppression for tree-sitter.

测试隔离准则:
- 所有文件操作使用 `temp_dir` fixture 而非写工作目录
- 所有 mock 使用 `unittest.mock` 而非猴子补丁
- 测试不应依赖执行顺序
"""

import sys
import tempfile
import warnings
from pathlib import Path

import pytest

# 注入项目根到 sys.path:
# 裸 `pytest` 可执行文件不会像 `python -m pytest` 那样自动把 cwd 加入 sys.path,
# 导致依赖 `import tools` 的测试模块收集失败 (ModuleNotFoundError: No module named 'tools').
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Suppress tree-sitter deprecation warnings project-wide
warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")


@pytest.fixture(autouse=True)
def _isolate_quality_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """将质量门禁基线隔离到临时目录，防止测试污染真实项目基线。"""
    monkeypatch.setenv("JCODE_QUALITY_BASELINE", str(tmp_path / ".jcode" / "baseline.json"))


@pytest.fixture
def temp_dir():
    """Create a temporary directory and clean up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_markdown():
    """Sample markdown content for testing."""
    return """# Test Document

## Section 1

This is a test document with some content.

## Section 2

More content here.
"""


@pytest.fixture
def sample_case_study():
    """Sample case study content for testing."""
    return """# Test Case Study

## 背景

Test background.

## 过程

Test process.

## 对比

| 指标 | Before | After |
|------|--------|-------|
| 效率 | 1x | 5x |

## 洞察

Test insights.

## 适用场景

Test scenarios.
"""
