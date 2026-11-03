# -*- coding: utf-8 -*-
"""ER 图 vs CORE §5 字段双向比对 —— 基于"列名+类型"模式，支持一行多列"""
import re,html,os,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SL=open(os.path.join(BASE,"ER_DIAGRAM_V2.1.1.svg"),encoding='utf-8').read().split('\n')
CARDS=[('data_source',100,296,34),('data_dataset',100,392,594),('import_batch',100,432,1154),
 ('source_record',460,812,34),('historical_place',460,864,594),('candidate_match',460,774,1154),
 ('historical_place_location',870,1352,34),('historical_place_name',870,1259,594),
 ('data_quality_issue',870,1264,1154),
 ('v_place_evidence',1380,1642,34),('v_place_liveness',1380,1660,594),('v_place_time_span',1380,1642,1154)]
TYPES=r'(?:double precision|text\[\]|bigint\[\]|integer\[\]|text|bigint|integer|boolean|jsonb|timestamptz|smallint|bytea|geometry\([^)]*\)|geometry)'
def card_text(name,y0,y1,x0):
    out=[]
    for i,l in enumerate(SL,1):
        m=re.search(r'<text x="(\d+)" y="(\d+)"',l)
        if not m: continue
        x,y=int(m.group(1)),int(m.group(2))
        if y0<=y<=y1 and x0-8<=x<=x0+515:
            t=html.unescape(re.sub(r'<[^>]+>','',l)).strip()
            if t: out.append(t)
    return "\n".join(out)

def extract_cols(txt, is_view):
    cols=[]
    if is_view:
        for m in re.finditer(r'(?:^|\s)(\d{1,2})\s+([a-z_][a-z_0-9]*)\b',txt,re.M):
            cols.append((int(m.group(1)),m.group(2)))
    else:
        # 列名紧跟类型
        for m in re.finditer(r'([a-z_][a-z_0-9]*)\s+'+TYPES+r'\b',txt):
            cols.append((None,m.group(1)))
        # 合并格 `a / b  type` 形式
        for m in re.finditer(r'([a-z_][a-z_0-9]*)\s*/\s*([a-z_][a-z_0-9]*)\s+'+TYPES+r'\b',txt):
            cols.append((None,m.group(1))); cols.append((None,m.group(2)))
    # 去重保序
    seen=set(); r=[]
    for n,c in cols:
        if c not in seen: seen.add(c); r.append((n,c))
    return r

CL=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')
TAB={}; cur=None
for l in CL:
    m=re.match(r'^(###|####)\s+5\.\d+(\.\d+)?\s+`([a-z_]+)`',l)
    if m:
        cur=m.group(3) if m.group(1)=='###' else None
        if cur: TAB.setdefault(cur,[])
        continue
    if re.match(r'^##\s',l): cur=None
    if cur and l.startswith('|'):
        cells=l.split('|')
        if len(cells)>=3:
            c=re.sub(r'\*\*','',cells[1]).strip().strip('`').strip()
            for part in re.split(r'\s*/\s*',c):
                part=re.sub(r'\*\*','',part).strip().strip('`').strip()
                if re.fullmatch(r'[a-z][a-z_0-9]*',part) and part not in TAB[cur]:
                    TAB[cur].append(part)
JUNK={'chgis_v6_prefecture_points','chgis_v6_county_points','mcgd_zenodo_22094815_head960',
 'pleiades_gis_4_1_slice','whg_geoname_s_gn_sample','whg_getty_tgn_sample',
 'whg_hgis_de_las_indias_sample','dq_0007487','dq_0007488'}
for k in TAB: TAB[k]=[c for c in TAB[k] if c not in JUNK]
VIEWS={'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active','source_inactive_reason','child_table','child_row_id','child_record_status','child_rejected_by','is_anchor','is_canonical_row'],
'v_place_liveness':['place_id','dataset_id','grain_key','record_status','manual_rejected_rows','distinct_inactive_reasons','liveness'],
'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows','to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total','derivation_kind','all_children_rejected']}
MODEL=dict(TAB); MODEL.update(VIEWS)
TOT_G=[];TOT_M=[]
print("### 双向比对（修正抽取：支持一行多列 / 合并格） ###\n")
RES={}
for name,y0,y1,x0 in CARDS:
    t=card_text(name,y0,y1,x0); isv=name.startswith('v_')
    got=extract_cols(t,isv)
    er=[c for _,c in got]; model=MODEL.get(name,[])
    ghost=[c for c in er if c not in model]
    missing=[c for c in model if c not in er]
    RES[name]=dict(er=er,model=model,ghost=ghost,missing=missing)
    TOT_G+= [(name,g) for g in ghost]; TOT_M += [(name,m) for m in missing]
    flag1='✅' if not ghost else '❌'; flag2='✅' if not missing else '❌'
    print(f"[{name}] 图内={len(er)} 模型={len(model)}")
    if isv:
        nums=[n for n,_ in got]
        print(f"   视图列编号: {nums}  连续1..{len(model)}: {nums==list(range(1,len(model)+1))}")
    print(f"   虚构(图有模型无) {flag1}: {ghost if ghost else '无'}")
    print(f"   漏画(模型有图无) {flag2}: {missing if missing else '无'}")
    print()
print("="*60)
print("总计 虚构字段 =",len(TOT_G), TOT_G)
print("总计 漏画字段 =",len(TOT_M), TOT_M)
json.dump(RES,open(os.path.join(BASE,"_build","qa_scripts","_b2_bidir2.json"),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
