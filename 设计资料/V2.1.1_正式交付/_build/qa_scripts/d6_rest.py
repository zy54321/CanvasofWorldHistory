# -*- coding: utf-8 -*-
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
def T(f): return open(os.path.join(BASE,f),encoding='utf-8').read()

print("### D6-2 权威数字 N01–N18 表（CORE §9.2） ###")
for i,l in enumerate(L("CORE_DATA_MODEL_V2.1.1.md"),1):
    if 1463<=i<=1500 and l.strip(): print(f"  L{i} {l[:210]}")

print("\n### D6-3 不得直读暂存时间列判 derivation_kind / no_evidence 的告警 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if ('derivation_kind' in l or 'no_evidence' in l) and ('不得直读' in l or 'H2' in l or '偏低 65' in l or '含 connection' in l):
            print(f"  {f}:L{i} {l.strip()[:200]}")

print("\n### D6-5 8,682（口径 A）/ 8,218（口径 B） ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if '8,682' in l or '8,218' in l:
            print(f"  {f}:L{i} {l.strip()[:200]}")

print("\n### D6-6 / D6-7 施工验证清单 U3/U4/U5/U12/U13/U14/U15/U16/U18 ###")
for u in ['U3','U4','U5','U12','U13','U14','U15','U16','U18']:
    hit=[f for f in FILES if re.search(r'\b'+u+r'\b',T(f))]
    print(f"  {u:4s} 出现在 {len(hit)} 个文件: {hit}")

print("\n### D6-8 两条施工级硬提醒 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'normalize.py:306' in l:
            print(f"  [H1] {f}:L{i} {l.strip()[:190]}")
print()
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'H2' in l and ('直读' in l or 'valid_from' in l):
            print(f"  [H2] {f}:L{i} {l.strip()[:190]}")
