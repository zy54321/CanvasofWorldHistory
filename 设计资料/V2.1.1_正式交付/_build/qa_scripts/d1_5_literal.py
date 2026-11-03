# -*- coding: utf-8 -*-
"""D1-5 ③ 字面层：许可字面词逐处 + 是否带【留痕】+ 语境分类"""
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
LIT=['attribution_text','citation_text','licence_unconfirmed','license_url','license_evidence',
     'license_id','redistributable','attribution_required','modification_note_required',
     'overlay_license_id','license_verified_at','license_status','acquisition_method','place_record']
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
tot=0; no_trace=[]
for f in FILES:
    hits=[]
    for i,l in enumerate(L(f),1):
        for w in LIT:
            if w in l:
                trace='【留痕' in l
                hits.append((i,w,trace,l.strip()[:160]))
                if not trace: no_trace.append((f,i,w,l.strip()[:170]))
    print(f"\n--- {f}: {len(hits)} 处（未带【留痕】{sum(1 for h in hits if not h[2])}） ---")
    for h in hits[:30]: print(f"  L{h[0]:5d} {'✅留痕' if h[2] else '⚠️无痕'} [{h[1]}] {h[3]}")
    tot+=len(hits)
print(f"\n合计字面命中 {tot}；未标【留痕】 {len(no_trace)}")
print("\n### 未标【留痕】逐处清单 ###")
for x in no_trace: print(f"  {x[0]}:L{x[1]} [{x[2]}] {x[3]}")
