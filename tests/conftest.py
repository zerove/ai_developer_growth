"""Shared test configuration for ai_developer_growth tests.

Contains project-wide fixtures and FutureWarning suppression for tree-sitter.

测试隔离准则:
- 所有文件操作使用 `temp_dir` fixture 而非写工作目录
- 所有 mock 使用 `unittest.mock` 而非猴子补丁
- 测试不应依赖执行顺序
- **确需改写受版本控制的仓库文件**时(被测代码硬编码了仓库相对
  路径, 无法注入), 必须使用 `repo_mutating_file` fixture 串行化,
  见该 fixture 文档。
"""

import contextlib
import fcntl
import os
import sys
import tempfile
import warnings
from collections.abc import Iterator
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


# 跨进程互斥锁文件名。放系统临时目录, 避免在仓库里留下未跟踪文件
# 污染 git status —— 本仓库的收口流程会以 git status 作为门禁之一。
REPO_MUTATION_LOCK = "adg-repo-mutation.lock"


def _lock_path() -> Path:
    # 允许测试/子进程把锁指向独立路径, 避免自身用例争用生产全局锁。
    override = os.environ.get("ADG_TEST_LOCK_PATH")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / REPO_MUTATION_LOCK


@contextlib.contextmanager
def acquire_repo_mutation_lock() -> Iterator[None]:
    """获取"改写受控仓库文件"的**独占**跨进程锁.

    供 **unittest.TestCase** 风格的用例使用 —— 那类用例无法注入
    pytest fixture, 故不能直接用 ``repo_mutating_file`` fixture。

    为何需要: 见 ``repo_mutating_file`` fixture 的文档。核心事实是
    pytest-xdist 下多个 worker 是独立**进程**, 彼此看不到对方的
    ``addCleanup``, 于是一个 worker 的还原会把另一个 worker 正在
    用的 canary 抹掉, 或反之。实测 ``-n 8``: 9 failed 且受控配置
    里残留 canary。
    """
    path = _lock_path()
    path.touch(exist_ok=True)
    with path.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def acquire_repo_read_lock() -> Iterator[None]:
    """获取"读取受控仓库文件"的**共享**跨进程锁.

    为何需要: 只锁写者不够。同一份 ``.jcode/hooks.json`` 既被
    ``FailOpenDetectorTest`` 真改写, 也被 ``SubcommandOptionTest`` /
    ``InterpreterConsistencyTest`` 只读地跑真实脚本校验。只锁写者
    时, 读者会在写者持有 canary 的窗口里读到**临时内容**而误报失败。

    实测证据: 仅给写类加锁后 ``-n 8`` 仍剩 2~3 failed, 且失败用例
    全部落在两个只读类上 (``test_runs_from_unrelated_cwd`` /
    ``test_real_config_has_subcommand_hook_and_passes``) —— 正是
    读到了写者窗口内的 canary。

    用 ``LOCK_SH`` 而非也用 ``LOCK_EX``: 多个读者之间无写冲突, 可
    并行, 不会把整个文件退化成串行。读者之间真正的隐患是"读到写者
    的中间态", 而写者持的是 ``LOCK_EX``, 共享锁天然被它挡住。
    """
    path = _lock_path()
    path.touch(exist_ok=True)
    with path.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@pytest.fixture
def repo_mutating_file() -> Iterator[None]:
    """序列化"改写受版本控制的仓库文件"的用例 (跨进程互斥锁).

    为何需要: 少数被测代码把仓库相对路径写死了 —— 例如
    ``check_hooks_json_integrity.sh`` 内嵌 ``HOOKS_JSON =
    ".jcode/hooks.json"``, 无法注入临时路径。这类用例只能真去改
    仓库里的 ``.jcode/hooks.json`` / ``docs/adr/ADR.md``。

    ``addCleanup`` 本身是可靠的, 但 pytest-xdist 下多个 worker
    **进程**并行, 彼此看不到对方的 cleanup。实测 (``-n 8``):
    9 failed, 且跑完后 ``ZZZ-canary`` 留在受控的 ``hooks.json``
    里 —— 此时提交就会把 canary 写进真实 hook 配置。

    故用 ``fcntl.flock`` 跨进程加锁: 同一时刻只允许一个 worker
    改写仓库文件。

    为何用 flock 而非 ``pytest-xdist`` 的 ``loadgroup``/``xdist_group``:
    后者只在**同一 worker 内**分组, 对"多个 worker 同时改同一
    文件"无效。flock 作用于文件本身, 与调度方式无关, ``-n 4`` 与
    ``-n 16`` 同样安全。

    本 fixture 只提供**互斥**, 不负责备份/还原 —— 备份还原仍由
    各用例自己的 ``addCleanup`` 负责, 职责不混。
    """
    with acquire_repo_mutation_lock():
        yield


@pytest.fixture
def restore_on_failure(path: Path) -> Iterator[Path]:
    """把受控文件的内容快照下来, 用例结束后无条件还原.

    与 ``repo_mutating_file`` 配套使用。区别: 后者解决"多个进程
    同时改", 本 fixture 解决"用例中途失败时文件被留在坏状态"。
    """
    original = path.read_bytes()
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            current = path.read_bytes()
            if current != original:
                path.write_bytes(original)
                os.utime(path, None)


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
