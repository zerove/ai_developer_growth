"""ADR-073 跨进程锁机制的**确定性**测试。

为何需要这组用例
----------------
"给读者加锁" 这类修复有一个证据链缺口: 把读锁去掉, 竞态窗口只有
``Path.write_text`` 截断重写的那几微秒, 常规 ``-n 8`` 全量跑
**复现不出**失败 (实测: 移除读锁后全量 4608 passed)。所以
"变异不通过" 既不能证明读锁有用, 也不能证明它无用。

与其依赖运气, 本组**直接测 conftest 里那两个真实的函数**:
``acquire_repo_read_lock`` / ``acquire_repo_mutation_lock``。
由真实子进程持锁一个确定的时长, 断言后继者的等待时长。锁真的
生效则必然通过; 被退化成 no-op / 一律用 LOCK_EX / 锁路径写错,
则必然失败。

设计要点
--------
* 被测对象是 conftest 的**真函数**, 不是内联的裸 ``fcntl`` ——
  否则"把函数体换成 no-op"这种变异测不出来 (已实测踩过这个坑)。
* 握手走**文件**而非管道: 管道 + ``readline()`` 在 pytest 捕获
  输出时会死锁。
* 锁文件用 ``tmp_path`` 下的独立路径, 与生产锁路径同构, 但不
  争用真实全局锁, 避免自身拖慢/干扰其它用例。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import _lock_path  # noqa: E402

HOLD_SECONDS = 1.5

# 子进程: 调用 conftest 里真实的 acquire_* 上下文管理器, 写就绪标记,
# 持锁 HOLD 秒, 再写释放标记。
_HOLD = textwrap.dedent(
    f"""
    import os, sys, time
    sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
    import conftest

    ready, release, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    # 可选: 持锁期间改写的目标文件 (复刻 FailOpenDetectorTest 的真实行为)
    target = sys.argv[4] if len(sys.argv) > 4 else ""
    restore = sys.argv[5] if len(sys.argv) > 5 else ""
    enter = (conftest.acquire_repo_mutation_lock if kind == "write"
             else conftest.acquire_repo_read_lock)
    with enter():
        with open(ready, "w") as fh:
            fh.write("locked")
        # **等探针落 go 标记后才起算窗口**: 探针的进程启动 + import conftest
        # 在高负载下可达 1s+, 若从写 ready 起算, 窗口会在探针真正阻塞前
        # 就被消耗光, 断言 blocked > HOLD/2 变成测机器负载而非测锁语义。
        # 实测: 1.5s 窗口在负载下 6/20 未挡住, 4.0s 则 0/20。
        go = os.path.join(os.path.dirname(ready), "probe.go")
        go_deadline = time.monotonic() + 60
        while time.monotonic() < go_deadline and not os.path.exists(go):
            time.sleep(0.005)
        if target:
            # 与真实用例一致: truncate + write, 非原子替换 -> 存在半截窗口
            payload = ('{{"hooks": {{"on_commit": [{{"name": "ZZZ-canary"}}]}}')
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(payload)
        deadline = time.monotonic() + float({HOLD_SECONDS})
        # 等测试放行, 或兜底自解, 绝不死等
        while time.monotonic() < deadline:
            try:
                with open(release):
                    break
            except FileNotFoundError:
                time.sleep(0.01)
        if target and restore:
            # 复刻 addCleanup 还原: 必须在**释放锁之前**完成
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(restore)
    """
)

# 子进程: 调用真实 acquire_* 取锁, 记录等待时长
_PROBE = textwrap.dedent(
    f"""
    import sys, time
    sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
    import conftest

    out, kind = sys.argv[1], sys.argv[2]
    enter = (conftest.acquire_repo_mutation_lock if kind == "write"
             else conftest.acquire_repo_read_lock)
    # **先落 go 标记再取锁**: 让持锁者知道探针已经进入待阻塞状态,
    # 从而把持锁窗口的计时起点对齐到"探针即将 flock"那一刻。
    # 探针不能先取锁再发信号 —— 那会死锁在 fcntl 上, 标记永远写不出。
    go = sys.argv[3]
    with open(go, "w") as fh:
        fh.write("go")
    t0 = time.monotonic()
    with enter():
        elapsed = time.monotonic() - t0
    with open(out, "w") as fh:
        fh.write(f"{{elapsed:.3f}}")
    """
)


def _probe(kind: str, lock: str, out: Path, go: Path | None = None) -> float:
    """在独立进程里通过 conftest 的真函数取锁, 返回**真正阻塞**的时长 (秒)。

    ``go`` 给定时, 探针会在取锁**之前**落该标记, 供持锁者对齐计时起点。
    缺省时用 ``probe.go`` —— **刻意不按 kind 区分**: 持锁者只知道在等
    "某个"探针, 若两边按 kind 取不同名(如持 write 等 ready-write.go 而
    探针是 read 落 ready-read.go), 持锁者会空等到超时。
    """
    marker = go if go is not None else out.with_name("probe.go")
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, str(out), kind, str(marker)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "ADG_TEST_LOCK_PATH": str(lock)},
    )
    assert proc.returncode == 0, f"取锁子进程失败: stderr={proc.stderr!r}"
    return float(out.read_text())


class TestRepoLockSemantics:
    """conftest 的跨进程锁必须真互斥, 且共享/独占语义不能一刀切。"""

    def _start_holder(
        self, kind: str, tmp: Path, target: Path | None = None, restore: str | None = None
    ) -> tuple[subprocess.Popen[bytes], Path]:
        """启动持锁子进程; 返回前确认它**确实已持锁** (避免测到空窗期)。

        ``target`` 非空时, 持锁期间会把 canary 写进该文件; ``restore``
        给定时在释放锁**之前**把它还原, 复刻 addCleanup 的真实时序。
        """
        ready, release = tmp / f"ready-{kind}", tmp / f"release-{kind}"
        # **必须先删 go 标记**: 基线探针(无竞争那次)在同目录写过 probe.go,
        # 持锁者一进来就看到它 -> 窗口从"基线探针时刻"起算, 而非从真正
        # 探针到达起算。满载下基线探针早到数百毫秒, 窗口被提前烧掉,
        # 实测 blocked 掉到 0.747s(阈值 0.75s) -> 假失败。
        (tmp / "probe.go").unlink(missing_ok=True)
        args = [sys.executable, "-c", _HOLD, str(ready), str(release), kind]
        if target is not None:
            args.append(str(target))
        args.append(restore or "")
        holder = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env={**os.environ, "ADG_TEST_LOCK_PATH": str(tmp / "probe.lock")},
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if ready.exists():
                return holder, release
            if holder.poll() is not None:
                err = holder.stderr.read().decode() if holder.stderr else ""
                raise AssertionError(f"持锁子进程提前退出, returncode={holder.returncode}: {err}")
            time.sleep(0.01)
        holder.kill()
        raise AssertionError("持锁子进程未在 30s 内就绪")

    def test_read_lock_is_blocked_while_write_lock_held(self, tmp_path: Path) -> None:
        """写者持独占锁期间, 读者的共享锁必须被挡住 —— ADR-073 的核心保证。"""
        lock = tmp_path / "probe.lock"
        lock.touch()
        # 无竞争基线: 证明测试环境本身没有让每次取锁都很慢
        baseline = _probe("read", str(lock), tmp_path / "base.out")
        assert baseline < HOLD_SECONDS / 2, f"无竞争时取锁就耗时 {baseline}s, 测试环境异常"

        holder, release = self._start_holder("write", tmp_path)
        try:
            blocked = _probe("read", str(lock), tmp_path / "read.out")
        finally:
            release.touch()
            holder.wait(timeout=60)

        assert blocked > HOLD_SECONDS / 2, (
            f"读者仅等待 {blocked}s, 而写者持锁 {HOLD_SECONDS}s -> acquire_repo_read_lock 没有被独占锁挡住"
        )

    def test_write_lock_is_mutually_exclusive(self, tmp_path: Path) -> None:
        """两个写者之间必须互斥: 后者要等前者释放。"""
        lock = tmp_path / "probe.lock"
        lock.touch()
        baseline = _probe("write", str(lock), tmp_path / "base.out")

        holder, release = self._start_holder("write", tmp_path)
        try:
            blocked = _probe("write", str(lock), tmp_path / "write.out")
        finally:
            release.touch()
            holder.wait(timeout=60)

        assert blocked > HOLD_SECONDS / 2, (
            f"第二个写者仅等待 {blocked}s (基线 {baseline}s) -> acquire_repo_mutation_lock 未互斥"
        )

    def test_reader_never_sees_writer_s_torn_content(self, tmp_path: Path) -> None:
        """回归 ADR-073 的真实故障形态, 且**确定性**, 不依赖运气。

        复刻 ``FailOpenDetectorTest``: 写者在持锁期间把受控 JSON 截断重写
        (``Path.write_text`` = truncate + write, 非原子替换), 期间放 canary。
        读者持共享锁读同一文件并 ``json.loads``。

        锁生效时: 读者必然被挡到写者完全结束之后, 只能读到**还原后**的
        合法 JSON。
        锁失效时: 读者会落进写者的窗口, 读到半截 JSON 而抛
        ``JSONDecodeError`` —— 这正是原始 flake 的形态。
        """
        lock = tmp_path / "probe.lock"
        lock = lock.as_posix()
        target = tmp_path / "controlled.json"
        payload = json.dumps({"hooks": {"on_commit": [{"name": "real"}]}}, ensure_ascii=False)
        target.write_text(payload, encoding="utf-8")

        # 写者: 持写锁 -> 放 canary -> 释放锁前还原
        holder, release = self._start_holder("write", tmp_path, target=target, restore=payload)
        try:
            # 读者: 持共享锁, 读文件并解析
            script = textwrap.dedent(
                f"""
                import json, sys
                sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
                import conftest
                # 取锁前落 go 标记, 供持锁者对齐窗口起点(见 _HOLD 注释)
                with open({str(tmp_path / "probe.go")!r}, "w") as fh:
                    fh.write("go")
                with conftest.acquire_repo_read_lock():
                    with open({str(target)!r}, encoding="utf-8") as fh:
                        data = json.load(fh)
                with open({str(tmp_path / "read.json")!r}, "w") as fh:
                    json.dump(data, fh, ensure_ascii=False)
                """
            )
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "ADG_TEST_LOCK_PATH": lock},
            )
        finally:
            release.touch()
            holder.wait(timeout=60)

        assert proc.returncode == 0, f"读者在写者持锁期间读到了不可解析的受控文件: stderr={proc.stderr!r}"
        seen = json.loads((tmp_path / "read.json").read_text(encoding="utf-8"))
        assert seen == json.loads(payload), f"读者读到的是写者的中间态: {seen}"

    def test_shared_readers_do_not_serialise_each_other(self, tmp_path: Path) -> None:
        """健康代码对照: 读者持共享锁期间, 另一个读者**必须能立刻**拿到锁。

        这条是对上面"必须阻塞"的反向校验, 同时也是"读锁被误写成
        LOCK_EX"的唯一探针 —— 若实现用 LOCK_EX 一刀切, 此处必然
        等待到持锁者释放, 断言失败。

        注意: 不能用"并发起 N 个短进程"来验, 短进程几乎不会真正
        重叠, 即便退化成独占也测不出来 (已实测踩过)。必须让一个读者
        **持续持锁**, 再探第二个。
        """
        lock = tmp_path / "probe.lock"
        lock.touch()

        holder, release = self._start_holder("read", tmp_path)
        try:
            second = _probe("read", str(lock), tmp_path / "second.out")
        finally:
            release.touch()
            holder.wait(timeout=60)

        assert second < HOLD_SECONDS / 2, (
            f"第二个读者等待 {second}s, 而第一个读者持锁 {HOLD_SECONDS}s -> 共享锁被误实现成独占锁, 并发被退化成串行"
        )

    def test_real_repo_lock_path_is_in_tmp_not_worktree(self) -> None:
        """锁文件必须在系统临时目录 —— 落在工作区会污染 git status 门禁。"""
        worktree = Path(__file__).resolve().parents[1]
        lock = _lock_path()
        assert lock.parent != worktree
        assert not str(lock).startswith(str(worktree) + os.sep)
