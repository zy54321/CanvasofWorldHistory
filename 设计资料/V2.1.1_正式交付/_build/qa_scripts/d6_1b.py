# -*- coding: utf-8 -*-
"""D6-1 精化：加入 入库 口径词 + 箭头/算术闭合豁免，找真正孤立行数"""
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","IMPORT_RULES_V2.1.1.md","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md","DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
QUALS=['暂存原始','暂存态','隔离后','预计入库','入库','活性','暂存','干跑','新增','变成','来源','条 content_hash','条哈希']
NUMS=['19,039','47,503','18,103','12,631','29,391','12,831','47,499','18,101','29,388','17,469','8,682','8,218','53,137','53,103','1,570','1,505','18,398','18,396','2,650','5,762','2,468','2,763','315','643']
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
print("### D6-1 精化扫描（正文行，窗口 90 字符） ###")
res=[]
for f in FILES:
    hits=[]
    for i,l in enumerate(L(f),1):
        s=l.strip()
        if not s or s.startswith('|') or s.startswith('```') or s.startswith('#'): continue
        for n in NUMS:
            for m in re.finditer(re.escape(n),s):
                win=s[max(0,m.start()-90):m.end()+90]
                if any(q in win for q in QUALS): continue
                hits.append((i,n,s[:200]))
    print(f"\n--- {f}: {len(hits)} 处 ---")
    for h in hits: print(f"  L{h[0]} [{h[1]}] {h[2]}")
    res+=hits
print("\n合计 =",len(res))
