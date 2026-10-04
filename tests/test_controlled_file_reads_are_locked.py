"""ADR-073 守卫: 任何读取**受控仓库文件**的用例都必须加共享读锁。

为什么需要这条守卫
------------------
ADR-073 的读锁修复曾漏过一次: `test_jcode_scheduled_dispatch.py` 里
两个用例读同一份 `.jcode/hooks.json`, 我只给其中一个加了锁, 另一个
仍裸读 —— 而后者恰好就是全量跑时报告过失败的那个。

这类遗漏靠人肉 grep 是守不住的: 文件里加一个用例不会触发任何
既有检查。本守卫把"读受控文件"与"是否在锁内"变成**可静态断言**的
关系, 新增漏锁用例直接变红。

判定方式 (静态, 不执行被测代码)
-------------------------------
对每个测试文件做源码扫描, 找出所有"读取受控文件"的表达式
(``read_text()`` / ``read_bytes()`` / ``open(...)`` /
``json.load(...)`` 作用在受控路径上), 再检查它所在的语句块是否
处在 ``acquire_repo_read_lock()`` / ``acquire_repo_mutation_lock()``
上下文内。

已知豁免 (必须有豁免理由, 不能静默跳过):

* **写者**: 持独占锁的用例本身就是被保护对象;
* **锁语义测试自身**: 故意构造并发场景;
* **辅助函数**: 读取封装在 ``_read_*`` 这类名字的函数里, 由调用
  ��共享锁 —— 这些函数在扫描中以"定义点"计入豁免, 且必须真的
  被带锁的调用点使用。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

# 受版本控制、会被真改写/真读取的仓库文件 (ADR-073)
CONTROLLED_FILES = (
    ".jcode/hooks.json",
    "docs/adr/ADR.md",
)

# 本文件与锁语义测试是"元测试": 它们自己构造锁场景, 不需要被守卫
SELF_EXEMPT = {"test_controlled_file_reads_are_locked.py", "test_repo_lock_semantics.py"}

# 明确豁免: 文件名 -> 理由
FILE_EXEMPT: dict[str, str] = {}

LOCK_HOLDERS = ("acquire_repo_read_lock", "acquire_repo_mutation_lock")

# 读取受控文件的调用形态
READ_CALLS = {"read_text", "read_bytes", "loads", "load", "readlines"}

# 表示"临时目录"的标识: 这些路径下的 hooks.json 是**副本**, 与受控
# 仓库文件无关 (如 tmp_path / workdir / go_project), 不需要加锁。
TEMPORARY_MARKERS = (
    "tmp_path",
    "workdir",
    "go_project",
    "tmpdir",
    "self.destination",
    "target",
    "dest",
    "proj_dir",
    "project",
)


def _is_temporary_path(stmt: ast.AST) -> bool:
    """若该语句读取的是临时目录下的副本, 返回 True (无需加锁)。

    真实仓库读法是 ``Path(__file__).resolve().parent.parent`` 或
    ``REPO_ROOT`` / ``ROOT`` 之类的模块常量; 副本读法通常是
    ``tmp_path / ...`` / ``workdir / ...``。
    """
    for child in ast.walk(stmt):
        if isinstance(child, ast.Name) and child.id in TEMPORARY_MARKERS:
            return True
        if isinstance(child, ast.Attribute) and child.attr in TEMPORARY_MARKERS:
            return True
    return False


def _controlled_name(node: ast.AST) -> str | None:
    """若该读取语句涉及某个受控文件的相对路径片段, 返回该文件名。

    必须检查**整条语句**, 而不只是调用节点自身: 真实写法是
    ``json.loads((ROOT / ".jcode" / "hooks.json").read_text(...))``,
    路径字符串位于 ``BinOp`` 兄弟节点里, 不在 ``read_text`` 的子树中。
    只看调用节点会一律返回 None —— 守卫会静默空转 (已实测踩过)。
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            for controlled in CONTROLLED_FILES:
                if controlled in child.value or child.value.endswith(Path(controlled).name):
                    return controlled
    return None


