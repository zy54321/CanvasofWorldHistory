# -*- coding: utf-8 -*-
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
def T(f): return open(os.path.join(BASE,f),encoding='utf-8').read()

print("### D2-9 place_grain 是 V2 既有列 / 不得出现「V2.1.1 新增」 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'place_grain' in l and ('新增' in l or '既有' in l or 'V2 既有' in l):
            print(f"  {f}:L{i} {l.strip()[:190]}")

print("\n### D2-10 「新列 +N」合计数扫描 ###")
pat=re.compile(r'新列\s*\*\*\+\d+\*\*|新列\s*\+\d+|新增\s*\*\*\+\d+\*\*\s*列|新视图派生列 \*\*\+\d+\*\*')
for f in FILES:
    for i,l in enumerate(L(f),1):
        if pat.search(l): print(f"  {f}:L{i} {l.strip()[:200]}")
print("  --- 「+N」一般形式（含列合计）---")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if re.search(r'\+\d+\s*列|列\s*\+\d+',l):
            print(f"  {f}:L{i} {l.strip()[:200]}")

print("\n### D2-11 约束 C01–C29 编号无缺失无重复 ###")
seen={}
for f in FILES:
    for m in re.finditer(r'\bC(\d{2})\b',T(f)):
        seen.setdefault(int(m.group(1)),set()).add(f)
missing=[n for n in range(1,30) if n not in seen]
print("  出现过的编号:",sorted(seen.keys()))
print("  缺失:",missing if missing else "无 ✅")
print("  超出 C29:",[n for n in seen if n>29] or "无 ✅")
print("\n  --- 「有效 27 / 可落库 24 / 断言级 3」口径 ---")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if re.search(r'有效\s*\*?\*?27|27\s*条|可落库\s*\*?\*?24|24\s*条|断言级|键级\s*3',l):
            print(f"    {f}:L{i} {l.strip()[:190]}")
