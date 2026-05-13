#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""juhuo daily cleanup"""
import os, shutil, argparse
from pathlib import Path
from datetime import datetime, timedelta

JR = Path(__file__).parent.resolve()
WS = Path(os.environ.get('COPAW_WORKING_DIR', str(Path.home() / '.copaw')))
LD = JR / 'logs'
LD.mkdir(exist_ok=True)

def log(m):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t}] {m}")
    open(LD / 'cleanup.log', 'a', encoding='utf-8').write(f'[{t}] {m}\n')

def gs(p):
    if p.is_file(): return p.stat().st_size
    try: return sum(e.stat().st_size for e in p.rglob('*') if e.is_file())
    except: return 0

def fs(s):
    if s < 1024: return str(s) + 'B'
    if s < 1024*1024: return str(s/1024) + 'KB'
    if s < 1024**3: return str(s/(1024*1024)) + 'MB'
    return str(s/(1024**3)) + 'GB'

def rp(a, b):
    try: return str(a.relative_to(b))
    except: return str(a)

def c1(dry=True):
    d = WS / "workspaces"
    if not d.exists(): return 0, 0
    ps = ["_test*.py","*.tmp","temp_*","~*","*_fix_*.py","*_fix.py"]
    n = s = 0
    for wd in d.iterdir():
        if not wd.is_dir(): continue
        for p in ps:
            for f in wd.glob(p):
                if f.is_file():
                    if dry:
                        log('[DRY] ' + rp(f,d))
                    else:
                        f.unlink()
                        log('DEL ' + rp(f,d))
                    n += 1; s += gs(f)
    return n, s

def c2(dry=True, days=30):
    c = datetime.now() - timedelta(days=days)
    n = s = 0
    md = WS / "memory"
    if md.exists():
        for f in md.glob('*.md'):
            try:
                mt = datetime.fromtimestamp(f.stat().st_mtime)
                if mt < c:
                    if dry:
                        log('[DRY] ' + f.name)
                    else:
                        f.unlink()
                        log('DEL ' + f.name)
                    n += 1; s += gs(f)
            except: pass
    return n, s

def c3(dry=True, days=7):
    d = WS / "sessions"
    if not d.exists(): return 0, 0
    c = datetime.now() - timedelta(days=days)
    n = s = 0
    for f in d.rglob('*'):
        if not f.is_file(): continue
        if f.suffix not in ['.json','.jsonl']: continue
        try:
            mt = datetime.fromtimestamp(f.stat().st_mtime)
            if mt < c:
                if dry:
                    log('[DRY] ' + f.name)
                else:
                    f.unlink()
                    log('DEL ' + f.name)
                n += 1; s += gs(f)
        except: pass
    return n, s

def c4(dry=True):
    d = WS / "sessions"
    if not d.exists(): return 0, 0
    kw = ["dump","tmp","partial","bak","context_","state_","intermediate","_cache_","swp","swo"]
    n = s = 0
    for f in d.rglob('*'):
        if not f.is_file(): continue
        if f.suffix in ['.json','.jsonl']: continue
        nl = f.name.lower()
        if any(k in nl for k in kw):
            if dry:
                log('[DRY] dump: ' + f.name)
            else:
                f.unlink()
                log('DEL dump: ' + f.name)
            n += 1; s += gs(f)
    return n, s

