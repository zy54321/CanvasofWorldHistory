# -*- coding: utf-8 -*-
"""D6-1 口径词：正文叙述中孤立行数（无口径词）扫描"""
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","IMPORT_RULES_V2.1.1.md","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md","DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
QUALS=['暂存原始','暂存态','隔离后','预计入库','入库口径','暂存态干跑','活性','入库后','暂存']
NUMS=['19,039','47,503','18,103','12,631','29,391','12,831','47,499','18,101','29,388','17,469','8,682','8,218','53,137','53,103','1,570','1,505']
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
print("### D6-1 正文行（非表格）中出现权威数字但 80 字符内无口径词 ###")
tot=0
for f in FILES:
    hits=[]
    for i,l in enumerate(L(f),1):
        s=l.strip()
        if not s or s.startswith('|') or s.startswith('```'): continue   # 表格行由列头声明口径，豁免
        for n in NUMS:
            for m in re.finditer(re.escape(n),s):
                win=s[max(0,m.start()-60):m.end()+60]
                if not any(q in win for q in QUALS):
                    hits.append((i,n,s[:170]))
    print(f"\n  --- {f} : {len(hits)} 处 ---")
    for h in hits[:40]: print(f"    L{h[0]} [{h[1]}] {h[2]}")
    tot+=len(hits)
print(f"\n  合计可疑 = {tot}")
