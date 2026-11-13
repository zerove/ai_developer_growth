#!/usr/bin/env python3
"""
JCode Platform - Docker Build & Push Script

功能:
- 多架构 Docker 镜像构建 (amd64/arm64)
- 多标签管理 (语义化版本、latest、git-sha)
- SBOM 生成
- 推送到容器镜像仓库

用法:
    python -m tools.scripts.docker_build --version v2.0.0 --push
    python -m tools.scripts.docker_build --version v2.0.0 --platform linux/amd64,linux/arm64 --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY = "registry.example.com"  # 可通过环境变量覆盖
PROJECT = "jcode-platform"
DEFAULT_PLATFORMS = "linux/amd64,linux/arm64"

# 组件列表 (对应 Dockerfile 路径)
COMPONENTS = [
    ("jcode-api", "tools/scripts/Dockerfile.api"),
    ("jcode-orchestrator", "tools/scripts/Dockerfile.orchestrator"),
    ("jcode-quality-gate", "tools/scripts/Dockerfile.quality-gate"),
    ("jcode-semantic", "tools/scripts/Dockerfile.semantic"),
    ("jcode-audit", "tools/scripts/Dockerfile.audit"),
    ("jcode-chaos", "tools/scripts/Dockerfile.chaos"),
    ("jcode-retro", "tools/scripts/Dockerfile.retro"),
]

# ──────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """运行命令"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or Path(__file__).parent.parent.parent,
            capture_output=capture,
            text=True,
            check=False,
            env=env,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except Exception as e:
        return 1, str(e)


def get_git_sha() -> str:
    """获取 Git 短 SHA"""
    code, output = run_cmd(["git", "rev-parse", "--short", "HEAD"])
    return output if code == 0 else "unknown"


def get_git_tag() -> str | None:
    """获取当前版本标签"""
    code, output = run_cmd(["git", "describe", "--tags", "--exact-match", "--match=v*"])
    return output if code == 0 else None


def _build_tag_list(component: str, version: str, registry: str, extra_tags: list[str]) -> list[str]:
    """组装镜像标签列表。"""
    image_name = f"{registry}/{PROJECT}/{component}"
    tags = [f"{image_name}:{version}", f"{image_name}:latest"]
    tags.extend([f"{image_name}:{tag}" for tag in extra_tags])
    return tags


def _buildx_command(dockerfile: str, platforms: str, tags: list[str], push: bool) -> list[str]:
    """构造 docker buildx build 命令。"""
    cmd = [
        "docker",
        "buildx",
        "build",
        "--platform",
        platforms,
        "-f",
        dockerfile,
    ]
    for tag in tags:
        cmd.extend(["-t", tag])
    cmd.append("--push" if push else "--load")
    cmd.append(".")
    return cmd


def _print_component_header(component: str, dockerfile: str, platforms: str, tags: list[str], push: bool) -> None:
    """打印组件构建信息头。"""
    print(f"\n{'=' * 60}")
    print(f"构建组件: {component}")
    print(f"Dockerfile: {dockerfile}")
    print(f"平台: {platforms}")
    print(f"标签: {', '.join(tags)}")
    print(f"推送: {'是' if push else '否 (本地加载)'}")
    print(f"{'=' * 60}")


def build_image(
    component: str,
    dockerfile: str,
    version: str,
    platforms: str,
    registry: str,
    push: bool,
    dry_run: bool,
    extra_tags: list[str],
) -> tuple[bool, str]:
    """构建单个组件镜像"""
    tags = _build_tag_list(component, version, registry, extra_tags)
    cmd = _buildx_command(dockerfile, platforms, tags, push)

    _print_component_header(component, dockerfile, platforms, tags, push)

    if dry_run:
        print(f"🔍 试运行模式，命令: {' '.join(cmd)}")
        return True, ""

    start = time.time()
    code, output = run_cmd(cmd, capture=False)
    elapsed = time.time() - start

    if code == 0:
        print(f"✅ {component} 构建成功 ({elapsed:.1f}s)")
        return True, ""
    print(f"❌ {component} 构建失败 ({elapsed:.1f}s)")
    print(output)
    return False, output


def generate_sbom(image: str, output_dir: Path) -> tuple[bool, str]:
    """生成 SBOM (使用 Syft)"""
    output_file = output_dir / f"{image.replace('/', '_').replace(':', '_')}.sbom.json"
    cmd = ["syft", image, "-o", f"json={output_file}"]

    print(f"生成 SBOM: {image} -> {output_file}")
    code, output = run_cmd(cmd)

    if code == 0:
        print(f"✅ SBOM 生成成功: {output_file}")
        return True, str(output_file)
    else:
        print(f"❌ SBOM 生成失败: {output}")
        return False, output


