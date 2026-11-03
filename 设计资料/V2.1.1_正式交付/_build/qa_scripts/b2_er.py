# -*- coding: utf-8 -*-
"""B-2 ER 图：XML 良构 + 四项 grep + 三视图齐 + data_source 6 列无许可列"""
import os,xml.etree.ElementTree as ET,re,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SVG=os.path.join(BASE,"ER_DIAGRAM_V2.1.1.svg")
raw=open(SVG,'rb').read()
txt=raw.decode('utf-8')
S=txt.split('\n')
print("### 1. XML 良构（ET.parse 实测） ###")
try:
    t=ET.parse(SVG); r=t.getroot()
    print("  ET.parse: OK ✅  root.tag =",r.tag)
    print("  元素总数:",len(list(r.iter())))
except Exception as e:
    print("  ET.parse 失败 ❌",e)

print("\n### 2. B-2 四项 grep（判据要求应全 0） ###")
for pat,expect in [('9 列',0),('许可默认值',0),('无变化',0),('时间戳',0)]:
    hits=[(i,l.strip()[:150]) for i,l in enumerate(S,1) if pat in l]
    print(f"  [{pat}] 命中={len(hits)} 期望={expect} -> {'PASS ✅' if len(hits)==expect else 'FAIL ❌'}")
    for h in hits[:6]: print("      L",h[0],h[1])

print("\n### 3. 三视图齐 + v_place_evidence 在 ###")
for v in ['v_place_evidence','v_place_liveness','v_place_time_span']:
    print(f"  {v:20s} 出现次数={txt.count(v)}  {'✅' if txt.count(v)>0 else '❌'}")

print("\n### 4. 'published' 命中（D3-3: 应 0） ###")
h=[(i,l.strip()[:140]) for i,l in enumerate(S,1) if "'published'" in l or 'published' in l]
print("  命中=",len(h))
for x in h[:10]: print("    L",x[0],x[1])

print("\n### 5. record_status <> 'rejected' 标注 ###")
print("  含 \"record_status <> 'rejected'\":", "record_status <> 'rejected'" in txt)
for i,l in enumerate(S,1):
    if "record_status <> 'rejected'" in l or 'rejected' in l and 'record_status' in l:
        print("    L",i,l.strip()[:160])

print("\n### 6. occurrence_key 命中（D3-5: 应 0 或不作为键） ###")
h=[(i,l.strip()[:140]) for i,l in enumerate(S,1) if 'occurrence_key' in l]
print("  命中=",len(h))
for x in h[:10]: print("    L",x[0],x[1])

print("\n### 7. data_source 6 列 & 许可列 ###")
LIC=['license','licence','redistributable','attribution','citation','default_license','license_gate','licensing']
h=[(i,l.strip()[:150]) for i,l in enumerate(S,1) if any(k in l.lower() for k in LIC)]
print("  许可相关关键词命中=",len(h))
for x in h[:20]: print("    L",x[0],x[1])
