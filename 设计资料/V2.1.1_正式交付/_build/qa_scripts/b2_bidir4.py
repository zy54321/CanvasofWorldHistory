# -*- coding: utf-8 -*-
"""ER 图 vs CORE §5 双向逐字比对 v4：token 级匹配（正确处理 合并行 a / b type）"""
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
def card_lines(y0,y1,x0):
    out=[]
    for i,l in enumerate(SL,1):
        m=re.search(r'<text x="(\d+)" y="(\d+)"',l)
        if not m: continue
        x,y=int(m.group(1)),int(m.group(2))
        if y0<=y<=y1 and x0-8<=x<=x0+515:
            t=html.unescape(re.sub(r'<[^>]+>','',l)).strip()
            if t: out.append((i,t))
    return out

TYPES={'text','bigint','integer','boolean','jsonb','timestamptz','smallint','bytea','geometry','numeric','precision','double','identity','not','null','default','check','in','generated','always','as','stored','pk','fk','uq','ck','and','or','is','running','succeeded','partial','failed','rolled_back','quarantined_only','none','place','name','location','edge','creator','candidate','confirmed','rejected','superseded','primary','alternate','transliteration','historical','colloquial','certain','uncertain','precise','approximate','rough','unknown','confirmed','inferred','auto','manual','import','high','medium','low','source_asserted','blocking','warning','info','discarded','ignored','fixed_manually','preserved_and_flagged','needs_manual_review','admin_center_prefecture','admin_center_county','admin_center_other','settlement','lev_rank','lev_rank_unmapped','source_code_unconfirmed','per_record','per_parent_external_id','source_declared','pipeline_composed','same_coord_diff_entity','homonym_diff_place','same_entity_same_seat','location_migration_candidate','pleiades_connection','true_duplicate_suspected','cross_layer_disagreement','none','a_to_b','b_to_a','source_absent','batch_rolled_back','duplicate_quarantine','disputed','arbitrated','none','staging','merged'}
print("### 双向比对 v4（token 级） ###\n")
GG=[];MM=[];DETAIL={}
for name,y0,y1,x0 in CARDS:
    lines=card_lines(y0,y1,x0)
    txt="\n".join(t for _,t in lines)
    tokens=set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*',txt))
    model=MODEL.get(name,[])
    ghost=[t for t in sorted(tokens) if t not in TYPES and '_' in t or (t not in TYPES and t not in model and len(t)>3 and t.islower())]
    # 更严格：把 token 里所有"看起来像列名"的（含下划线 或 在任一模型表里出现过）拿来做虚构检查
    allcols=set()
    for v in MODEL.values(): allcols.update(v)
    ghost=[t for t in sorted(tokens) if '_' in t and t not in model and t not in allcols]
    missing=[c for c in model if c not in tokens]
    GG+=[(name,g) for g in ghost]; MM+=[(name,m) for m in missing]
    DETAIL[name]=dict(er_tokens=sorted(t for t in tokens if '_' in t),model=model,ghost=ghost,missing=missing)
    print(f"[{name}] 图内含下划线token={len([t for t in tokens if '_' in t])} 模型列={len(model)}")
    print(f"   虚构 {'✅' if not ghost else '❌'}: {ghost if ghost else '无'}")
    if missing:
        print(f"   漏画 ❌: {missing}")
        for c in missing:
            for ln,t in lines:
                if c in t: print(f"        实际出现在 L{ln}: {t[:150]}")
    else:
        print(f"   漏画 ✅: 无")
    print()
print("="*64)
print("虚构合计 =",len(GG),GG)
print("漏画合计 =",len(MM),MM)
