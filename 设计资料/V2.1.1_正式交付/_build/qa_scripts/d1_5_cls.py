# -*- coding: utf-8 -*-
"""D1-5 ③ 字面层分类：区分「整表/整块已标留痕」与「完全无任何留痕标记」"""
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
LIT=['attribution_text','citation_text','licence_unconfirmed','license_url','license_evidence',
     'license_id','redistributable','attribution_required','modification_note_required',
     'overlay_license_id','license_verified_at','license_status','acquisition_method']
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
CTX=['已删除列','明确不做','禁用词','删枚举值','删除','作废','取消','不重新引入','不新增','不得','⛔','原设计','修改后']
print("### D1-5 ③ 逐处判定：语境是否属四类豁免 + 是否有留痕（本行 或 前后 3 行内） ###")
unmarked=[]
for f in FILES:
    lines=L(f); n=len(lines)
    for i,l in enumerate(lines,1):
        if not any(w in l for w in LIT): continue
        near="\n".join(lines[max(0,i-4):min(n,i+3)])
        has_trace = '【留痕' in near
        in_ctx = any(c in near for c in CTX)
        if not has_trace:
            unmarked.append((f,i,in_ctx,l.strip()[:150]))
print(f"  无留痕（本行±3 行内无【留痕）合计 = {len(unmarked)}")
print(f"  其中语境属四类（仅漏标留痕）= {sum(1 for x in unmarked if x[2])}")
print(f"  其中语境不属于四类（真风险）= {sum(1 for x in unmarked if not x[2])}")
print("\n--- 语境不属于四类（潜在真实缺陷） ---")
for x in unmarked:
    if not x[2]: print(f"  {x[0]}:L{x[1]} {x[3]}")
print("\n--- 属四类但漏【留痕】按文件统计 ---")
import collections
c=collections.Counter(x[0] for x in unmarked if x[2])
for k,v in c.items(): print(f"  {k:46s} {v}")
