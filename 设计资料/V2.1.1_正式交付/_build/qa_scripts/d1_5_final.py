# -*- coding: utf-8 -*-
"""D1-5 ③ 终判：以「节级块」（## / ### 标题之间）为单位判定是否有【留痕】或整表声明"""
import re,os,collections
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","ER_DIAGRAM_V2.1.1.svg","IMPORT_RULES_V2.1.1.md",
       "FIELD_MAPPING_V2.1.1.csv","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md",
       "DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
LIT=['attribution_text','citation_text','licence_unconfirmed','license_url','license_evidence',
     'license_id','redistributable','attribution_required','modification_note_required',
     'overlay_license_id','license_verified_at','license_status','acquisition_method']
def secs(f):
    L=open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
    out=[]; start=1; buf=[]
    for i,l in enumerate(L,1):
        if re.match(r'^#{1,3}\s',l) and buf:
            out.append((start,i-1,buf[:])); start=i; buf=[]
        buf.append((i,l))
    if buf: out.append((start,len(L),buf))
    return out
print("### D1-5 ③ 节级留痕判定 ###")
bad=[]
for f in FILES:
    for s,e,buf in secs(f):
        body="\n".join(l for _,l in buf)
        if not any(w in body for w in LIT): continue
        has = '【留痕' in body
        # 四类语境关键词
        ctx = any(c in body for c in ['已删除列','明确不做','禁用词','删枚举值','不得重新引入','不重新引入','不新增'])
        hits=[(i,l) for i,l in buf if any(w in l for w in LIT)]
        mark='✅节内留痕' if has else ('⚠️仅语境无留痕' if ctx else '❌无留痕无语境')
        if not has:
            bad.append((f,s,e,ctx,len(hits)))
            print(f"  {mark} {f}:L{s}-L{e}  含字面词行数={len(hits)}")
            for i,l in hits[:4]: print(f"        L{i} {l.strip()[:130]}")
print(f"\n  无节级留痕的节数 = {len(bad)}")
print("  其中连四类语境也没有的节数 =", sum(1 for x in bad if not x[3]))