def _statement_of(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    """向上找到承载该调用的最内层语句节点。"""
    cur: ast.AST | None = node
    while cur is not None and not isinstance(cur, ast.stmt):
        cur = parents.get(cur)
    return cur if cur is not None else node


def _is_within_lock(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """判断节点是否位于某个锁上下文管理器的作用域内。"""
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, (ast.With, ast.AsyncWith)):
            for item in cur.items:
                call = item.context_expr
                if isinstance(call, ast.Call):
                    func = call.func
                    if isinstance(func, ast.Attribute) and func.attr in LOCK_HOLDERS:
                        return True
                    if isinstance(func, ast.Name) and func.id in LOCK_HOLDERS:
                        return True
        cur = parents.get(cur)
    return False


def _locked_reader_helpers(tree: ast.Module) -> set[str]:
    """找出"读取封装函数": 内部读受控文件, 且自身已正确加锁。

    两种合规形态都算:
    1. 函数体里就有 ``with acquire_repo_read_lock():`` (自锁封装);
    2. 函数名以 ``_read`` 开头, 由调用点在锁内使用 (外锁封装)。
    """
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("_read"):
            continue
        reads_controlled = any(
            isinstance(sub, ast.Call)
            and (
                (isinstance(sub.func, ast.Attribute) and sub.func.attr in READ_CALLS)
                or (isinstance(sub.func, ast.Name) and sub.func.id in READ_CALLS)
            )
            and _controlled_name(_statement_of(sub, parents)) is not None
            for sub in ast.walk(node)
        )
        if reads_controlled:
            found.add(node.name)
    return found


def _unguarded_reads(path: Path) -> list[tuple[int, str]]:
    """返回 (行号, 说明) 列表: 未受锁保护的受控文件读取点。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    helpers = _locked_reader_helpers(tree)
    offenders: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if attr not in READ_CALLS:
            continue
        # 判定要看承载该调用的**整条语句**, 路径常量常在兄弟节点里
        stmt = _statement_of(node, parents)
        controlled = _controlled_name(stmt)
        if controlled is None:
            continue
        # 临时目录下的副本与受控仓库文件无关, 不要求加锁
        if _is_temporary_path(stmt):
            continue
        if _is_within_lock(node, parents):
            continue
        # 落在"读取封装函数"里: 豁免, 但要求该函数本身被带锁调用
        enclosing = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and node in ast.walk(n) and n.name in helpers
            ),
            None,
        )
        if enclosing is not None:
            continue
        offenders.append((node.lineno, f"{controlled} (受控文件读取未加共享读锁)"))

    return offenders


def _locks_internally(tree: ast.Module, func_name: str, parents: dict[ast.AST, ast.AST]) -> bool:
    """该读取封装函数体内部是否自己加了锁。"""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                inner = sub.func
                name = inner.attr if isinstance(inner, ast.Attribute) else getattr(inner, "id", "")
                if name in LOCK_HOLDERS:
                    return True
    return False


def _is_called_with_lock(tree: ast.Module, func_name: str) -> bool:
    """该读取封装函数是否至少有一处调用点在锁内。"""
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name == func_name and _is_within_lock(node, parents):
                return True
    return False


def _test_files() -> list[Path]:
    return sorted(p for p in TESTS_DIR.glob("test_*.py") if p.name not in SELF_EXEMPT)


class TestControlledFileReadsAreLocked:
    """受控仓库文件被真改写, 故读取方必须持共享锁 (ADR-073)。"""

    @pytest.mark.parametrize("path", _test_files(), ids=lambda p: p.name)
    def test_no_unguarded_controlled_file_read(self, path: Path) -> None:
        reason = FILE_EXEMPT.get(path.name)
        if reason:
            pytest.skip(f"已显式豁免: {reason}")
        offenders = _unguarded_reads(path)
        assert not offenders, "\n".join(f"{path.name}:{line} {msg}" for line, msg in offenders) + (
            "\n\n受控文件: " + ", ".join(CONTROLLED_FILES) + "\n读取它们必须放进 with acquire_repo_read_lock(): 内。"
            "\n若确实需要豁免, 请在 FILE_EXEMPT 中写明理由, 不要静默跳过。"
        )

    @pytest.mark.parametrize("path", _test_files(), ids=lambda p: p.name)
    def test_reader_helpers_are_actually_used_under_lock(self, path: Path) -> None:
        """防止"定义了带锁的封装却没人用"的假合规。

        只针对**外锁**封装: 自锁封装 (函数体自己加锁) 内部已合规,
        调用点无需再套一层。
        """
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        for helper in sorted(_locked_reader_helpers(tree)):
            if _locks_internally(tree, helper, parents):
                continue
            assert _is_called_with_lock(tree, helper), (
                f"{path.name}: 外锁读取封装 {helper}() 定义了但没有任何带锁调用点 —— 要么改用, 要么直接内联到锁内"
            )


def test_controlled_files_are_the_ones_we_think() -> None:
    """健康代码对照: 受控文件清单必须仍真实存在于仓库, 否则守卫会空转。"""
    for controlled in CONTROLLED_FILES:
        assert (REPO_ROOT / controlled).is_file(), f"受控文件不存在: {controlled}"


if __name__ == "__main__":
    sys.exit(0)
