# -*- coding: utf-8 -*-
import re, os, sys, io
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = ["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
         "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
         "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def lines(f):
    return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')

print("### B-1 硬标准：全库 grep ###")
pats = ['<canonical', 'FALSE AS is_canonical_row', 'JOIN source_record']
for p in pats:
    hits=[]
    for f in FILES:
        for i,l in enumerate(lines(f),1):
            if p in l: hits.append((f,i,l.strip()[:140]))
    print(f"[{p}] 命中={len(hits)}")
    for h in hits[:20]: print("   ",h[0],h[1],h[2])
print()
print("### B-1 补充：FALSE 相关 is_canonical 任意写法 ###")
for f in FILES:
    for i,l in enumerate(lines(f),1):
        if 'is_canonical_row' in l and re.search(r'FALSE|false', l):
            print("  ",f,i,l.strip()[:160])
print()
print("### B-3：'不可能并列' 命中 ###")
for f in FILES:
    for i,l in enumerate(lines(f),1):
        if '不可能并列' in l: print("  ",f,i,l.strip()[:160])
