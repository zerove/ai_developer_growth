#!/usr/bin/env python3
"""MkDocs strict 分片复验器 —— case-studies 48 树调 6 片,每片本地 strict build(<60s)
用法: python3 tools/scripts/mkdocs_strict_shards.py [--shards N]
产出: 每片 strict rc;全片 rc=0 → 本地 strict 绿 = 1621 断链本地终验(不再押 CI)
"""
import subprocess, os, sys, pathlib, tempfile
R = subprocess.run(["git","rev-parse","--show-toplevel"],capture_output=True,text=True).stdout.strip(); os.chdir(R)
def G(*a,**k): return subprocess.run(["git"]+list(a),capture_output=True,text=True,**k)
def blob(rel): return G("show",f"origin/master:{rel}").stdout
cs = [l for l in G("ls-tree","-r","--name-only","origin/master").stdout.splitlines() if l.startswith("case-studies/") and l.endswith(".md")]
N = int(sys.argv[sys.argv.index("--shards")+1]) if "--shards" in sys.argv else 6
mk = blob("mkdocs.yml")
# 每片 = 完整 mkdocs.yml, nav 的 case-studies 段只含本片子集 → strict 只解析本片可达面
import re
def mkdocs_for(chunk):
    nw = mk
    seg = "  - Case Studies:\n"
    for c in chunk: seg += f"    - {os.path.basename(c)[:-3].replace('-',' ').title()}: {c}\n"
    nw = re.sub(r"(?ms)  - Case Studies:.*?(?=^  - |\Z)", seg, nw, count=1)
    return nw
ok = bad = 0
with tempfile.TemporaryDirectory() as td:
    for i in range(N):
        chunk = cs[i::N]
        with open(f"{td}/mkdocs.yml","w") as f: f.write(mkdocs_for(chunk))
        b = subprocess.run(["mkdocs","build","--strict","-f",f"{td}/mkdocs.yml"],capture_output=True,text=True)
        if b.returncode==0: ok+=1
        else:
            bad+=1
            w = [l for l in (b.stdout+b.stderr).splitlines() if "WARNING" in l and ("path" in l.lower() or "link" in l.lower())]
            print(f"  片{i}: rc={b.returncode} | WARNING {len(w)}")
    print(f"── strict 分片: ✅ {ok}/{N} 片绿{' → 1621 本地终绿' if ok==N and bad==0 else f' | 残留断链面: {bad} 片(续修)'} ──")
