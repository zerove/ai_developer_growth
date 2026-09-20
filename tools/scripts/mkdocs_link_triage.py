#!/usr/bin/env python3
"""MkDocs 断链分型器 —— strict build 输出按 断链类型 归因计数
用法: mkdocs build --strict 2>&1 | python3 tools/scripts/mkdocs_link_triage.py
产出: 类型 × 计数（file-missing / nav-gap / rel-escape / 其它）
"""
import sys, re
from collections import Counter
c = Counter()
pat = {
 "nav-gap": re.compile(r"nav", re.I),
 "rel-escape": re.compile(r"\.\./", re.I),
}
for l in sys.stdin:
    if "WARNING" not in l: continue
    low = l.lower()
    if "source" in low and ("docs/") in low: ty = "rel-escape"
    elif "case-studies" in low and ("link" in low or "path" in low or "target" in low): ty = "nav-gap"
    else: ty = "other"
    c[ty] += 1
n = sum(c.values())
print(f"── 断链分型: 总 {n} 条 | " + " | ".join(f"{k}={v}" for k,v in c.most_common()))
if c["nav-gap"] and not c["rel-escape"]: print("    · 全 nav-gap → 根因=nav 未挂 case-studies 树(文件权威全在) → 修=nav 挂树(已落)")
elif c["rel-escape"]: print("    · rel-escape 存在 → 存相对链上抛(存量) → 修=nav 挂树后 strict 重判")
