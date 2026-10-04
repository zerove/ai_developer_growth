"""规则磁盘缓存的跨进程并发安全 (ADR-075).

缺陷 (本轮实测复现, 非推断): ``rule_loader`` 的磁盘缓存是**读-改-写**
事务, 原先既无跨进程锁、又用 ``write_text`` 直接覆盖::

    disk_cache = _load_disk_cache()   # 读
    ...
    disk_cache[cache_key] = result
    _save_disk_cache(disk_cache)      # 非原子整体覆盖写

两个并发写者各自基于陈旧快照覆盖写, 后写者静默抹掉前写者的 key; 而
``write_text`` 先把文件截断为 0 字节再逐字写入, 并发读者会读到半截 JSON,
且被 ``_load_disk_cache`` 的 ``except json.JSONDecodeError`` 吞掉返回空
dict —— 缓存静默失效。

本文件锁定的两条不变量 (各有独立变异验证, 见 ADR-075):
    1. **不丢更新**: N 个进程并发 ``load_rules()`` 后, 磁盘上必须留下全部
       N 个语言 key。
    2. **不会读到半截文件**: 写盘进行中并发读, 只能读到"完整的旧内容"或
       "完整的新内容", 绝不能读到损坏 JSON。

不变量 2 是本文件的真正价值: 第一版测试只在子进程**退出前**读一次盘,
而那时写入早已结束, 于是变异后依然全绿 (实测 3 passed/3 passed)。本版
改为让**专用读进程**在另一个写进程持续写盘期间**不停**读, 才拿到区分度。

注意用真实子进程而非线程: ``flock`` 是进程级 advisory 锁, 同进程内多
线程共享同一 fd 与锁状态, 测不出跨进程语义 (ADR-073 已踩过这个坑)。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── 写进程: 反复走真实 load_rules 路径, 每次写一个不同语言的 key ──────────
_WRITER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, sys.argv[2])
    from tools.scripts.rules_engine import rule_loader as rl

    cache_dir = Path(sys.argv[1])
    rl._DISK_CACHE_DIR = cache_dir
    rl._DISK_CACHE_FILE = cache_dir / "rules_cache.json"
    lang = sys.argv[3]

    # 清除内存缓存, 强制每次都走磁盘事务
    for _ in range(int(sys.argv[4])):
        rl._RULE_CACHE.clear()
        try:
            rl.load_rules(lang)
        except (AttributeError, KeyError, IndexError, ValueError):
            pass
    print("WROTE", lang)
    """
)

# ── 预置进程: 写一份大缓存, 用于放大撕裂读取窗口 ─────────────────────────
_SEEDER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, sys.argv[2])
    from tools.scripts.rules_engine import rule_loader as rl

    cache_dir = Path(sys.argv[1])
    rl._DISK_CACHE_DIR = cache_dir
    rl._DISK_CACHE_FILE = cache_dir / "rules_cache.json"
    rl._save_disk_cache({"seed": {"anti_patterns": ["x" * 200] * int(sys.argv[3])}})
    print("SEEDED", 1)
    """
)

# ── 大载荷写进程: 反复走生产写盘函数 _save_disk_cache ────────────────────
#
# 之所以不用 load_rules 写: 真实规则体积小, 截断→写完 的窗口只有微秒级,
# 读者很难撞上, 导致“去掉原子写”的变异可能漏网 (实测 4 passed)。改用大
# 载荷直接调**同一个生产函数** _save_disk_cache, 把窗口拉长到可观测。
_BIG_WRITER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, sys.argv[2])
    from tools.scripts.rules_engine import rule_loader as rl

    cache_dir = Path(sys.argv[1])
    rl._DISK_CACHE_DIR = cache_dir
    rl._DISK_CACHE_FILE = cache_dir / "rules_cache.json"
    size = int(sys.argv[3])
    for i in range(int(sys.argv[4])):
        rl._save_disk_cache({"k" + str(i): {"anti_patterns": ["y" * 500] * size}})
    print("BIGWROTE", i + 1)
    """
)

# ── 读进程: 在写进程工作期间持续读盘, 统计损坏 JSON 次数 ─────────────────
_READER = textwrap.dedent(
    """
    import json, sys, time
    from pathlib import Path
    sys.path.insert(0, sys.argv[2])
    from tools.scripts.rules_engine import rule_loader as rl

    cache_dir = Path(sys.argv[1])
    cache_file = cache_dir / "rules_cache.json"
    rl._DISK_CACHE_DIR = cache_dir
    rl._DISK_CACHE_FILE = cache_file
    deadline = time.time() + float(sys.argv[3])

    reads = 0
    corrupt = 0
    while time.time() < deadline:
        try:
            text = cache_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except OSError:
            corrupt += 1
            continue
        reads += 1
        try:
            json.loads(text)
        except json.JSONDecodeError:
            corrupt += 1
    print("RESULT", reads, corrupt)
    """
)


def _popen(script: str, cache_dir: Path, *args: str) -> subprocess.Popen[str]:
    # 仓库路径经 argv 传入而非拼接进脚本文本: 子进程脚本里含 ``{"seed": ...}``
    # 这类字面量花括号, ``str.format`` 会把它们当成占位符而抛 KeyError,
    # 而字符串拼接又会引入引号转义与路径注入风险。
    cmd = [sys.executable, "-c", script, str(cache_dir), str(REPO_ROOT), *args]
    return subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT,
    )


