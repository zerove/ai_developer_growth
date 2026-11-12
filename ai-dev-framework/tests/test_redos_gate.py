"""ai_dev_framework 的 ReDoS 闸门回归测试。

对应缺陷: `scan.py` 会拿规则文件里的正则去匹配任意长度的源码, 而规则文件在
下游仓库中是 **PR 可控面**。恶意规则如 `(x|xx)+$` 会让扫描在 CI 上指数级挂死。

`ai-dev-framework` 以 `pip install` 分发, 不能依赖主仓的 regex_cache, 故自带
`redos.py` (由脚本从主仓原样提取)。本测试同时锁定两件事:

1. 提取无损 —— 与主仓判定在真实规则语料上零分歧
2. 闸门有效 —— 危险规则被跳过且**留痕**, 不静默丢弃 (否则又是一次 fail-open)
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_dev_framework.redos import is_dangerous  # noqa: E402

DANGEROUS = [
    r"(x|xx)+$",
    r"(a|aa)+$",
    r"(a+)+$",
    r"(a*)*$",
    r"(\d+|\w)+",
    r"(a|a)*",
    r"(a|aa)*b",
]

SAFE = [
    r"\b\w+\b",
    r"^[a-z][a-z0-9_]*\.rs$",
    r"(foo|bar)+",
    r"^\s*$",
    r"(GET|POST|PUT)",
    r"[0-9]{3}-[0-9]{4}",
    r"\d{4}-\d{2}-\d{2}",
    r"(?:abc)+",
    r"(.*a){10}",
]


class TestDetector:
    @pytest.mark.parametrize("pattern", DANGEROUS)
    def test_flags_catastrophic(self, pattern: str) -> None:
        assert is_dangerous(pattern) is True, f"漏判: {pattern}"

    @pytest.mark.parametrize("pattern", SAFE)
    def test_does_not_flag_safe(self, pattern: str) -> None:
        assert is_dangerous(pattern) is False, f"误判: {pattern}"

    def test_never_raises_on_junk(self) -> None:
        for junk in ["(", "[a-", "*", "\\", "(?P<n>a)(?P<n>b)", ""]:
            assert isinstance(is_dangerous(junk), bool)

    def test_repeat_ops_initialized_when_parser_available(self) -> None:
        """fail-open 守护: _sre_parse 可用时 _REPEAT_OPS 必须非空且等于期望值。

        初始化块历史上曾重复一份, 且第二份前置 `_REPEAT_OPS = frozenset()`
        重置 —— 清理时若只删 try/except 留下重置, 静态分析会恒判"不危险"
        而闸门形同虚设 (fail-open)。本用例锁定唯一初始化序列的正确性。
        """
        from ai_dev_framework import redos

        if redos._sre_parse is None:
            pytest.skip("解析器不可用 (本机 re 结构差异)")
        assert redos._REPEAT_OPS, "_REPEAT_OPS 被重置为空 —— ReDoS 分析器已失明 (fail-open)"
        expected = frozenset({redos._sre_constants.MAX_REPEAT, redos._sre_constants.MIN_REPEAT})
        assert redos._REPEAT_OPS == expected

    def test_matches_parent_repo_analyzer(self) -> None:
        """提取无损: 两份实现对真实规则语料的判定必须完全一致。

        任何分歧都意味着同步已失效 —— 此时应以主仓为准重新生成本包文件。
        """
        yaml = pytest.importorskip("yaml")
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root))
        try:
            from tools.scripts.rules_engine.regex_cache import _is_dangerous as parent
        except ImportError:
            pytest.skip("主仓 regex_cache 不可达 (分发场景)")

        patterns: set[str] = set()

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ("pattern", "exclude_pattern") and isinstance(v, str):
                        patterns.add(v)
                    else:
                        walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        for yml in repo_root.rglob("*.y*ml"):
            if any(s in yml.parts for s in {".git", "node_modules", ".venv"}):
                continue
            try:
                walk(yaml.safe_load(yml.read_text(encoding="utf-8")))
            except Exception:
                continue

        assert len(patterns) > 100, "语料采样异常, 本用例失去意义"
        drift = [p for p in patterns if parent(p) is not is_dangerous(p)]
        assert not drift, (
            f"与主仓判定分歧 {len(drift)} 条, 同步已失效: {drift[:5]}。应重新从主仓 regex_cache.py 提取本文件。"
        )


class TestScannerGate:
    """端到端: 恶意**项目规则**不得让扫描挂死, 且跳过必须留痕。"""

    def _scan_with_project_rule(self, pattern: str) -> tuple[float, object]:
        from ai_dev_framework import scan as scan_mod

        tmp = Path(tempfile.mkdtemp())
        rules_dir = tmp / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text(
            f"anti_patterns:\n  - id: evil\n    pattern: '{pattern}'\n    message: pwn\n    severity: warning\n",
            encoding="utf-8",
        )
        original = scan_mod._PROJECT_LANGUAGES
        scan_mod._PROJECT_LANGUAGES = tmp
        try:
            target = tmp / "a.py"
            target.write_text("x = '" + "x" * 40 + "'\n", encoding="utf-8")
            # 用 process_time 而非 perf_counter：全量 `-n auto` 并发下墙钟时间
            # 会被 CPU 争抢放大（实测安全规则被拖到 6.0s 而误报），而灾难性
            # 回溯消耗的是真实 CPU，阈值语义不受影响。
            start = time.process_time()
            result = scan_mod.scan_file(target)
            return time.process_time() - start, result
        finally:
            scan_mod._PROJECT_LANGUAGES = original

    def test_malicious_rule_is_skipped_and_logged(self) -> None:
        elapsed, result = self._scan_with_project_rule(r"(x|xx)+$")

        assert elapsed < 2.0, f"疑似灾难性回溯未阻断: {elapsed:.1f}s"
        assert "evil" not in [i.rule_id for i in result.issues], "危险规则未被跳过"
        assert any("evil" in w for w in result.warnings), "跳过后未留痕 —— 静默丢弃规则同样是 fail-open"

    def test_safe_project_rule_still_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """反向约束: 闸门不得把正常规则一起拦掉。"""
        from ai_dev_framework import scan as scan_mod

        # ADG_HOME 指向空目录: 隔离用户级内置规则。
        # 否则在装过 `adg bootstrap` 的机器上, 断言会被内置 common-todo 命中
        # 而"假通过"——项目规则本身是否生效完全没被验证; 反过来在干净的
        # CI 机器上没有内置规则, 就退化成"扫描零结果"。
        monkeypatch.setattr(scan_mod, "_RULES_HOME", tmp_path / "adg-home")

        tmp = tmp_path / "proj"
        rules_dir = tmp / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        # 注意不能用 r"..." 包住 \n: 原始字符串里的 \n 是**两个字符**,
        # 写出来的 YAML 会是一整行(含字面量反斜杠 n) → 解析失败 → 规则为空,
        # 测试于是变成"断言空结果里有 issue", 必失败。
        (rules_dir / "anti_patterns.yml").write_text(
            "anti_patterns:\n  - id: todo\n    pattern: '\\bTODO\\b'\n    message: m\n    severity: warning\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(scan_mod, "_PROJECT_LANGUAGES", tmp)

        target = tmp / "a.py"
        # 不能用纯注释行: scan.py 会跳过整行只有注释的内容
        target.write_text("x = 1  # TODO: fix\n", encoding="utf-8")
        result = scan_mod.scan_file(target)

        # 闸门**没有**把它当危险规则跳过 —— 那才是"误伤"。
        assert not any("todo" in w for w in result.warnings), f"正常规则被 ReDoS 闸门误伤: {result.warnings}"
        # 命中必须来自项目规则本身(内置规则已隔离), 才算真正验证了"没误伤"。
        assert [i.rule_id for i in result.issues] == ["todo"], f"项目规则未生效: {result.issues}"
