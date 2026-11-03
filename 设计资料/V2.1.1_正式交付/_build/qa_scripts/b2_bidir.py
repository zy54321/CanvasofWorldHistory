# -*- coding: utf-8 -*-
"""ER 图 vs CORE §5 字段双向逐字比对"""
import re,html,os,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
svg=open(os.path.join(BASE,"ER_DIAGRAM_V2.1.1.svg"),encoding='utf-8').read()
SL=svg.split('\n')

CARDS=[('data_source',100,296,34),('data_dataset',100,390,594),('import_batch',100,430,1154),
 ('source_record',460,810,34),('historical_place',460,862,594),('candidate_match',460,772,1154),
 ('historical_place_location',870,1350,34),('historical_place_name',870,1257,594),
 ('data_quality_issue',870,1262,1154),
 ('v_place_evidence',1380,1640,34),('v_place_liveness',1380,1658,594),('v_place_time_span',1380,1640,1154)]

def texts_in(y0,y1,x0,x1):
    out=[]
    for i,l in enumerate(SL,1):
        m=re.search(r'<text x="(\d+)" y="(\d+)"',l)
        if not m: continue
        x,y=int(m.group(1)),int(m.group(2))
        if y0<=y<=y1 and x0-10<=x<=x1+10:
            t=html.unescape(re.sub(r'<[^>]+>','',l)).strip()
            if t: out.append((i,t))
    return out

# CORE 表列（脚本抽取）
CL=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')
TAB={}
cur=None
for i,l in enumerate(CL,1):
    m=re.match(r'^(###|####)\s+5\.\d+(\.\d+)?\s+`([a-z_]+)`',l)
    if m:
        cur=m.group(3) if m.group(1)=='###' else None
        if cur: TAB.setdefault(cur,[])
        continue
    if re.match(r'^##\s',l): cur=None
    if cur:
        cells=l.split('|')
        if len(cells)>=3:
            c=re.sub(r'\*\*','',cells[1]).strip().strip('`').strip()
            for part in re.split(r'\s*/\s*',c):
                part=re.sub(r'\*\*','',part).strip().strip('`').strip()
                if re.fullmatch(r'[a-z][a-z_0-9]*',part) and part not in TAB[cur]:
                    TAB[cur].append(part)
def clean(cols):
    # 去掉值域外的伪列（数据集 id 行、示例 id 行等）
    JUNK={'chgis_v6_prefecture_points','chgis_v6_county_points','mcgd_zenodo_22094815_head960',
          'pleiades_gis_4_1_slice','whg_geoname_s_gn_sample','whg_getty_tgn_sample',
          'whg_hgis_de_las_indias_sample','dq_0007487','dq_0007488'}
    return [c for c in cols if c not in JUNK]
for k in TAB: TAB[k]=clean(TAB[k])

VIEWS={
'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active','source_inactive_reason','child_table','child_row_id','child_record_status','child_rejected_by','is_anchor','is_canonical_row'],
'v_place_liveness':['place_id','dataset_id','grain_key','record_status','manual_rejected_rows','distinct_inactive_reasons','liveness'],
'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows','to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total','derivation_kind','all_children_rejected'],
}
MODEL=dict(TAB); MODEL.update(VIEWS)

# 视图只比对 "N  列名" 编号行
print("### ER 图内实体字段抽取 + 双向比对 ###\n")
summary={}
for name,y0,y1,x0 in CARDS:
    rows=texts_in(y0,y1,x0,x0+510)
    er_cols=[]
    if name.startswith('v_'):
        for ln,t in rows:
            m=re.match(r'^\s*(\d{1,2})\s+([a-z_][a-z_0-9]*)\b',t)
            if m: er_cols.append((int(m.group(1)),m.group(2),ln,t))
        er_names=[c[1] for c in er_cols]
    else:
        for ln,t in rows:
            m=re.match(r'^\s*(?:PK|FK|\+|\*|~|D|\s)\s*([a-z_][a-z_0-9]*)\b',t)
            if m and m.group(1) not in ('CHECK','NOT','DEFAULT','text','bigint','integer','boolean','jsonb','timestamptz','smallint','bytea','GENERATED','IN','NULL'):
                er_cols.append((None,m.group(1),ln,t))
        er_names=[c[1] for c in er_cols]
    model=MODEL.get(name,[])
    # 去重保序
    seen=set(); en=[]
    for c in er_names:
        if c not in seen: seen.add(c); en.append(c)
    ghost=[c for c in en if c not in model]
    missing=[c for c in model if c not in en]
    summary[name]=dict(er=en,model=model,ghost=ghost,missing=missing,n_er=len(en),n_model=len(model))
    print(f"[{name}]  图内={len(en)}  模型={len(model)}")
    print(f"   图内字段: {en}")
    print(f"   模型字段: {model}")
    print(f"   ❌ 图有模型无（虚构）: {ghost if ghost else '无 ✅'}")
    print(f"   ❌ 模型有图无（漏画）: {missing if missing else '无 ✅'}")
    print()
json.dump(summary,open(os.path.join(BASE,"_build","qa_scripts","_b2_bidir.json"),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
