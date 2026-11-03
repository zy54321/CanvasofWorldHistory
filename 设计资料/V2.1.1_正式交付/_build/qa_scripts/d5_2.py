# -*- coding: utf-8 -*-
"""D5-2 每个 target_column 在 CORE 中真实存在；D5-5 不凭空补行"""
import csv,re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CL=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')
TAB={}; i=0; n=len(CL)
while i<n:
    m=re.match(r'^###\s+5\.\d+\s+`([a-z_]+)`',CL[i])
    if m:
        t=m.group(1); cols=[]; j=i+1
        while j<n and not re.match(r'^\|\s*列\s*\|',CL[j]): j+=1
        if j<n:
            k=j+2
            while k<n and CL[k].startswith('|'):
                c=re.sub(r'\*\*','',CL[k].split('|')[1]).strip().strip('`').strip()
                for p in re.split(r'\s*/\s*',c):
                    p=re.sub(r'\*\*','',p).strip().strip('`').strip()
                    if re.fullmatch(r'[a-z][a-z_0-9]*',p) and p not in cols: cols.append(p)
                k+=1
        TAB[t]=cols; i=j if j>i else i+1; continue
    i+=1
# 视图列
VL=CL
VIEWS={'v_place_evidence':[],'v_place_liveness':[],'v_place_time_span':[]}
for v in VIEWS:
    for idx,l in enumerate(VL):
        if l.strip().startswith('#### 5.10') and v in l:
            for m in re.finditer(r'^\|\s*(\d+)\s*\|\s*`([a-z_][a-z_0-9]*)`',"\n".join(VL[idx:idx+80]),re.M):
                VIEWS[v].append(m.group(2))
            break
ALL=dict(TAB); ALL.update(VIEWS)
rows=list(csv.DictReader(open(os.path.join(BASE,"FIELD_MAPPING_V2.1.1.csv"),encoding='utf-8-sig')))
print("### D5-2 target_column 是否在 CORE 真实存在 ###")
bad=[]
for r in rows:
    tt=(r['target_table'] or '').strip(); tc=(r['target_column'] or '').strip()
    if tc in ('(dropped)','-','') : continue
    if tt not in ALL:
        bad.append((tt,tc,'表名不在 CORE §5')); continue
    if tc not in ALL[tt]:
        bad.append((tt,tc,'列不在该表'))
print(f"  不合规行 = {len(bad)}  {'✅' if not bad else '❌'}")
for b in bad: print("    ",b)
print(f"\n  检过的 (target_table,target_column) 组合 = {len(set((r['target_table'],r['target_column']) for r in rows))}")
print("\n### D5-5 不凭空补行：staging_table 值域 ###")
import collections
c=collections.Counter(r['staging_table'] for r in rows)
for k,v in c.items(): print(f"   {k!r:34} {v}")
