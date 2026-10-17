"""提交边界守卫: 本次提交入库后, 链接不得指向未入库的文件。

## 要锁住的缺陷

`docs/adr/ADR.md`(已跟踪) 曾含 `[[ADR-078-...]]`, 而 ADR-078 当时**未被 git 跟踪**。
工作树上两者都在, 所以 `link_auditor.py` 报 "All links are valid" —— 它校验的是
**文件是否存在**, 而断链只发生在**干净 clone** 里: 提交记录了引用, 却没有记录被
引用的文件。`generate_adr_index.py --check` 同样看不见, 因为它 glob 磁盘而非 git。

这与 ADR-052/074/076/078 一路的 fail-open 同源: 某一侧"看起来是好的"。
本次实测中它就是**全仓唯一**的真断链, 且靠纯链接检查无法发现。

## 判定口径

"入库集合" = HEAD 已跟踪文件 ∪ 本次将提交的 staged 文件。
只检查 **staged** 文件里的出链 —— 未改动的文件早已入库过, 与本次提交无关。

## 与 lock/link 测试的分工

- `test_controlled_file_reads_are_locked.py`: 读受控文件必须持锁(并发安全)
- `test_link_auditor*.py`: 链接解析逻辑本身是否正确(工作树视角)
- 本文件: **提交边界**视角 —— 目标文件是否会随本次提交一起入库

## 降级

无 git / 非仓库环境下 skip, 不制造假红。测试仓(如打包分发)里 staged 为空,
同样 skip —— 此时无"本次提交"可言。
"""

from __future__ import annotations

import functools
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

WIKILINK = re.compile(r"\[\[([^\]\n]+?)\]\]")
MDLINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _git(*args: str) -> set[str] | None:
    """返回 git 命令的路径集合; 非仓库/无 git 时返回 None 以便 skip。"""
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


@functools.lru_cache(maxsize=256)
def _is_gitignored(rel_path: str) -> bool:
    """该路径是否被 .gitignore 排除。

    被 gitignore 的文件**永远**不会随任何提交入库, 因此指向它的链接不可能靠
    "补一次 git add" 修好 —— 它不是提交边界问题, 而是文档缺陷(实测:
    `.jcode/AGENTS.md` 被 .gitignore:82 的 `.jcode/*` 排除, 却同时被根 AGENTS.md
    与 CONTEXT.md 引用)。若不在此豁免, 本用例会**永久报红**, 而报红的守卫
    等于没有守卫。
    """
    try:
        out = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def _will_be_committed() -> tuple[set[str], set[str]]:
    head = _git("ls-tree", "-r", "--name-only", "HEAD")
    staged = _git("diff", "--cached", "--name-only")
    if head is None or staged is None:
        return set(), set()
    return head | staged, staged


def _resolve(src: str, target: str) -> str | None:
    """按 Obsidian 语义解析: 文件相对 -> vault 相对 -> 同名回退。"""
    t = target.split("#")[0].strip()
    if not t.endswith(".md"):
        t += ".md"
    p = Path(t)
    stack = [] if p.is_absolute() else list(Path(src).parts[:-1])
    for seg in p.parts:
        if seg == "..":
            if stack:
                stack.pop()
        elif seg not in (".", ""):
            stack.append(seg)
    return "/".join(stack)


@pytest.fixture(scope="module")
def commit_boundary() -> tuple[set[str], set[str]]:
    committed, staged = _will_be_committed()
    if not staged:
        pytest.skip("staged 为空, 无'本次提交'可言 (如分发用测试仓)")
    return committed, staged


def _committed_resolve(src: str, target: str, files: set[str], stems: set[str]) -> bool:
    """已提交树内的链接解析。

    刻意不复用上面的 `_resolve`: 它只做文件相对, 因此对 `docs/MOC.md` 里的
    vault 相对链接 `docs/mindset/README` 会解析成 `docs/docs/mindset/README.md` ——
    该缺陷此前不可见, 因为当时唯一被检查的 staged 文件位于仓库根 (`CONTEXT.md`),
    `Path(src).parts[:-1]` 为空, 双前缀不会显现。已提交树检查覆盖子目录文件后
    立即暴露。

    另需处理指向**非 markdown** 文件的链接(如 `README.md -> LICENSE`): 只补
    `.md` 会把真实存在的文件误判为断链。
    """
    t = target.split("#")[0].strip()
    if not t:
        return True

    src_dir = Path(src).parts[:-1]

    def norm(parts: tuple[str, ...]) -> str:
        stack: list[str] = []
        for seg in parts:
            if seg == "..":
                if stack:
                    stack.pop()
            elif seg not in (".", ""):
                stack.append(seg)
        return "/".join(stack)

    def with_ext(base: str) -> list[str]:
        return [base] if base.endswith(".md") else [base + ".md", base]

    candidates: list[str] = []
    p = Path(t)
    if p.is_absolute():
        candidates += with_ext(norm(p.parts))
    else:
        candidates += with_ext(norm(tuple([*src_dir, *p.parts])))  # 1) 文件相对
        candidates += with_ext(norm(p.parts))  # 2) vault 相对 (仓库根)
        # 3) 本仓约定 docs/ 为 vault 根: docs/efficiency/*.md 里的
        #    `efficiency/xxx` 指的是 docs/efficiency/xxx, 非仓库根下的
        #    efficiency/xxx。与 link_auditor.py 的口径保持一致。
        candidates += with_ext(norm(tuple(["docs", *p.parts])))
    if any(c in files for c in candidates):
        return True
    return "/" not in t and Path(t).stem in stems