def c5(dry=True):
    d = WS / 'workspaces'
    if not d.exists(): return 0, 0
    n = s = 0
    ap = ['*_article_text*','*_article_content*','*_text.txt','*_content.txt','*_raw.txt','*_scrape*.txt','*_crawl*.txt','*.article','*.scraped']
    for wd in d.iterdir():
        if not wd.is_dir(): continue
        for pt in ap:
            for f2 in wd.rglob(pt):
                if f2.is_file():
                    if dry:
                        log('[DRY] junk: ' + rp(f2,d))
                    else:
                        f2.unlink()
                        log('DEL junk: ' + rp(f2,d))
                    n += 1; s += gs(f2)
    co = datetime.now() - timedelta(days=60)
    cr = datetime.now() - timedelta(days=30)
    for wd in d.iterdir():
        ld = wd / 'learning'
        if not ld.exists(): continue
        for f2 in ld.rglob('*'):
            if not f2.is_file(): continue
            try:
                mt = datetime.fromtimestamp(f2.stat().st_mtime)
                at = datetime.fromtimestamp(f2.stat().st_atime)
                if mt < co and at < cr:
                    if dry:
                        log('[DRY] old learning: ' + rp(f2,d))
                    else:
                        f2.unlink()
                        log('DEL old learning: ' + rp(f2,d))
                    n += 1; s += gs(f2)
            except: pass
    seen = {}
    for wd in d.iterdir():
        md = wd / 'memory'
        if not md.exists(): continue
        for f2 in md.glob('*.md'):
            if not f2.is_file(): continue
            try:
                base = f2.stem
                mt = datetime.fromtimestamp(f2.stat().st_mtime)
                if base in seen:
                    op, om = seen[base]
                    if mt > om:
                        if dry:
                            log('[DRY] dup: ' + op.name + ' (keep ' + f2.name + ')')
                        else:
                            op.unlink()
                            log('DEL dup: ' + op.name + ' (keep ' + f2.name + ')')
                        n += 1; s += gs(op)
                        seen[base] = (f2, mt)
                else:
                    seen[base] = (f2, mt)
            except: pass
    for wd in d.iterdir():
        if not wd.is_dir(): continue
        for td in wd.rglob('temp*'):
            if td.is_dir():
                try:
                    if not any(td.iterdir()):
                        if dry:
                            log('[DRY] empty dir: ' + rp(td,d))
                        else:
                            td.rmdir()
                            log('DEL empty dir: ' + rp(td,d))
                        n += 1
                except: pass
    return n, s

def c6(dry=True, days=7):
    d = WS / 'tool_result'
    if not d.exists(): return 0, 0
    c = datetime.now() - timedelta(days=days)
    n = s = 0
    for f in d.rglob('*'):
        if not f.is_file(): continue
        try:
            mt = datetime.fromtimestamp(f.stat().st_mtime)
            if mt < c:
                if dry:
                    log('[DRY] tool result: ' + f.name[:40])
                else:
                    f.unlink()
                    log('DEL tool result: ' + f.name[:40])
                n += 1; s += gs(f)
        except: pass
    return n, s

def c7(dry=True):
    n = s = 0
    for sub in ['embedding_cache','file_store']:
        d = WS / sub
        if not d.exists(): continue
        for f in d.rglob('*'):
            if not f.is_file(): continue
            try:
                if f.stat().st_size > 10*1024*1024:
                    if dry:
                        log('[DRY] big cache: ' + f.name)
                    else:
                        f.unlink()
                        log('DEL big cache: ' + f.name)
                    n += 1; s += gs(f)
            except: pass
    return n, s

def c8(dry=True):
    n = s = 0
    for p in JR.rglob('__pycache__'):
        if p.is_dir():
            sz = gs(p)
            if dry:
                log('[DRY] pycache: ' + str(p.relative_to(JR)))
            else:
                shutil.rmtree(p)
                log('DEL pycache: ' + str(p.relative_to(JR)))
            n += 1; s += sz
    for p in JR.rglob('*.pyc'):
        if p.is_file():
            if dry:
                log('[DRY] pyc: ' + str(p.relative_to(JR)))
            else:
                p.unlink()
                log('DEL pyc: ' + str(p.relative_to(JR)))
            n += 1; s += gs(p)
    return n, s

def main():
    import argparse
    p = argparse.ArgumentParser(description='juhuo daily cleanup')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--days', type=int, default=7)
    a = p.parse_args()
    dry = a.dry_run
    log('=== Cleanup start ' + ('[DRY RUN]' if dry else '[LIVE]') + ' ===')
    td = ts = 0
    log('1. workspace temp files...')
    n, s = c1(dry); td += n; ts += s
    log('2. old memory logs (30d)...')
    n, s = c2(dry, 30); td += n; ts += s
    log('3. old sessions (' + str(a.days) + 'd)...')
    n, s = c3(dry, a.days); td += n; ts += s
    log('4. session dumps...')
    n, s = c4(dry); td += n; ts += s
    log('5. learning junk...')
    n, s = c5(dry); td += n; ts += s
    log('6. old tool results (' + str(a.days) + 'd)...')
    n, s = c6(dry, a.days); td += n; ts += s
    log('7. big caches (>10MB)...')
    n, s = c7(dry); td += n; ts += s
    log('8. Python caches...')
    n, s = c8(dry); td += n; ts += s
    log('=== Done: ' + str(td) + ' files, ' + fs(ts) + ' freed ===')
    if dry: log('Hint: run without --dry-run to actually delete')

if __name__ == '__main__':
    main()
