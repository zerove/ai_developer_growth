"""Compiled regex cache for performance optimization.

Avoids re-compiling regex patterns on every file check.

包含:
- LRU 大小限制（防止缓存无界增长）
- 灾难性回溯危险模式检测（防止正则卡死检查进程）
"""

from __future__ import annotations

import importlib
import re
import string
from collections import OrderedDict
from collections.abc import Iterator
from typing import Any

from .logger import logger

# Module-level compiled regex cache (LRU 限制条目数)
_COMPILED_CACHE: OrderedDict[str, re.Pattern[str]] = OrderedDict()
_CACHE_MAX_SIZE = 4096


class RegexSafetyError(ValueError):
    """正则存在灾难性回溯风险时抛出。"""


# re 的解析器在 3.11+ 迁入 re._parser / re._constants (3.10 及更早为顶层模块)。
# 静态分析依赖它把正则拆成语法树, 从而判定"量词包住分支"这类用字符串匹配
# 无法可靠识别的结构。私有 API 且不出现在类型存根中, 故用 importlib 载入
# (直接 from re import _parser 会被 mypy 判 attr-defined, 而抑制指令被禁用)。
# 不可用时退回启发式。
_sre_constants: Any = None
_sre_parse: Any = None
_REPEAT_OPS: frozenset[Any] = frozenset()
try:  # pragma: no cover
    _sre_constants = importlib.import_module("re._constants")
    _sre_parse = importlib.import_module("re._parser")
    _REPEAT_OPS = frozenset({_sre_constants.MAX_REPEAT, _sre_constants.MIN_REPEAT})
except ImportError:
    pass

# 启发式补充网: 静态分析不覆盖的两类形态 ——
#   1. 占有量词 / 字符类上的双量词 ([a-z]*+) ;
#   2. 相邻贪婪量词 (.*.*, 二次方而非指数级)。
# 原先还有一条 "组内含量词" 的嵌套量词正则, 已删除: 静态分析能正确判定嵌套量词,
# 而该正则会把 ([a-z][a-z0-9]*\.)* 这类安全的惯用法误判为危险 (实测 4/467 误报中
# 唯一确凿的误报即来自它)。
_DANGEROUS_PATTERNS = [
    re.compile(r"\[[^\]]*\]\s*[+*]\s*[+*]"),  # [a-z]*+ 字符类双量词
    re.compile(r"(?:\.\*){2,}"),  # .*.* 连续贪婪
]


def _subpatterns(op: Any, av: Any) -> Iterator[Any]:
    """产出该 token 的直接子 SubPattern。"""
    if op in _REPEAT_OPS:
        yield av[2]
    elif op is _sre_constants.BRANCH:
        yield from av[1]
    elif op is _sre_constants.SUBPATTERN:
        yield av[3]


def _token_first_set(data: list[Any], idx: int) -> tuple[int, set[str]] | None:
    """data[idx] 这单个 token 的首字符集。

    对可空量词 ([a-z0-9]*) 同样返回其体部字符集: 歧义与否取决于内层量词能否吃掉
    后继强制字符, 而非该位置的首字符。若对可空量词返回 None,
    ``([a-z][a-z0-9]*\\.)*`` 这类安全惯用法会被保守误判。
    """
    op, av = data[idx]
    if op is _sre_constants.LITERAL:
        return (_FS_POS, {chr(av)})
    if op is _sre_constants.IN:
        return _in_first_set(av)
    if op is _sre_constants.SUBPATTERN:
        return _first_set(av[3])
    if op in _REPEAT_OPS:
        return _first_set(av[2])
    if op is _sre_constants.BRANCH:
        union: set[str] = set()
        for branch in av[1]:
            got = _first_set(branch)
            if got is None:
                return None
            if got[0] == _FS_NEG:
                return (_FS_NEG, set())
            union |= got[1]
        return (_FS_POS, union)
    return None


