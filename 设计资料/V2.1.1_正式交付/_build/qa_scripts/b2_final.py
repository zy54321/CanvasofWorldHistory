# -*- coding: utf-8 -*-
"""B-2 最终判定：card 内逐列名 token 精确匹配（列名必须作为独立 token 出现）"""
import re,html,os,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CL=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')
TAB={}; i=0; n=len(CL)
while i<n:
    m=re.match(r'^###\s+5\.\d+\s+`([a-z_]+)`',CL[i])
    if m:
        tname=m.group(1); cols=[]; j=i+1
        while j<n and not re.match(r'^\|\s*列\s*\|',CL[j]): j+=1
        if j<n:
            k=j+2
            while k<n and CL[k].startswith('|'):
                c=re.sub(r'\*\*','',CL[k].split('|')[1]).strip().strip('`').strip()
                for part in re.split(r'\s*/\s*',c):
                    part=re.sub(r'\*\*','',part).strip().strip('`').strip()
                    if re.fullmatch(r'[a-z][a-z_0-9]*',part) and part not in cols: cols.append(part)
                k+=1
        TAB[tname]=cols; i=j if j>i else i+1; continue
    i+=1
VIEWS={'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active','source_inactive_reason','child_table','child_row_id','child_record_status','child_rejected_by','is_anchor','is_canonical_row'],
'v_place_liveness':['place_id','dataset_id','grain_key','record_status','manual_rejected_rows','distinct_inactive_reasons','liveness'],
'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows','to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total','derivation_kind','all_children_rejected']}
MODEL=dict(TAB); MODEL.update(VIEWS)
SL=open(os.path.join(BASE,"ER_DIAGRAM_V2.1.1.svg"),encoding='utf-8').read().split('\n')
CARDS=[('data_source',100,296,34),('data_dataset',100,392,594),('import_batch',100,432,1154),
 ('source_record',460,812,34),('historical_place',460,864,594),('candidate_match',460,774,1154),
 ('historical_place_location',870,1352,34),('historical_place_name',870,1259,594),
 ('data_quality_issue',870,1264,1154),
 ('v_place_evidence',1380,1642,34),('v_place_liveness',1380,1660,594),('v_place_time_span',1380,1642,1154)]
ALLCOLS=set()
for v in MODEL.values(): ALLCOLS.update(v)
print("### B-2 双向逐字比对（最终） ###\n")
GG=[];MM=[];DET={}
for name,y0,y1,x0 in CARDS:
    tok=set(); lines=[]
    for i,l in enumerate(SL,1):
        m=re.search(r'<text x="(\d+)" y="(\d+)"',l)
        if not m: continue
        x,y=int(m.group(1)),int(m.group(2))
        if y0<=y<=y1 and x0-8<=x<=x0+515:
            t=html.unescape(re.sub(r'<[^>]+>','',l)).strip()
            if t:
                lines.append((i,t)); tok|=set(re.findall(r'[a-z][a-z_0-9]*',t))
    model=MODEL.get(name,[])
    # 虚构：卡片里出现、形如列名（在任一模型列集合里找不到 且 不在本表）→ 真正虚构需人工确认
    ghost=[t for t in sorted(tok) if '_' in t and t not in ALLCOLS and t not in model]
    missing=[c for c in model if c not in tok]
    GG+=[(name,g) for g in ghost]; MM+=[(name,m) for m in missing]
    DET[name]=dict(model=model,ghost=ghost,missing=missing)
    print(f"[{name:26s}] 模型列={len(model):2d}  虚构={len(ghost)}  漏画={len(missing)}")
    if ghost: print(f"     虚构候选: {ghost}")
    if missing: print(f"     漏画: {missing}")
print("\n"+"="*64)
print("虚构字段（含跨表引用的正常词）候选 =",len(GG))
for x in GG: print("   ",x)
print("\n漏画字段 =",len(MM))
for x in MM: print("   ",x)
