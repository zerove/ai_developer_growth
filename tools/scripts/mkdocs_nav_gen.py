#!/usr/bin/env python3
"""MkDocs nav 生成器 —— case-studies/ 树 → 权威 nav 段（树↔nav 永同源,手写漂移=0）
用法: python3 tools/scripts/mkdocs_nav_gen.py   # 从 case-studies/ 树生成 nav 段(打印)
"""
import subprocess, os, re, sys
R = subprocess.run(["git","rev-parse","--show-toplevel"],capture_output=True,text=True).stdout.strip(); os.chdir(R)
def G(*a,**k): return subprocess.run(["git"]+list(a),capture_output=True,text=True,**k)
cs = sorted(blob for blob in
            [l for l in G("ls-tree","-r","--name-only","origin/master").stdout.splitlines() if l.startswith("case-studies/")]
            if blob.endswith(".md"))
seg = "  - Case Studies:
"
for c in cs:
    name = os.path.basename(c)[:-3].replace("-", " ").title()
    seg += f"    - {name}: {c}\n"
print(seg, end="")