class TestStagedFilesHaveNoDanglingLinks:
    def test_all_staged_links_resolve_within_commit(self, commit_boundary: tuple[set[str], set[str]]) -> None:
        committed, staged = commit_boundary
        stems = {Path(f).stem for f in committed if f.endswith(".md")}

        dangling: list[str] = []
        for rel in sorted(staged):
            path = REPO_ROOT / rel
            if not path.is_file() or path.suffix != ".md":
                continue
            text = path.read_text(encoding="utf-8").replace("\\|", "|")
            text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            text = re.sub(r"`[^`\n]*`", "", text)
            for pattern in (WIKILINK, MDLINK):
                for m in pattern.finditer(text):
                    target = m.group(1).split("|")[0].strip()
                    if not target or target.startswith(("http://", "https://", "mailto:")):
                        continue
                    resolved = _resolve(rel, target)
                    if resolved in committed:
                        continue
                    # 同名回退只对**裸文件名**成立: Obsidian 的 [[ADR-078]] 是按
                    # 文件名在整个 vault 内解析的。但对写了显式路径的链接, 路径是
                    # 权威的 —— 干净 clone 里 .jcode/AGENTS.md 不存在, 只有根目录
                    # 的 AGENTS.md, 同名不能互相顶替。
                    # 少了这个限定, 本用例会漏检真实断链(实测确有: .jcode/AGENTS.md
                    # 未被跟踪, 却被 staged 的 CONTEXT.md 引用)。
                    if "/" not in target and Path(target).stem in stems:
                        continue
                    if _is_gitignored(resolved):
                        continue
                    dangling.append(f"{rel} -> {target}")

        assert not dangling, (
            "以下链接指向的文件不会随本次提交入库, 干净 clone 中即为断链:\n  "
            + "\n  ".join(dangling)
            + "\n请把被引用的文件一并 git add (或修正该引用)。"
        )

    def test_adr_index_references_are_tracked(self) -> None:
        """docs/adr/ADR.md 是生成索引, 它的每条引用都必须指向已跟踪文件。

        单独成例: 它是被多条路径引用的中枢文档, 一旦引用了未跟踪 ADR,
        断链会出现在**所有**引用它的文档里, 排查成本高。
        """
        committed, _ = _will_be_committed()
        if not committed:
            pytest.skip("非 git 仓库, 跳过")

        index = REPO_ROOT / "docs" / "adr" / "ADR.md"
        if not index.is_file():
            pytest.skip("ADR 索引不存在")

        text = index.read_text(encoding="utf-8").replace("\\|", "|")
        refs = [m.group(1).split("|")[0].strip() for m in WIKILINK.finditer(text)]
        assert refs, "ADR 索引为空或格式异常, 本用例失去意义"

        missing = sorted(
            {
                r
                for r in refs
                if not (REPO_ROOT / "docs" / "adr" / f"{r}.md").exists() and f"docs/adr/{r}.md" not in committed
            }
        )
        assert not missing, f"ADR 索引引用了不存在的条目: {missing}"


class TestCommittedTreeHasNoDanglingLinks:
    """已提交树内部不得存在断链。

    `TestStagedFilesHaveNoDanglingLinks` 只看 staged 文件, 而干净 clone 中
    staged 为空, 按设计 skip —— 因此"引用已在仓库里、但被引用的文件从未提交"
    这类缺陷对它完全不可见。

    实测: ADR.md / docs/adr/ADR.md / CONTEXT.md / ROADMAP.md 四处引用
    ADR-078, 而该文件从未入库, 干净 clone 中必然出现 4 处死链。靠人工 clone
    才发现, 说明这个盲区需要机械覆盖。

    必须读**已提交内容**而非工作树: 工作树里该文件存在(只是没提交), 读工作树
    会误判为通过 —— 那正是本用例要防的失效模式。故用 `git archive HEAD` 把
    已提交的 md 取出到临时目录再扫描。
    """

    @staticmethod
    def _committed_tree(tmp: Path) -> Path:
        proc = subprocess.run(
            ["git", "archive", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=300,
        )
        if proc.returncode != 0:
            pytest.skip("非 git 仓库或 git archive 不可用")
        subprocess.run(["tar", "-x", "-C", str(tmp)], input=proc.stdout, capture_output=True, check=True)
        return tmp

    def test_committed_tree_has_no_dangling_links(self, tmp_path: Path) -> None:
        root = self._committed_tree(tmp_path)
        # 解析集含**全部**已提交文件: 链接可能指向 LICENSE、图片等非 md 资源,
        # 只把 md 放进解析集会把它们误判为断链
        files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        assert len(files) > 100, f"只取出 {len(files)} 个文件, 采样异常, 本用例失去意义"
        stems = {Path(f).stem for f in files}
        md_files = {f for f in files if f.endswith(".md")}

        dangling: list[str] = []
        for rel in sorted(md_files):
            text = (root / rel).read_text(encoding="utf-8", errors="replace").replace("\\|", "|")
            text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            text = re.sub(r"`[^`\n]*`", "", text)
            for pattern in (WIKILINK, MDLINK):
                for m in pattern.finditer(text):
                    target = m.group(1).split("|")[0].split("#")[0].strip()
                    if not target or target.startswith(("http://", "https://", "mailto:")):
                        continue
                    if not _committed_resolve(rel, target, files, stems):
                        dangling.append(f"{rel} -> {target}")

        assert not dangling, (
            "已提交树中存在断链 —— 干净 clone 中即为死链:\n  "
            + "\n  ".join(dangling[:20])
            + (f"\n  ... 共 {len(dangling)} 处" if len(dangling) > 20 else "")
            + "\n请提交被引用的文件, 或修正该引用。"
        )
