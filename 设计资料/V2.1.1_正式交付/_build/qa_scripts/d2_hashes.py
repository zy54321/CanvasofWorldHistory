# -*- coding: utf-8 -*-
"""D2-5/6/7/8/9/10/11 机械验证"""
import re,os,hashlib,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
def T(f): return open(os.path.join(BASE,f),encoding='utf-8').read()

print("### D2-7 content_hash 规范串自行重算 ###")
SPEC = "sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))"
print(f"  规范串 len = {len(SPEC)}  (判据值 85) {'✅' if len(SPEC)==85 else '❌'}")
print(f"  sha1(规范串) = {hashlib.sha1(SPEC.encode()).hexdigest()}")
print(f"  判据值       = 9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5")
print(f"  一致: {'✅' if hashlib.sha1(SPEC.encode()).hexdigest()=='9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5' else '❌'}")
print("\n  --- 各文件规范串出现次数（逐字） ---")
for f in FILES:
    print(f"    {f:46s} {T(f).count(SPEC)}")
print("\n  --- 旧 md5 版 content_hash 串命中（应为 0） ---")
OLD=["md5(json.dumps(payload","hashlib.md5(payload","md5( canonical_json(","content_hash = md5"]
for o in OLD:
    h=[(f,i) for f in FILES for i,l in enumerate(L(f),1) if o in l]
    print(f"    [{o}] 命中={len(h)} {h[:5]}")

print("\n### D2-8 issue_fingerprint md5 串 ###")
FP="md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value))"
for f in FILES:
    n=T(f).count(FP)
    print(f"    {f:46s} 逐字出现={n}")
print("  --- ALG-1 声明检索 ---")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'ALG-1' in l and ('不可互换' in l or '并存' in l or '不可统一' in l):
            print(f"    {f}:L{i} {l.strip()[:190]}")

print("\n### D2-5 五段业务键逐字 ###")
KEY="(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)"
for f in FILES:
    print(f"    {f:46s} 逐字={T(f).count(KEY)}")
print("  --- 四段旧键 (dataset_id, record_scope, external_id, duplicate_ordinal) 命中 ---")
K4="(dataset_id, record_scope, external_id, duplicate_ordinal)"
for f in FILES:
    n=T(f).count(K4)
    if n: print(f"    {f:46s} {n}")
print("  --- UQ/UNIQUE 行全员 ---")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'UNIQUE' in l and 'dataset_id' in l:
            print(f"    {f}:L{i} {l.strip()[:170]}")

print("\n### D2-6 parent_external_id 哨兵 ###")
for f in FILES:
    for i,l in enumerate(L(f),1):
        if 'parent_external_id' in l and ('NULL' in l or '空串' in l or "哨兵" in l):
            print(f"    {f}:L{i} {l.strip()[:175]}")