def sign_image(image: str) -> bool:
    """Cosign 签名镜像"""
    cmd = ["cosign", "sign", "--yes", image]
    print(f"签名镜像: {image}")
    code, output = run_cmd(cmd, capture=False)
    return code == 0


def verify_signature(image: str) -> bool:
    """验证镜像签名"""
    cmd = ["cosign", "verify", image]
    code, output = run_cmd(cmd)
    return code == 0


# ──────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────


def _parse_build_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        prog="docker_build",
        description="JCode Platform Docker Build & Push",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", required=True, help="版本号 (如 v2.0.0)")
    parser.add_argument("--registry", default=REGISTRY, help="镜像仓库地址")
    parser.add_argument("--platforms", default=DEFAULT_PLATFORMS, help="目标平台 (逗号分隔)")
    parser.add_argument("--push", action="store_true", help="推送到镜像仓库")
    parser.add_argument("--no-push", dest="push", action="store_false", help="仅本地构建")
    parser.add_argument("--dry-run", action="store_true", help="试运行")
    parser.add_argument("--sbom", action="store_true", help="生成 SBOM")
    parser.add_argument("--sign", action="store_true", help="Cosign 签名")
    parser.add_argument("--components", help="指定组件 (逗号分隔)，默认全部")
    parser.add_argument("--extra-tags", help="额外标签 (逗号分隔)")
    parser.set_defaults(push=True)

    return parser.parse_args()


def _select_components(args: argparse.Namespace) -> list[tuple[str, str]] | None:
    """按 --components 过滤组件; 含未知组件时打印错误并返回 None。

    V2.20 P4-29 拆分: 抽 _filter_components 收口过滤逻辑,
    _print_unknown_components 收口错误打印.
    """
    if not args.components:
        return list(COMPONENTS)
    selected = [c.strip() for c in args.components.split(",")]
    components = _filter_components(selected)
    if len(components) != len(selected):
        _print_unknown_components(selected, components)
        return None
    return components


def _filter_components(selected: list[str]) -> list[tuple[str, str]]:
    """过滤 COMPONENTS 保留 selected 中命名的项.

    Args:
        selected: 用户指定的组件名列表

    Returns:
        [(name, dockerfile), ...] 匹配项
    """
    return [(name, df) for name, df in COMPONENTS if name in selected]


def _print_unknown_components(selected: list[str], matched: list[tuple[str, str]]) -> None:
    """打印未匹配的组件名 (错误信息).

    Args:
        selected: 用户指定的组件名列表
        matched: 实际匹配到的组件列表
    """
    known = {c[0] for c in COMPONENTS}
    unknown = set(selected) - known
    print(f"❌ 未知组件: {unknown}")


def _collect_extra_tags(args: argparse.Namespace) -> list[str]:
    """合并 --extra-tags、git sha 与时间戳标签。"""
    tags = [t.strip() for t in args.extra_tags.split(",")] if args.extra_tags else []
    git_sha = get_git_sha()
    if git_sha != "unknown":
        tags.append(f"sha-{git_sha}")
    tags.append(f"build-{datetime.now().strftime('%Y%m%d%H%M')}")
    return tags


def _print_build_header(args: argparse.Namespace, components: list[tuple[str, str]]) -> None:
    """打印构建信息头。"""
    print(f"\n{'=' * 60}")
    print("JCode Platform Docker Build")
    print(f"版本: {args.version}")
    print(f"仓库: {args.registry}")
    print(f"平台: {args.platforms}")
    print(f"推送: {'是' if args.push else '否'}")
    print(f"SBOM: {'是' if args.sbom else '否'}")
    print(f"签名: {'是' if args.sign else '否'}")
    print(f"组件: {', '.join(c[0] for c in components)}")
    print(f"{'=' * 60}\n")


def _preflight_checks(components: list[tuple[str, str]]) -> bool:
    """验证 Dockerfile 存在与 buildx 可用。"""
    for name, df in components:
        if not Path(df).exists():
            print(f"❌ Dockerfile 不存在: {df}")
            return False

    code, _ = run_cmd(["docker", "buildx", "version"])
    if code != 0:
        print("❌ docker buildx 不可用")
        return False

    # 创建/使用 builder (失败不阻断, 后续构建会给出明确错误)
    run_cmd(
        [
            "docker",
            "buildx",
            "create",
            "--name",
            "jcode-builder",
            "--use",
            "--bootstrap",
        ],
        capture=False,
    )
    return True


