import os, subprocess
os.chdir('E:/juhuo')
for f in ['_cleanup.py','_find3.py']:
    try: os.remove(f)
    except: pass

r = subprocess.run(['git','add','-A'], capture_output=True, text=True)
r2 = subprocess.run(['git','status','--short'], capture_output=True, text=True)
print(r2.stdout[:2000])

# commit
r3 = subprocess.run(['git','commit','-m','feat: P1双向矛盾处理+to_prompt结构化\n\n- generate(): 矛盾时L1降priority+L2升priority双向\n- to_prompt(): 改为[PROFILE: priority=X, source=Y, recency=Z, claim="...", flag=Z]格式\n- pipeline.py: 清理inject_biography/experiences/causal_memory死代码(325->265行)'],
                    capture_output=True, text=True)
print(r3.stdout[:500])
print(r3.stderr[:500])
