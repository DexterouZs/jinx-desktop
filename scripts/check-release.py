#!/usr/bin/env python3
"""Check source release hygiene; prints paths/categories, never matched secrets."""
from pathlib import Path
import re
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
patterns={
    'GitHub credential':r'gh[pousr]_[A-Za-z0-9]{25,}',
    'API secret':r'sk-[A-Za-z0-9_-]{25,}',
    'private key':r'-----BEGIN [A-Z ]*PRIVATE KEY',
    'owner home path':r'/home/davidsflow',
    'household subnet':r'192\.168\.178\.\d+',
}
failures=[]
if (root/'.git').exists():
    files=[root/x for x in subprocess.check_output(['git','-C',root,'ls-files'],text=True).splitlines()]
else:
    files=[p for p in root.rglob('*') if p.is_file() and not any(x in p.relative_to(root).parts for x in ('.git','__pycache__','dist'))]
for p in files:
    rel=p.relative_to(root)
    if any(x in rel.parts for x in ('personal-assets','node_modules','.venv','backups','state')) or p.suffix in ('.key','.pem','.sqlite3','.db','.wav','.gguf','.glb','.onnx'):
        failures.append((str(rel),'private/runtime file'))
    if p.stat().st_size>5*1024**2:failures.append((str(rel),'unexpected large source file'))
    try:text=p.read_text()
    except UnicodeDecodeError:continue
    # This checker contains the intentionally forbidden patterns themselves.
    if p==Path(__file__).resolve():continue
    for name,pattern in patterns.items():
        if re.search(pattern,text):failures.append((str(rel),name))
for filename,reason in failures:print(filename+': '+reason)
if failures:sys.exit(1)
print('Release hygiene passed:',len(files),'source files; no matched secrets or private runtime assets.')
