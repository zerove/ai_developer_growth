#!/usr/bin/env python3
"""ADG Bootstrap — 把本项目的治理能力一键移植到任意项目。

用法（在本项目根目录执行）:
    python tools/scripts/adg_bootstrap.py /path/to/target-project
    python tools/scripts/adg_bootstrap.py /path/to/target --langs go,typescript
    python tools/scripts/adg_bootstrap.py /path/to/target --minimal

移植内容:
    1. .jcode/hooks.json          统一 hook 运行器配置（按目标语言裁剪）
    2. .jcode/scripts/            核心治理脚本（governance-auditor/context-sync 等）
    3. adg CLI 规则               ai-dev-framework 规则集（按语言选择）
    4. pre-commit 配置            质量门禁钩子
    5. AGENTS.md 片段             AI 协作规范注入

目标项目无需安装本项目，仅依赖 Python 3.11+。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
PROJECT_ROOT = THIS_DIR.parent.parent

# 核心治理脚本：目标项目 hooks 流程的最小依赖集
CORE_JCODE_SCRIPTS = [
    "_common.py",
    "governance-auditor.py",
    "context-sync.py",
    "hooks_runner.py",
]

# 完整模式额外脚本
EXTRA_JCODE_SCRIPTS = [
    "governance-docs-validator.py",
    "self-correction-loop.py",
    "multi_agent_orch.py",
]

# ai-dev-framework 中与语言无关的规则目录
FRAMEWORK_COMMON_DIRS = ["common", "domains", "frameworks", "scripts"]

# 支持的目标语言（对应 ai-dev-framework/languages/<lang>）
SUPPORTED_LANGUAGES = [
    "python",
    "go",
    "rust",
    "java",
    "typescript",
    "javascript",
    "kotlin",
    "csharp",
    "ruby",
    "php",
    "swift",
    "cpp",
]


def detect_target_languages(target: Path) -> list[str]:
    """按标记文件探测目标项目的语言组合 (V2.22 P6-6 拆分: 抽 _detect_by_markers + _detect_by_extensions)."""
    markers: dict[str, list[str]] = {
        "python": ["pyproject.toml", "requirements.txt", "setup.py"],
        "go": ["go.mod"],
        "rust": ["Cargo.toml"],
        "java": ["pom.xml", "build.gradle"],
        "kotlin": ["build.gradle.kts"],
        "typescript": [],  # 由扩展名判断
        "javascript": [],
        "ruby": ["Gemfile"],
        "php": ["composer.json"],
        "csharp": [],
        "swift": ["Package.swift"],
        "cpp": ["CMakeLists.txt", "Makefile"],
    }
    found = _detect_by_markers(target, markers)
    found.extend(_detect_by_extensions(target, found))
    return found or ["python"]


def _detect_by_markers(target: Path, markers: dict[str, list[str]]) -> list[str]:
    """按 marker 文件检测语言 (模块级 helper).

    Args:
        target: 项目根目录
        markers: {lang: marker 文件列表}

    Returns:
        检测到的语言列表
    """
    found: list[str] = []
    for lang, files in markers.items():
        if any((target / f).exists() for f in files):
            found.append(lang)
    return found


def _detect_by_extensions(target: Path, found: list[str]) -> list[str]:
    """按文件扩展名兜底检测 (typescript/javascript/csharp, 模块级 helper).

    Args:
        target: 项目根目录
        found: 已检测到的语言列表 (避免重复)

    Returns:
        新增的语言列表
    """
    ext_map = {".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".cs": "csharp"}
    new_found: list[str] = []
    for path in target.rglob("*"):
        if path.is_file() and path.suffix.lower() in ext_map:
            lang = ext_map[path.suffix.lower()]
            if lang not in found and lang not in new_found:
                new_found.append(lang)
        if len(found) + len(new_found) >= len(SUPPORTED_LANGUAGES):
            break
    return new_found


def copy_jcode_scripts(target: Path, minimal: bool) -> int:
    """复制 .jcode/scripts 核心脚本。"""
    src_dir = PROJECT_ROOT / ".jcode" / "scripts"
    dst_dir = target / ".jcode" / "scripts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    scripts = CORE_JCODE_SCRIPTS + ([] if minimal else EXTRA_JCODE_SCRIPTS)
    count = 0
    for name in scripts:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dst_dir / name)
            count += 1
    # hooks_runner 的依赖
    for dep_name in ("auto_fix.py", "quality_gate.py"):
        dep_src = PROJECT_ROOT / "tools" / "scripts" / dep_name
        if not minimal and dep_src.exists():
            shutil.copy2(dep_src, dst_dir / f"_dep_{dep_name}")
            count += 1
    return count


def copy_tools_scripts(target: Path, minimal: bool) -> int:
    """复制 tools/scripts 运行时依赖（.jcode 脚本按约定从 <root>/tools/scripts 导入）。"""
    src_dir = PROJECT_ROOT / "tools" / "scripts"
    dst_dir = target / "tools" / "scripts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    deps = ["_common.py", "language_registry.py", "app_config.py"]
    if not minimal:
        deps += ["quality_gate.py", "auto_fix.py"]
    count = 0
    for name in deps:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dst_dir / name)
            count += 1
    # adg_cli 的检查链依赖 rules_engine（语言无关规则引擎），完整移植
    re_src = PROJECT_ROOT / "tools" / "scripts" / "rules_engine"
    if not minimal and re_src.is_dir():
        shutil.copytree(
            re_src,
            dst_dir / "rules_engine",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        count += len(list((dst_dir / "rules_engine").rglob("*.py")))
    # 包结构标记，保证 python -m tools.scripts.adg_cli 可用
    (target / "tools" / "__init__.py").touch(exist_ok=True)
    (dst_dir / "__init__.py").touch(exist_ok=True)
    return count


def adapt_hooks_config(target: Path, langs: list[str]) -> bool:
    """读取本仓库 hooks.json，按目标语言裁剪后写入。"""
    src = PROJECT_ROOT / ".jcode" / "hooks.json"
    if not src.exists():
        print("  ⚠️ 源 hooks.json 不存在，跳过")
        return False
    config = json.loads(src.read_text(encoding="utf-8"))
    primary_lang = langs[0]
    hooks = config.get("hooks", {})
    for trigger, entries in hooks.items():
        kept = []
        for entry in entries:
            cmd = entry.get("command", "")
            # 按主语言替换 --lang 参数；文档类检查对非 python 项目默认跳过
            if "--lang python" in cmd:
                entry["command"] = cmd.replace("--lang python", f"--lang {primary_lang}")
            kept.append(entry)
        hooks[trigger] = kept
    dst = target / ".jcode" / "hooks.json"
    dst.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def copy_framework_rules(target: Path, langs: list[str], minimal: bool) -> int:
    """复制 ai-dev-framework 公共规则与所选语言规则。"""
    fw = PROJECT_ROOT / "ai-dev-framework"
    if not fw.exists():
        print("  ⚠️ ai-dev-framework 不存在，跳过规则复制")
        return 0
    dst_fw = target / ".adg" / "framework"
    dst_fw.mkdir(parents=True, exist_ok=True)
    count = 0
    for d in FRAMEWORK_COMMON_DIRS:
        src = fw / d
        if src.is_dir():
            shutil.copytree(
                src,
                dst_fw / d,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            count += 1
    if minimal:
        return count
    languages_dst = dst_fw / "languages"
    languages_dst.mkdir(exist_ok=True)
    for lang in langs:
        src = fw / "languages" / lang
        if src.is_dir():
            shutil.copytree(src, languages_dst / lang, dirs_exist_ok=True)
            count += 1
    return count


def write_precommit(target: Path) -> bool:
    """生成精简版 pre-commit 配置（ruff/mypy 仅在 python 项目启用）。"""
    import yaml  # noqa: PLC0415

    repos: list[dict[str, object]] = [
        {
            "repo": "https://github.com/pre-commit/pre-commit-hooks",
            "rev": "v4.6.0",
            "hooks": [
                {"id": "trailing-whitespace"},
                {"id": "end-of-file-fixer"},
                {"id": "check-merge-conflict"},
                {"id": "check-yaml"},
                {"id": "check-toml"},
            ],
        },
    ]
    if (target / "pyproject.toml").exists() or (target / "requirements.txt").exists():
        repos.append(
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.6.9",
                "hooks": [
                    {"id": "ruff", "args": ["--fix"]},
                    {"id": "ruff-format"},
                ],
            }
        )
    cfg = {"repos": repos}
    dst = target / ".pre-commit-config.yaml"
    dst.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return True


def inject_agents_md(target: Path, langs: list[str]) -> None:
    """向目标项目 AGENTS.md 注入 ADG 使用说明（不覆盖已有内容）。"""
    dst = target / "AGENTS.md"
    section = (
        "\n\n## ADG 治理（自动注入）\n\n"
        "- 质量检查: `python -m tools.scripts.adg_cli check`\n"
        f"- 主语言: {', '.join(langs)}\n"
        "- Hook 流程: `python .jcode/scripts/hooks_runner.py <command>`\n"
        "- 提交信息格式: `type(scope): 中文描述`\n"
    )
    if dst.exists():
        content = dst.read_text(encoding="utf-8")
        if "ADG 治理" not in content:
            dst.write_text(content + section, encoding="utf-8")
    else:
        dst.write_text(f"# {target.name}\n" + section, encoding="utf-8")


def write_adg_exclude(target: Path) -> None:
    """确保目标项目 pyproject.toml 含 [tool.adg].exclude，排除治理设施自身。"""
    excludes = [".adg", ".jcode", "tools"]
    pyproject = target / "pyproject.toml"
    try:
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            if "[tool.adg]" in content:
                return  # 已有配置，不覆盖用户设置
            section = '\n[tool.adg]\nexclude = [".adg", ".jcode", "tools"]\n'
            pyproject.write_text(content + section, encoding="utf-8")
        else:
            lines = ["[tool.adg]", "exclude = [" + ", ".join(f'"{e}"' for e in excludes) + "]\n"]
            pyproject.write_text("\n".join(lines), encoding="utf-8")
        print("  ✅ pyproject.toml: [tool.adg].exclude 已写入")
    except OSError as e:
        print(f"  ⚠️ 无法写 pyproject.toml: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADG Bootstrap：治理能力移植到任意项目")
    parser.add_argument("target", help="目标项目路径")
    parser.add_argument("--langs", default="", help="逗号分隔的语言列表（默认自动探测）")
    parser.add_argument("--minimal", action="store_true", help="最小安装（仅核心脚本+公共规则）")
    return parser.parse_args()


def validate_target(raw: str) -> Path:
    """校验目标路径，失败时打印原因并抛出 SystemExit。"""
    target = Path(raw).resolve()
    if not target.exists():
        print(f"❌ 目标目录不存在: {target}")
        raise SystemExit(1)
    if target == PROJECT_ROOT:
        print("❌ 不能把治理装到源项目自身")
        raise SystemExit(1)
    return target


def resolve_languages(args: argparse.Namespace, target: Path) -> list[str]:
    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()] or detect_target_languages(target)
    unknown = [lang for lang in langs if lang not in SUPPORTED_LANGUAGES]
    if unknown:
        print(f"❌ 不支持的语言: {unknown}（支持: {SUPPORTED_LANGUAGES}）")
        raise SystemExit(1)
    return langs


def copy_adg_cli(target: Path) -> None:
    if (PROJECT_ROOT / "tools" / "scripts" / "adg_cli").is_dir():
        shutil.copytree(
            PROJECT_ROOT / "tools" / "scripts" / "adg_cli",
            target / "tools" / "scripts" / "adg_cli",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        print("  ✅ tools/scripts/adg_cli: 已移植（python -m tools.scripts.adg_cli check）")


def write_requirements(target: Path, minimal: bool) -> None:
    """目标项目的 Python 依赖清单（adg_cli/rules_engine 运行所需）。"""
    req = target / ".adg" / "requirements.txt"
    req.parent.mkdir(exist_ok=True)
    deps = ["pyyaml", "loguru"]
    if not minimal:
        deps += [
            "tree-sitter>=0.23",
            "tree-sitter-python>=0.23",
            "tree-sitter-typescript>=0.23",
            "tree-sitter-javascript>=0.23",
            "tree-sitter-go>=0.23",
            "tree-sitter-rust>=0.23",
            "tree-sitter-java>=0.23",
            "tree-sitter-ruby>=0.23",
            "tree-sitter-cpp>=0.23",
        ]
    req.write_text("\n".join(deps) + "\n", encoding="utf-8")
    print(f"  ✅ .adg/requirements.txt: {len(deps)} 个依赖")


def print_next_steps(langs: list[str]) -> None:
    print("\n📋 目标项目后续步骤:")
    print("   pip install -r .adg/requirements.txt")
    print("   pip install pre-commit && pre-commit install")
    print("   python -m tools.scripts.adg_cli check . --lang " + langs[0])


def main() -> int:
    args = parse_args()
    target = validate_target(args.target)
    langs = resolve_languages(args, target)

    mode = "minimal" if args.minimal else "full"
    print(f"🚀 移植 ADG 治理能力 → {target}")
    print(f"   语言: {langs} | 模式: {mode}")

    n_scripts = copy_jcode_scripts(target, args.minimal)
    print(f"  ✅ .jcode/scripts: {n_scripts} 个脚本")

    n_deps = copy_tools_scripts(target, args.minimal)
    print(f"  ✅ tools/scripts: {n_deps} 个运行时依赖")

    if adapt_hooks_config(target, langs):
        print("  ✅ .jcode/hooks.json: 已按语言适配")

    if not args.minimal:
        copy_adg_cli(target)

    n_rules = copy_framework_rules(target, langs, args.minimal)
    print(f"  ✅ .adg/framework: {n_rules} 个规则目录")

    try:
        write_precommit(target)
        print("  ✅ .pre-commit-config.yaml: 已生成")
    except ImportError:
        print("  ⚠️ 缺 pyyaml，跳过 pre-commit 配置（pip install pyyaml 后重跑）")

    inject_agents_md(target, langs)
    print("  ✅ AGENTS.md: 已注入使用说明")

    # 防止规则引擎扫描治理设施自身 + 输出目标依赖清单
    write_adg_exclude(target)
    write_requirements(target, args.minimal)
    print_next_steps(langs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