class TestDiskCacheConcurrency:
    """ADR-075: 磁盘缓存的跨进程并发安全。"""

    def test_concurrent_writers_keep_every_key(self) -> None:
        """不变量 1: N 个进程并发写, 磁盘上必须留下全部 N 个 key。"""
        langs = ["python", "javascript", "typescript", "rust", "go", "java"]

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            for _ in range(3):
                writers = [_popen(_WRITER, cache_dir, lang, "4") for lang in langs]
                for proc in writers:
                    out, err = proc.communicate(timeout=300)
                    assert "WROTE" in out, f"写进程异常: {out!r} / {err[-800:]!r}"

                # 每个语言只写一个 key; 该轮应有全部 6 个 key。
                # key 形如 ``<language>:<rules_hash>``, 故比对语言前缀而非完整 key。
                payload = json.loads((cache_dir / "rules_cache.json").read_text())
                prefixes = {key.split(":", 1)[0] for key in payload}
                print(f"\n[并发写] 磁盘 key 数={len(payload)} (期望 {len(langs)})")
                missing = set(langs) - prefixes
                assert not missing, f"并发写丢更新: 缺少语言 {sorted(missing)}, 实得 {sorted(payload)}"

    def test_reader_never_sees_torn_file(self) -> None:
        """不变量 2: 写盘进行中并发读, 绝不能读到损坏的 JSON。"""
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            # 先写入一份很大的缓存, 拉长“已截断但未写完”的暴露窗口
            seeder = _popen(_SEEDER, cache_dir, "2000")
            seed_out, seed_err = seeder.communicate(timeout=300)
            assert "SEEDED" in seed_out, f"预置进程异常: {seed_err[-800:]!r}"

            # 写进程: 载荷大小与轮数
            writer = _popen(_BIG_WRITER, cache_dir, "300", "25")
            reader = _popen(_READER, cache_dir, "10")
            reader_out, _ = reader.communicate(timeout=300)
            writer_out, writer_err = writer.communicate(timeout=300)
            assert "BIGWROTE" in writer_out, f"写进程异常: {writer_err[-800:]!r}"

            line = reader_out.strip().splitlines()[-1]
            assert line.startswith("RESULT"), f"读进程无结果: {reader_out!r}"
            _, reads, corrupt = line.split()
            reads, corrupt = int(reads), int(corrupt)
            print(f"\n[并发读] 读 {reads} 次, 损坏 {corrupt} 次")
            assert reads > 0, "读进程一次都没读到内容, 测试无区分度"
            assert corrupt == 0, f"读到损坏 JSON {corrupt} 次 —— 写盘非原子 (should be 0)"

    def test_single_threaded_behavior_unchanged(self) -> None:
        """对照组: 锁不能改变单线程语义, 也不能引入死锁。"""
        sys.path.insert(0, str(REPO_ROOT))
        from tools.scripts.rules_engine import rule_loader as rl

        orig_dir, orig_file = rl._DISK_CACHE_DIR, rl._DISK_CACHE_FILE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cache_dir = Path(tmp)
                rl._DISK_CACHE_DIR = cache_dir
                rl._DISK_CACHE_FILE = cache_dir / "rules_cache.json"

                payload = {"python:abc": {"anti_patterns": []}}
                rl._save_disk_cache(payload)
                assert rl._load_disk_cache() == payload

                # 覆盖写应替换而非合并
                rl._save_disk_cache({"rust:xyz": {}})
                assert rl._load_disk_cache() == {"rust:xyz": {}}

                # 损坏的 JSON 必须被吞掉并返回空 dict, 而非抛异常
                rl._DISK_CACHE_FILE.write_text("{not json", encoding="utf-8")
                assert rl._load_disk_cache() == {}
        finally:
            rl._DISK_CACHE_DIR, rl._DISK_CACHE_FILE = orig_dir, orig_file

    def test_save_leaves_no_temp_files(self) -> None:
        """原子写用临时文件 + rename, 结束后不得残留临时文件。"""
        sys.path.insert(0, str(REPO_ROOT))
        from tools.scripts.rules_engine import rule_loader as rl

        orig_dir, orig_file = rl._DISK_CACHE_DIR, rl._DISK_CACHE_FILE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cache_dir = Path(tmp)
                rl._DISK_CACHE_DIR = cache_dir
                rl._DISK_CACHE_FILE = cache_dir / "rules_cache.json"

                rl._save_disk_cache({"python:abc": {"anti_patterns": []}})

                names = sorted(p.name for p in cache_dir.iterdir())
                print(f"\n[残留检查] 目录内容={names}")
                assert names == ["rules_cache.json"], f"原子写残留临时文件: {names}"
                assert json.loads(rl._DISK_CACHE_FILE.read_text(encoding="utf-8")) == {
                    "python:abc": {"anti_patterns": []}
                }
        finally:
            rl._DISK_CACHE_DIR, rl._DISK_CACHE_FILE = orig_dir, orig_file