def _forces_unique_split(data: list[Any], idx: int) -> bool:
    """data[idx] 是无界量词时, 其后是否紧跟一个首字符集与之不相交的强制消费者。

    ``([a-z][a-z0-9]*\\.)*`` 属于此类: 内层 ``*`` 之后强制消费 ``\\.``, 且 ``.``
    不在内层量词的首字符集内 —— 分界线唯一, 回溯无歧义, 故不算危险。
    找不到这样的强制消费者 (如 ``(a*)+``) 则分法指数级, 返回 False。
    """
    inner_first = _token_first_set(data, idx)
    if inner_first is None:
        return False

    # 后继方向: 紧跟一个与内层量词首字符集不相交的强制消费者, 分界即被钉死
    for j in range(idx + 1, len(data)):
        op, av = data[j]
        if op is _sre_constants.AT:
            continue
        if op in _REPEAT_OPS and av[0] == 0:
            continue
        follower = _token_first_set(data, j)
        if follower is None:
            return False
        return _disjoint(follower, inner_first)

    # 前驱方向: 内层量词若**前面**紧跟一个它吃不掉的强制字符, 同样钉死分界。
    # ``(?:\\.\\w+)*`` 属此类 —— 每次迭代必以 `\\.` 开头, 迭代边界由 `.` 的位置
    # 唯一确定, 不存在歧义。只看后继会把它误判为危险, 进而静默禁用依赖它��规则。
    for j in range(idx - 1, -1, -1):
        op, av = data[j]
        if op is _sre_constants.AT:
            continue
        if op in _REPEAT_OPS and av[0] == 0:
            continue
        preceding = _token_first_set(data, j)
        if preceding is None:
            return False
        return _disjoint(preceding, inner_first)

    return False


def _nested_ambiguous_repeat(seq: Any) -> bool:
    """seq 子树内是否存在会造成歧义的嵌套无界量词。"""
    data = seq.data
    for idx, (op, av) in enumerate(data):
        if op in _REPEAT_OPS and av[1] == _sre_constants.MAXREPEAT:
            if not _forces_unique_split(data, idx):
                return True
        for sub in _subpatterns(op, av):
            if _nested_ambiguous_repeat(sub):
                return True
    return False


def _iter_branches(seq: Any) -> Iterator[list[Any]]:
    """逐个产出 seq 子树中的 BRANCH 备选列表。"""
    for op, av in seq.data:
        if op is _sre_constants.BRANCH:
            yield av[1]
            for branch in av[1]:
                yield from _iter_branches(branch)
        elif op in _REPEAT_OPS:
            yield from _iter_branches(av[2])
        elif op is _sre_constants.SUBPATTERN:
            yield from _iter_branches(av[3])


def _literal_of(seq: Any) -> str | None:
    """分支是否为纯字面量串; 含字符类/组/量词时返回 None。"""
    out: list[str] = []
    for op, av in seq.data:
        if op is _sre_constants.LITERAL:
            out.append(chr(av))
        elif op is not _sre_constants.AT:
            return None
    return "".join(out)


_FS_POS = 0  # 首字符集是正向枚举
_FS_NEG = 1  # 首字符集是补集 (chars 为被排除的字符)

# `\w` / `\d` / `\s` 简写展开。**必须支持**: 真实规则里 `\w+` 极常见, 若不展开
# 则 _in_first_set 返回 None, _forces_unique_split 一律保守判危险 —— 实测这会把
# `@\w+(?:\.\w+)*\.ignore` (装饰器命名规则) 误判, 静默禁用整条命名检查。
# 取 ASCII 近似: 对"两个首字符集是否可能相交"而言足够, 且 ASCII 下确定不属于
# 该集合的字符 (如 '.') 在 Unicode 语义下同样不属于。
_CATEGORY_CHARS: dict[str, tuple[int, set[str]]] = {
    "CATEGORY_WORD": (_FS_POS, set(string.ascii_letters + string.digits + "_")),
    "CATEGORY_NOT_WORD": (_FS_NEG, set(string.ascii_letters + string.digits + "_")),
    "CATEGORY_DIGIT": (_FS_POS, set(string.digits)),
    "CATEGORY_NOT_DIGIT": (_FS_NEG, set(string.digits)),
    "CATEGORY_SPACE": (_FS_POS, set(" \t\n\r\f\v")),
    "CATEGORY_NOT_SPACE": (_FS_NEG, set(" \t\n\r\f\v")),
}


