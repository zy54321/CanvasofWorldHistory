# -*- coding: utf-8 -*-
"""D2 跨文档字段与枚举一致性"""
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
def txt(f): return open(os.path.join(BASE,f),encoding='utf-8').read()

print("### D2-1 record_scope 枚举值：connection 作为枚举值命中 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'connection' in l and ('record_scope' in l or "IN (" in l or '枚举' in l or '4 值' in l or '5 值' in l or 'edge' in l):
            print(f"  {f}:L{i} {l.strip()[:170]}")

print("\n### D2-1b 'connection' 全量命中统计（区分源端概念名 vs 枚举值） ###")
for f in FILES:
    n=sum(1 for l in L(f) if 'connection' in l)
    print(f"  {f:46s} {n}")

print("\n### D2-2 evidence_role：place_record 命中 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'place_record' in l: print(f"  {f}:L{i} {l.strip()[:170]}")

print("\n### D2-3 liveness 8 值 & record_status 3 值 ###")
LIV=['merged','manual','active','mixed_inactive','all_sources_absent','all_sources_rolled_back','quarantined_only','orphaned']
for f in FILES:
    T=txt(f)
    miss=[v for v in LIV if v not in T]
    print(f"  {f:46s} liveness 缺: {miss if miss else '无 ✅'}")
print("  --- record_status 值域 ---")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'record_status' in l and ('IN (' in l or '3 值' in l or '值域' in l):
            print(f"    {f}:L{i} {l.strip()[:180]}")

print("\n### D2-4 枚举：time_bound_type 7 值 / derivation_kind 3 值 / inactive_reason 3 / issue_type 19 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if re.search(r'time_bound_type',l) and re.search(r'7 值|七值|IN \(',l):
            print(f"  [tbt] {f}:L{i} {l.strip()[:170]}")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'derivation_kind' in l and re.search(r'3 值|三值|IN \(',l):
            print(f"  [dk]  {f}:L{i} {l.strip()[:170]}")
