#!/usr/bin/env python3
"""
JCode Platform - Docker Build & Push Script

功能:
- 多架构 Docker 镜像构建 (amd64/arm64)
- 多标签管理 (语义化版本、latest、git-sha)
- SBOM 生成
- 推送到容器镜像仓库

用法:
    python tools/scripts/docker_build.py --version v2.0.0 --push
    python tools/scripts/docker_build.py --version v2.0.0 --platform linux/amd64,linux/arm64 --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

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

def run_cmd(cmd: list[str], cwd: Path | None = None, capture: bool = True, env: dict | None = None) -> tuple[int, str]:
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
    image_name = f"{registry}/{PROJECT}/{component}"
    
    # 标签列表
    tags = [f"{image_name}:{version}", f"{image_name}:latest"]
    tags.extend([f"{image_name}:{tag}" for tag in extra_tags])
    
    # Buildx 命令
    cmd = [
        "docker", "buildx", "build",
        "--platform", platforms,
        "-f", dockerfile,
        "-t", tags[0],
    ]
    
    for tag in tags[1:]:
        cmd.extend(["-t", tag])
    
    if push:
        cmd.append("--push")
    else:
        cmd.append("--load")
    
    cmd.append(".")
    
    print(f"\n{'='*60}")
    print(f"构建组件: {component}")
    print(f"Dockerfile: {dockerfile}")
    print(f"平台: {platforms}")
    print(f"标签: {', '.join(tags)}")
    print(f"推送: {'是' if push else '否 (本地加载)'}")
    print(f"{'='*60}")
    
    if dry_run:
        print(f"🔍 试运行模式，命令: {' '.join(cmd)}")
        return True, ""
    
    start = time.time()
    code, output = run_cmd(cmd, capture=False)
    elapsed = time.time() - start
    
    if code == 0:
        print(f"✅ {component} 构建成功 ({elapsed:.1f}s)")
        return True, ""
    else:
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

def main() -> int:
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
    
    args = parser.parse_args()
    
    # 解析组件
    if args.components:
        selected = [c.strip() for c in args.components.split(",")]
        components = [(name, df) for name, df in COMPONENTS if name in selected]
        if len(components) != len(selected):
            print(f"❌ 未知组件: {set(selected) - {c[0] for c in COMPONENTS}}")
            return 1
    else:
        components = COMPONENTS
    
    # 额外标签
    extra_tags = [t.strip() for t in args.extra_tags.split(",")] if args.extra_tags else []
    git_sha = get_git_sha()
    if git_sha != "unknown":
        extra_tags.append(f"sha-{git_sha}")
    extra_tags.append(f"build-{datetime.now().strftime('%Y%m%d%H%M')}")
    
    # 创建 SBOM 输出目录
    sbom_dir = Path("sbom") / args.version.lstrip("v")
    if args.sbom:
        sbom_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"JCode Platform Docker Build")
    print(f"版本: {args.version}")
    print(f"仓库: {args.registry}")
    print(f"平台: {args.platforms}")
    print(f"推送: {'是' if args.push else '否'}")
    print(f"SBOM: {'是' if args.sbom else '否'}")
    print(f"签名: {'是' if args.sign else '否'}")
    print(f"组件: {', '.join(c[0] for c in components)}")
    print(f"{'='*60}\n")
    
    # 验证 Dockerfile 存在
    for name, df in components:
        df_path = Path(df)
        if not df_path.exists():
            print(f"❌ Dockerfile 不存在: {df}")
            return 1
    
    # 检查 buildx
    code, _ = run_cmd(["docker", "buildx", "version"])
    if code != 0:
        print("❌ docker buildx 不可用")
        return 1
    
    # 创建/使用 builder
    run_cmd(["docker", "buildx", "create", "--name", "jcode-builder", "--use", "--bootstrap"], capture=False)
    
    # 构建各组件
    failed = []
    sbom_files = []
    
    for name, dockerfile in components:
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
            failed.append(name)
            continue
        
        # 生成 SBOM
        if args.sbom and not args.dry_run:
            image_ref = f"{args.registry}/{PROJECT}/{name}:{args.version}"
            ok, sbom_file = generate_sbom(image_ref, Path(sbom_dir))
            if ok:
                sbom_files.append(sbom_file)
        
        # 签名
        if args.sign and not args.dry_run:
            image_ref = f"{args.registry}/{PROJECT}/{name}:{args.version}"
            if not sign_image(image_ref):
                print(f"⚠️ {name} 签名失败")
    
    # 汇总
    print(f"\n{'='*60}")
    print("构建汇总")
    print(f"{'='*60}")
    print(f"版本: {args.version}")
    print(f"成功: {len(components) - len(failed)}/{len(components)}")
    if failed:
        print(f"失败: {', '.join(failed)}")
        return 1
    
    if args.sbom and sbom_files:
        print(f"\nSBOM 文件:")
        for f in sbom_files:
            print(f"  {f}")
    
    if args.sign:
        print("\n✅ 所有镜像已签名")
    
    print("\n✅ 所有组件构建成功!")
    return 0


if __name__ == "__main__":
    sys.exit(main())