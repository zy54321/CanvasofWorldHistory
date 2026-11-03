# -*- coding: utf-8 -*-
"""D1-5 三层扫描：① 功能层 LICENSE_GATE=0 ② 结构层无许可列 ③ 字面层需【留痕】"""
import re,os,csv,io,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def lines(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')

print("="*70)
print("### ① 功能层（硬）：LICENSE_GATE 命中数必须 = 0 ###")
tot=0
for f in FILES:
    h=[(i,l.strip()[:140]) for i,l in enumerate(lines(f),1) if 'LICENSE_GATE' in l]
    tot+=len(h)
    print(f"  {f:46s} 命中={len(h)}")
    for x in h: print(f"      L{x[0]}: {x[1]}")
print(f"  >>> 合计 = {tot}  {'PASS ✅' if tot==0 else 'FAIL ❌'}")

print("\n### ①b 功能层扩展：许可门禁 / 授权判断 关键短语 ###")
GATE=['许可门禁','授权判断','许可判定','redistributable 判定','license_status','gate_license','许可检查','许可校验']
for p in GATE:
    h=[(f,i,l.strip()[:120]) for f in FILES for i,l in enumerate(lines(f),1) if p in l]
    print(f"  [{p}] 命中={len(h)}")
    for x in h[:5]: print(f"      {x[0]}:L{x[1]} {x[2]}")

print("\n"+"="*70)
print("### ② 结构层（硬）：表列定义中不得出现许可列 ###")
LIC=['default_license_id','default_redistributable','license_url','license_evidence',
     'attribution_text','citation_text','licence_unconfirmed','license_status','redistributable']
# CSV target_column 检查
p=os.path.join(BASE,"FIELD_MAPPING_V2.1.1.csv")
rows=list(csv.DictReader(open(p,encoding='utf-8-sig')))
print(f"  FIELD_MAPPING 行数={len(rows)}  列头={list(rows[0].keys())}")
bad=[r for r in rows if any(k in (r.get('target_column') or '').lower() for k in LIC)]
print(f"  target_column 含许可列 = {len(bad)}  {'PASS ✅' if not bad else 'FAIL ❌'}")
for b in bad[:10]: print("     ",b)
bad2=[r for r in rows if any(k in (r.get('staging_column') or '').lower() for k in LIC)]
print(f"  staging_column 含许可列 = {len(bad2)}")
for b in bad2[:10]: print("     ",b)

print("\n  --- md 表格首列（列定义）中的许可列 ---")
for f in FILES:
    L=lines(f)
    hits=[]
    for i,l in enumerate(L,1):
        if l.startswith('|'):
            cell=re.sub(r'\*\*','',l.split('|')[1]).strip().strip('`').strip()
            if any(k.lower() in cell.lower() for k in LIC):
                hits.append((i,cell,l.strip()[:140]))
    print(f"  {f:46s} 列定义命中={len(hits)}")
    for x in hits: print(f"      L{x[0]} cell={x[1]!r} :: {x[2]}")