def _in_first_set(items: list[Any]) -> tuple[int, set[str]] | None:
    """把 IN 内的 LITERAL/RANGE 解析为首字符集; 含类别简写时返回 None。

    取反类 ([^()]) 必须返回补集而非 None —— 一律返回 None 会把
    ``(?:[^()]|\\([^()]*\\))*`` 这类真实规则误判为危险; 该误判实测直接导致
    ts-no-op-test 规则被静默丢弃 (由 test_validate_language_rules 捕获)。
    """
    out: set[str] = set()
    negated = False
    saw_pos_cat = False
    saw_neg_cat = False
    for op, av in items:
        if op is _sre_constants.LITERAL:
            out.add(chr(av))
        elif op is _sre_constants.RANGE:
            lo, hi = av
            if hi - lo > 256:
                return None
            out.update(chr(c) for c in range(lo, hi + 1))
        elif op is _sre_constants.NEGATE:
            negated = True
        elif op is _sre_constants.CATEGORY:
            # op 是统一的 CATEGORY, 具体类别在 av 里 (如 CATEGORY_WORD)
            key = getattr(av, "name", "")
            if key not in _CATEGORY_CHARS:
                return None
            kind, chars = _CATEGORY_CHARS[key]
            if kind == _FS_POS:
                saw_pos_cat = True
                out |= chars
            else:
                saw_neg_cat = True
                negated = True
                out |= chars
        else:
            return None
    if saw_pos_cat and saw_neg_cat:
        # [\w\W] 之类同时含正反类别, 语义是全集; 无法静态判定, 交由保守路径处理
        return None
    if negated:
        return (_FS_NEG, out) if out else None
    return (_FS_POS, out) if out else None


def _first_set(seq: Any) -> tuple[int, set[str]] | None:
    """分支可能的首字符集; 无法静态确定时返回 None (保守视为会重叠)。

    ``.`` (非 DOTALL) 是除换行外的补集 —— 这一点决定 ``.*\\n`` 的分界是否唯一。
    早先当作"未知"处理, 会把 ``(?:.*\\n){2,}`` 一类安全模式误判为危险。
    """
    for op, av in seq.data:
        if op is _sre_constants.LITERAL:
            return (_FS_POS, {chr(av)})
        if op is _sre_constants.AT:
            continue
        if op is _sre_constants.IN:
            return _in_first_set(av)
        if op is _sre_constants.ANY:
            return (_FS_NEG, {"\n"})
        if op is _sre_constants.ANY_ALL:
            return (_FS_NEG, set())
        if op is _sre_constants.SUBPATTERN:
            return _first_set(av[3])
        if op is _sre_constants.BRANCH:
            union: set[str] = set()
            for branch in av[1]:
                got = _first_set(branch)
                if got is None:
                    return None
                if got[0] == _FS_NEG:
                    return (_FS_NEG, set())
                union |= got[1]
            return (_FS_POS, union)
        return None
    return None


def _disjoint(a: tuple[int, set[str]], b: tuple[int, set[str]]) -> bool:
    """两个首字符集是否不可能相交。

    补集之间无法廉价判定覆盖全集, 一律视为相交 (保守方向)。
    """
    if a[0] == _FS_POS and b[0] == _FS_POS:
        return not a[1] & b[1]
    if a[0] == _FS_POS:
        return a[1] <= b[1]  # 正集完全落在对方的排除集内
    if b[0] == _FS_POS:
        return b[1] <= a[1]
    return False


def _pair_overlaps(left: Any, right: Any) -> bool:
    """两个分支是否会在同一起点上让引擎反复回溯。"""
    lit_left, lit_right = _literal_of(left), _literal_of(right)
    if lit_left is not None and lit_right is not None:
        if lit_left == lit_right:
            return True
        shorter, longer = sorted((lit_left, lit_right), key=len)
        return longer.startswith(shorter)
    first_left, first_right = _first_set(left), _first_set(right)
    if first_left is None or first_right is None:
        return True
    return not _disjoint(first_left, first_right)


def _branches_overlap(branches: list[Any]) -> bool:
    return any(
        _pair_overlaps(branches[i], branches[j]) for i in range(len(branches)) for j in range(i + 1, len(branches))
    )


def _analyze_dangerous(pattern: str) -> bool:
    """静态分析: 判定是否存在指数级回溯结构。

    两类可判定结构:
    1. 嵌套无界量词 —— 无界量词内再套无界量词, 如 ``(a+)+``。
    2. 量词下的重叠分支 —— 无界量词包住 BRANCH 且备选不互斥, 重复分支
       ``(x|x)+`` 与前缀重叠分支 ``(a|aa)+`` 同属此类。
    """
    parsed = _sre_parse.parse(pattern)
    for op, av in parsed.data:
        if op not in _REPEAT_OPS or av[1] != _sre_constants.MAXREPEAT:
            continue
        body = av[2]
        if _nested_ambiguous_repeat(body):
            return True
        if any(len(bs) > 1 and _branches_overlap(bs) for bs in _iter_branches(body)):
            return True
    return False


