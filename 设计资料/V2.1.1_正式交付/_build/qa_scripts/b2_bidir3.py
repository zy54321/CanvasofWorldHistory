# -*- coding: utf-8 -*-
"""ER 图 vs CORE §5 字段双向比对（v3：模型侧只取每节第一个"列|类型|约束"表）"""
import re,html,os,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CL=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')

# --- 模型侧：定位每节列定义表 ---
TAB={}; i=0; n=len(CL)
while i<n:
    m=re.match(r'^###\s+5\.\d+\s+`([a-z_]+)`',CL[i])
    if m:
        tname=m.group(1); cols=[]
        j=i+1
        # 找第一个表头含"列"的表
        while j<n and not re.match(r'^\|\s*列\s*\|',CL[j]): j+=1
        if j<n:
            k=j+2
            while k<n and CL[k].startswith('|'):
                cells=CL[k].split('|')
                c=re.sub(r'\*\*','',cells[1]).strip().strip('`').strip()
                for part in re.split(r'\s*/\s*',c):
                    part=re.sub(r'\*\*','',part).strip().strip('`').strip()
                    if re.fullmatch(r'[a-z][a-z_0-9]*',part) and part not in cols: cols.append(part)
                k+=1
        TAB[tname]=cols
        i=j if j>i else i+1
        continue
    i+=1
print("### 模型侧列（只取每节首个列定义表） ###")
for k,v in TAB.items(): print(f"  {k:28s} ({len(v):2d}) {v}")

VIEWS={'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active','source_inactive_reason','child_table','child_row_id','child_record_status','child_rejected_by','is_anchor','is_canonical_row'],
'v_place_liveness':['place_id','dataset_id','grain_key','record_status','manual_rejected_rows','distinct_inactive_reasons','liveness'],
'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows','to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total','derivation_kind','all_children_rejected']}
MODEL=dict(TAB); MODEL.update(VIEWS)

# --- 图侧 ---
SL=open(os.path.join(BASE,"ER_DIAGRAM_V2.1.1.svg"),encoding='utf-8').read().split('\n')
CARDS=[('data_source',100,296,34),('data_dataset',100,392,594),('import_batch',100,432,1154),
 ('source_record',460,812,34),('historical_place',460,864,594),('candidate_match',460,774,1154),
 ('historical_place_location',870,1352,34),('historical_place_name',870,1259,594),
 ('data_quality_issue',870,1264,1154),
 ('v_place_evidence',1380,1642,34),('v_place_liveness',1380,1660,594),('v_place_time_span',1380,1642,1154)]
TYPES=r'(?:double precision|text\[\]|bigint\[\]|integer\[\]|text|bigint|integer|boolean|jsonb|timestamptz|smallint|bytea|geometry\([^)]*\)|geometry|numeric)'
def card_text(y0,y1,x0):
    out=[]
    for l in SL:
        m=re.search(r'<text x="(\d+)" y="(\d+)"',l)
        if not m: continue
        x,y=int(m.group(1)),int(m.group(2))
        if y0<=y<=y1 and x0-8<=x<=x0+515:
            t=html.unescape(re.sub(r'<[^>]+>','',l)).strip()
            if t: out.append(t)
    return "\n".join(out)
def extract(txt,isv):
    cols=[]
    if isv:
        for m in re.finditer(r'(?:^|\s)(\d{1,2})\s+([a-z_][a-z_0-9]*)\b',txt,re.M): cols.append(m.group(2))
    else:
        for m in re.finditer(r'([a-z_][a-z_0-9]*)\s*/\s*([a-z_][a-z_0-9]*)\s+'+TYPES+r'\b',txt):
            cols.append(m.group(1)); cols.append(m.group(2))
        for m in re.finditer(r'([a-z_][a-z_0-9]*)\s+'+TYPES+r'\b',txt): cols.append(m.group(1))
        # `X / Y  type1 / type2` 形式
        for m in re.finditer(r'([a-z_][a-z_0-9]*)\s*/\s*([a-z_][a-z_0-9]*)\s+(?:'+TYPES+r'\s*/\s*)+',txt):
            cols.append(m.group(1)); cols.append(m.group(2))
    seen=set(); r=[]
    for c in cols:
        if c not in seen: seen.add(c); r.append(c)
    return r

NOTCOL={'check','not','default','null','in','generated','always','as','stored','pk','fk','uq','ck','d','identity','none','smallint','and','or','is','text','bigint','integer','boolean','jsonb','timestamptz','bytea','geometry','numeric','double','precision'}
print("\n### 双向比对 ###\n")
G=[];M=[]
for name,y0,y1,x0 in CARDS:
    t=card_text(y0,y1,x0); isv=name.startswith('v_')
    er=[c for c in extract(t,isv) if c not in NOTCOL]
    model=MODEL.get(name,[])
    ghost=[c for c in er if c not in model]
    missing=[c for c in model if c not in er]
    G+=[(name,g) for g in ghost]; M+=[(name,m) for m in missing]
    print(f"[{name}] 图={len(er)} 模型={len(model)}  虚构={'无 ✅' if not ghost else ghost}  漏画={'无 ✅' if not missing else missing}")
print("\n"+"="*60)
print("虚构字段合计 =",len(G),G)
print("漏画字段合计 =",len(M),M)
