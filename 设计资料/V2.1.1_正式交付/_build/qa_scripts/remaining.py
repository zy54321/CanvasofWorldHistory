# -*- coding: utf-8 -*-
import re,os,csv
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
def T(f): return open(os.path.join(BASE,f),encoding='utf-8').read()

print("### D2-12 三视图字段名一致性 + inactive_at 落点 ###")
V={'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active','source_inactive_reason','child_table','child_row_id','child_record_status','child_rejected_by','is_anchor','is_canonical_row'],
   'v_place_liveness':['place_id','dataset_id','grain_key','record_status','manual_rejected_rows','distinct_inactive_reasons','liveness'],
   'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows','to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total','derivation_kind','all_children_rejected']}
for v,cols in V.items():
    miss={f:[c for c in cols if c not in T(f)] for f in FILES}
    miss={k:x for k,x in miss.items() if x}
    print(f"  {v:22s} 缺列文件: {miss if miss else '无（7 文件全覆盖）✅'}")
print("\n  --- inactive_at / inactive_in_batch_id 落点 ---")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'inactive_at' in l and ('source_record' in l or '落点' in l or 'sr.' in l or '视图加' in l):
            print(f"    {f}:L{i} {l.strip()[:185]}")

print("\n### D4-8 不得为凑数新增台账类型 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'source_metadata_incomplete' in l or ('凑' in l and '类型' in l):
            print(f"  {f}:L{i} {l.strip()[:185]}")

print("\n### D4-9 STOP_AUTO 三份一致 ###")
for f in ["CORE_DATA_MODEL_V2.1.1.md","IMPORT_RULES_V2.1.1.md","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md"]:
    for i,l in enumerate(L(f),1):
        if 'STOP_AUTO' in l and ('SKIP_UPDATE' in l or 'duplicate_external_id' in l):
            print(f"  {f}:L{i} {l.strip()[:185]}")

print("\n### D4-11 MCGD 最小 NameID / 643 按 parent_external_id 建点 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if '643' in l and ('NameID' in l or 'parent_external_id' in l or '按组' in l):
            print(f"  {f}:L{i} {l.strip()[:180]}")

print("\n### D4-12 rejected_by 两列 + 值域 auto/manual ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'rejected_by' in l and ('auto' in l and 'manual' in l):
            print(f"  {f}:L{i} {l.strip()[:180]}")

print("\n### D5-3 覆盖率 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if '覆盖率' in l:
            print(f"  {f}:L{i} {l.strip()[:190]}")
