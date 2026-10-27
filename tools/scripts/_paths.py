"""仓库路径与 frontmatter 解析的唯一入口。

以 `__file__` 锚定仓库根，脚本从任意 CWD 启动都读写同一份
`docs/`、`docs/MOC.md`、`docs/case-studies/`。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def repo_root() -> Path:
    """返回仓库根目录 (与启动 CWD 无关)."""
    return REPO_ROOT


def resolve_repo_path(path: str | Path) -> Path:
    """相对路径按仓库根解析；绝对路径原样返回."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """解析 `---` 包裹的简单 YAML frontmatter.

    仅支持 `key: value` 标量（项目文档约定子集）；嵌套 YAML 请用
    `yaml.safe_load`。返回值中的 body 已去掉前导空行。
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    block = content[3:end]
    body = content[end + 4 :].lstrip("\r\n")

    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")

    return data, body