def _is_dangerous(pattern: str) -> bool:
    """检测可能引起灾难性回溯的正则结构。

    主判据是 re._parser 静态分析 —— 字符串层面的启发式无法识别"量词包住
    重叠分支", 旧实现因此漏掉 (a|aa)+$ / (x|x)+ 这类真实挂死模式。
    启发式仅作为补充网保留 (相邻贪婪量词等静态分析不覆盖的形态)。

    不阻断编译，只标记。
    """
    if _sre_parse is not None:
        try:
            if _analyze_dangerous(pattern):
                return True
        except re.error:
            return False
    simplified = pattern.replace(r"\.", ".").replace(r"\+", "+").replace(r"\*", "*")
    return any(danger.search(simplified) for danger in _DANGEROUS_PATTERNS)


def get_compiled(pattern: str, flags: int = 0) -> re.Pattern[str]:
    """Get or compile a regex pattern with caching (LRU).

    Args:
        pattern: Regex pattern string.
        flags: Regex flags (re.MULTILINE, etc.).

    Returns:
        Compiled regex pattern.

    Raises:
        re.error: If pattern is invalid.
    """
    key = f"{pattern}:{flags}"
    compiled = _COMPILED_CACHE.get(key)
    if compiled is not None:
        # LRU: 移到末尾
        _COMPILED_CACHE.move_to_end(key)
        return compiled

    compiled = re.compile(pattern, flags)
    _COMPILED_CACHE[key] = compiled
    if len(_COMPILED_CACHE) > _CACHE_MAX_SIZE:
        # 淘汰最久未用（队首）
        _COMPILED_CACHE.popitem(last=False)
    return compiled


_WARNED_PATTERNS: set[str] = set()


def guard_pattern(pattern: str, context: str = "") -> bool:
    """判定 pattern 是否危险; 危险时**留痕**并返回 True, 调用方须跳过。

    跳过必须留痕: 静默丢弃一条规则与"该文件检查通过"在报告里无法区分,
    这正是 ADR-074/076/078 一系列的 fail-open 形态。

    该函数在"每文件 × 每规则"的热路径上被调用, 故按 pattern 去重日志,
    避免同一条被跳过的规则刷出上千行。
    """
    if not _is_dangerous(pattern):
        return False
    if pattern not in _WARNED_PATTERNS:
        _WARNED_PATTERNS.add(pattern)
        where = f"[{context}] " if context else ""
        logger.warning(f"跳过疑似灾难性回溯的正则 (该规则本次未被检查): {where}{pattern[:120]}")
    return True


def is_dangerous(pattern: str) -> bool:
    """公开 API: 判断正则是否可能灾难性回溯。

    供调用方在匹配前决策（跳过危险模式或限制重试）。

    Args:
        pattern: 正则表达式字符串。

    Returns:
        True 表示可能危险。
    """
    return get_dangerous(pattern)


def get_dangerous(pattern: str) -> bool:
    """别名: 判断正则是否可能灾难性回溯。

    Args:
        pattern: 正则表达式字符串。

    Returns:
        True 表示可能危险。
    """
    return _is_dangerous(pattern)


def clear_cache() -> None:
    """Clear the compiled regex cache."""
    _COMPILED_CACHE.clear()


def cache_stats() -> dict[str, int]:
    """Get cache statistics."""
    return {
        "cached_patterns": len(_COMPILED_CACHE),
        "memory_estimate_bytes": sum(len(p.pattern.encode()) for p in _COMPILED_CACHE.values()),
    }


def iter_cached() -> Iterator[tuple[str, object]]:
    """迭代缓存中的 (pattern, flags) 键（供测试/诊断）。

    修复 (ADR-028): 当 flags=re.MULTILINE 等 RegexFlag 时, str(flags) 为
    're.MULTILINE' 等非数字字符串, 旧版 int() 抛 ValueError. 改为兼容
    str (失败则返回原值)。返回类型由 int 扩展为 int | str。
    """
    for key in _COMPILED_CACHE:
        pattern, _, flags_str = key.rpartition(":")
        try:
            flags_value: int | str = int(flags_str)
        except ValueError:
            flags_value = flags_str
        yield pattern, flags_value


def scan_dangerous_patterns(patterns: list[str]) -> list[tuple[str, bool]]:
    """批量扫描多个正则，返回 (pattern, is_dangerous) 列表。

    Args:
        patterns: 正则表达式列表。

    Returns:
        每个模式的危险标记列表。
    """
    return [(p, _is_dangerous(p)) for p in patterns]
