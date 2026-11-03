# -*- coding: utf-8 -*-
import re,os,csv
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')

print("### D1-1 / D1-2 目录清单 ###")
names=sorted(os.listdir(BASE))
for n in names: print("   ",n, "(dir)" if os.path.isdir(os.path.join(BASE,n)) else "")
EXP8=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
      "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
      "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md","V2.1.1_QA_REPORT.md"]
files=[n for n in names if os.path.isfile(os.path.join(BASE,n))]
for e in EXP8:
    print(f"   D1-1 {e:46s} {'存在 ✅' if e in files else '缺失'}")

print("\n### D1-4 FIELD_MAPPING 列头逐字 ###")
hdr=open(os.path.join(BASE,"FIELD_MAPPING_V2.1.1.csv"),encoding='utf-8-sig').readline().strip()
EXP_HDR="staging_table,staging_column,target_table,target_column,target_type,required,transform,enum_rule,notes"
print("  实测:",hdr)
print("  期望:",EXP_HDR)
print("  一致:", "✅" if hdr==EXP_HDR else "❌")

print("\n### D1-6 首部声明 V2.1.1 + 以 V0.2.2-r2 为权威依据（豁免 CSV） ###")
for f in FILES:
    head="\n".join(L(f)[:20])
    has_v211 = 'V2.1.1' in head
    has_r2 = ('V0.2.2-r2' in head) or ('V0.2.2' in head)
    print(f"  {f:46s} 首部含V2.1.1={has_v211}  含V0.2.2(⁻r2)={has_r2}  {'✅' if has_v211 and has_r2 else ('⚠️' if has_v211 else '❌')}")
    if not (has_v211 and has_r2):
        for i,l in enumerate(L(f)[:8],1): print(f"        L{i}: {l[:150]}")

print("\n### D3-9 旧 ER 图作废声明 ###")
for f in ["CORE_DATA_MODEL_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md","ER_DIAGRAM_V2.1.1.svg"]:
    for i,l in enumerate(L(f),1):
        if 'ER_DIAGRAM_V2.1.svg' in l and ('作废' in l):
            print(f"  {f}:L{i} {l.strip()[:200]}")

print("\n### D3-8 data_quality_issue 行数 12,831 + 三列 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if '12,831' in l:
            print(f"  {f}:L{i} {l.strip()[:190]}")
for c in ['first_batch_id','last_batch_id','occurrence_count']:
    n=sum(1 for f in FILES for l in L(f) if c in l)
    print(f"  {c:20s} 出现文件数={sum(1 for f in FILES if any(c in l for l in L(f)))}")

print("\n### D6-4 candidate_match 不得进权威数字表 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'candidate_match' in l and ('53,1' in l or '不进权威' in l or 'U18' in l):
            print(f"  {f}:L{i} {l.strip()[:190]}")