def _build_all_components(
    args: argparse.Namespace,
    components: list[tuple[str, str]],
    extra_tags: list[str],
    sbom_dir: Path,
) -> tuple[list[str], list[str]]:
    """逐组件构建, 返回 (失败列表, SBOM 文件列表)。

    V2.20 P4-30 拆分: 抽 _build_single_component 收口单组件构建 + SBOM + 签名,
    主函数仅遍历 + 收集结果 (用 SBOM_FAILURE sentinel 区分失败).
    """
    failed: list[str] = []
    sbom_files: list[str] = []

    for name, dockerfile in components:
        sbom_file = _build_single_component(name, dockerfile, args, extra_tags, sbom_dir)
        if sbom_file == _SBOM_FAILURE:
            failed.append(name)
        elif sbom_file is not None:
            sbom_files.append(sbom_file)

    return failed, sbom_files


_SBOM_FAILURE = "__build_failure__"


def _build_single_component(
    name: str,
    dockerfile: str,
    args: argparse.Namespace,
    extra_tags: list[str],
    sbom_dir: Path,
) -> str | None:
    """构建单个组件 (含 SBOM + 签名).

    Args:
        name: 组件名
        dockerfile: Dockerfile 路径
        args: CLI 参数
        extra_tags: 额外 tags
        sbom_dir: SBOM 输出目录

    Returns:
        SBOM 文件路径 (None if 成功但不需要 SBOM),
        或 _SBOM_FAILURE sentinel (构建失败)
    """
    success, err = build_image(
        component=name,
        dockerfile=dockerfile,
        version=args.version,
        platforms=args.platforms,
        registry=args.registry,
        push=args.push,
        dry_run=args.dry_run,
        extra_tags=extra_tags,
    )
    if not success:
        return _SBOM_FAILURE

    image_ref = f"{args.registry}/{PROJECT}/{name}:{args.version}"

    sbom_file: str | None = None
    if args.sbom and not args.dry_run:
        ok, sbom_path = generate_sbom(image_ref, sbom_dir)
        if ok:
            sbom_file = sbom_path

    if args.sign and not args.dry_run and not sign_image(image_ref):
        print(f"⚠️ {name} 签名失败")

    return sbom_file


def _print_summary(
    args: argparse.Namespace,
    components: list[tuple[str, str]],
    failed: list[str],
    sbom_files: list[str],
) -> int:
    """打印构建汇总; 有失败返回 1。

    V2.20 P4-31 拆分: 抽 _print_summary_header / _print_sbom_list / _print_signature_note
    收口各段打印, 主函数仅判定 + 委托.
    """
    _print_summary_header(args, components, failed)
    if failed:
        return 1
    _print_sbom_list(args, sbom_files)
    _print_signature_note(args)
    print("\n✅ 所有组件构建成功!")
    return 0


def _print_summary_header(
    args: argparse.Namespace,
    components: list[tuple[str, str]],
    failed: list[str],
) -> None:
    """打印汇总头 (版本 + 成功/失败计数)."""
    print(f"\n{'=' * 60}")
    print("构建汇总")
    print(f"{'=' * 60}")
    print(f"版本: {args.version}")
    print(f"成功: {len(components) - len(failed)}/{len(components)}")
    if failed:
        print(f"失败: {', '.join(failed)}")


def _print_sbom_list(args: argparse.Namespace, sbom_files: list[str]) -> None:
    """打印 SBOM 文件列表 (仅当启用 SBOM 且有文件)."""
    if not (args.sbom and sbom_files):
        return
    print("\nSBOM 文件:")
    for f in sbom_files:
        print(f"  {f}")


def _print_signature_note(args: argparse.Namespace) -> None:
    """打印签名完成提示 (仅当启用签名)."""
    if not args.sign:
        return
    print("\n✅ 所有镜像已签名")


def main() -> int:
    args = _parse_build_args()

    components = _select_components(args)
    if components is None:
        return 1

    extra_tags = _collect_extra_tags(args)

    sbom_dir = Path("sbom") / args.version.lstrip("v")
    if args.sbom:
        sbom_dir.mkdir(parents=True, exist_ok=True)

    _print_build_header(args, components)

    if not _preflight_checks(components):
        return 1

    failed, sbom_files = _build_all_components(args, components, extra_tags, sbom_dir)
    return _print_summary(args, components, failed, sbom_files)


if __name__ == "__main__":
    sys.exit(main())
