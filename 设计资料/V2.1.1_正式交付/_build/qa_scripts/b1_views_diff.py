# -*- coding: utf-8 -*-
"""B-1 第二部分：DP §7.1/§7.2 与 CORE §5.10.1/§5.10.2 逐字比对"""
import os,re,difflib,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def blocks(f):
    L=open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
    incode=False; out=[]; start=None; buf=[]
    for i,l in enumerate(L,1):
        m=re.match(r'^\s*```(\w*)',l)
        if m and not incode:
            incode=True; start=i; buf=[]; continue
        if incode and re.match(r'^\s*```\s*$',l):
            out.append(dict(start=start,end=i,lines=buf[:])); incode=False; continue
        if incode: buf.append(l)
    return L,out

core_L, core_B = blocks("CORE_DATA_MODEL_V2.1.1.md")
dp_L, dp_B = blocks("DATA_PROVENANCE_V2.1.1.md")

def norm(ls):
    # 去掉纯注释/空白差异，保留结构
    r=[]
    for l in ls:
        s=l.strip()
        if not s: continue
        r.append(re.sub(r'\s+',' ',s))
    return r

# 定位含 CREATE OR REPLACE VIEW 的块
def find_view(bl, name):
    for b in bl:
        txt='\n'.join(b['lines'])
        if name in txt and ('CREATE' in txt.upper() or 'SELECT' in txt.upper()):
            yield b

for vname in ['v_place_evidence','v_place_liveness','v_place_time_span']:
    print("="*70); print("VIEW:",vname)
    cb=[b for b in find_view(core_B, vname)]
    db=[b for b in find_view(dp_B, vname)]
    print("CORE blocks:",[(b['start'],b['end']) for b in cb])
    print("DP   blocks:",[(b['start'],b['end']) for b in db])
    if cb and db:
        a=norm(cb[0]['lines']); b_=norm(db[0]['lines'])
        print("CORE 有效行数:",len(a)," DP 有效行数:",len(b_))
        d=list(difflib.unified_diff(a,b_,fromfile=f'CORE L{cb[0]["start"]}',tofile=f'DP L{db[0]["start"]}',lineterm='',n=1))
        if not d: print(">>> 逐字一致（去空白/注释后）: TRUE")
        else:
            print(">>> 差异行数:",len([x for x in d if x.startswith(('+','-')) and not x.startswith(('+++','---'))]))
            for x in d[:80]: print("   ",x[:180])
    print()
