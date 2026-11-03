# -*- coding: utf-8 -*-
"""区分 SQL 代码块内 vs 正文叙述，避免把'原缺陷留痕'误判为可执行占位符。"""
import re,os,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","IMPORT_RULES_V2.1.1.md","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md","DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
def scan(f):
    L=open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
    incode=False; codestart=0; blocks=[]  # (start,end,lang)
    for i,l in enumerate(L,1):
        m=re.match(r'^\s*```(\w*)',l)
        if m and not incode:
            incode=True; codestart=i; lang=m.group(1).lower(); continue
        if incode and re.match(r'^\s*```\s*$',l):
            blocks.append((codestart,i,lang)); incode=False
    return L,blocks
PATS=['<canonical','FALSE AS is_canonical_row','<...>','...']
report={}
for f in FILES:
    L,blocks=scan(f)
    def inblock(n):
        for s,e,lang in blocks:
            if s<n<e: return lang
        return None
    rep={}
    for p in PATS:
        incode_hits=[]; prose_hits=[]
        for i,l in enumerate(L,1):
            if p in l:
                lang=inblock(i)
                (incode_hits if lang is not None else prose_hits).append((i,lang,l.strip()[:110]))
        rep[p]=dict(code=len(incode_hits), prose=len(prose_hits), code_hits=incode_hits, prose_hits=[ (a,b) for a,b,c in prose_hits])
    report[f]=dict(nblocks=len(blocks), blocks=[(s,e,g) for s,e,g in blocks], pats=rep)
print(json.dumps(report,ensure_ascii=False,indent=1))
