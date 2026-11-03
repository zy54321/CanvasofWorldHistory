# -*- coding: utf-8 -*-
import os,re,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')

# 显式列清单（人工从 CORE §5 表格核对，脚本校对一致性见 b1_sql_static2.py）
TABLES={
'data_source':['source_id','display_name','homepage_url','display_priority','notes','created_at'],
'data_dataset':['dataset_id','source_id','display_name','dataset_version','record_scopes','place_grain','location_grain','grain_evidence','occurrence_key_rule','external_id_nature','content_sha256','local_path','record_count','is_active','notes','created_at','updated_at'],
'import_batch':['batch_id','dataset_id','dataset_version','derivation_version','status','input_file','input_sha256','input_row_count','inserted_source_record_ids','updated_source_record_ids','quarantined_count','skipped_count','failed_count','blocked_count','rollback_of_batch_id','started_at','finished_at','operator','notes'],
'source_record':['source_record_id','dataset_id','record_scope','external_id','parent_external_id','duplicate_ordinal','raw_file','raw_record_index','raw_payload','content_hash','first_batch_id','last_batch_id','is_active','inactive_reason','inactive_at','inactive_in_batch_id','ingested_at'],
'historical_place':['place_id','dataset_id','grain_key','canonical_name','canonical_name_lang','place_type','place_type_source','place_type_basis_note','description','record_status','merged_into_place_id','merge_review_ref','merged_at','created_from_source_record_id','created_by','locked','manual_edited_fields','notes','created_at','updated_at'],
'historical_place_location':['location_id','place_id','source_record_id','geom','geom_type','representative_lon','representative_lat','original_x','original_y','original_crs','crs_confidence','axis_order_verified','crs_transform_meta','location_precision','uncertainty_m','uncertainty_source','valid_from_year_astro','valid_to_year_astro','time_bound_type','source_beg_rule','source_end_rule','source_time_columns','time_note','conflict_status','is_preferred','record_status','rejected_by','locked','manual_edited_fields','created_by','notes'],
'historical_place_name':['name_id','place_id','source_record_id','name_text','name_lang','name_script','name_type','transliteration_scheme','association_certainty','valid_from_year_astro','valid_to_year_astro','time_bound_type','source_time_columns','time_note','notes','record_status','rejected_by','locked','manual_edited_fields','created_by'],
'candidate_match':['candidate_id','relation_type','place_id_a','place_id_b','source_record_id_a','source_record_id_b','distance_m','direction','evidence','confidence','status','reviewer','reviewed_at','review_note','created_at','updated_at'],
'data_quality_issue':['issue_id','dataset_id','source_record_id','place_id','batch_id','issue_fingerprint','issue_type','severity','field_name','observed_value','expected_rule','action_taken','first_batch_id','last_batch_id','occurrence_count','resolved','resolved_at','resolver','resolution_note','created_at'],
}
VIEWS={
'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active','source_inactive_reason','child_table','child_row_id','child_record_status','child_rejected_by','is_anchor','is_canonical_row'],
'v_place_liveness':['place_id','dataset_id','grain_key','record_status','manual_rejected_rows','distinct_inactive_reasons','liveness'],
'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows','to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total','derivation_kind','all_children_rejected'],
}
def sqlblock(kw):
    for i,l in enumerate(L):
        if l.strip().startswith('####') and kw in l:
            j=i
            while j<len(L) and not L[j].strip().startswith('```sql'): j+=1
            k=j+1
            while k<len(L) and not L[k].strip().startswith('```'): k+=1
            return j+1,k+1,'\n'.join(L[j+1:k])
    return None
S={v:sqlblock(v) for v in VIEWS}
ok=True
print("### A. v_place_liveness：e.* / sr.* / p.* 列可见性 ###")
t=S['v_place_liveness'][2]
for alias,allowed,label in [('e',VIEWS['v_place_evidence'],'v_place_evidence 11列'),
                            ('sr',TABLES['source_record'],'source_record'),
                            ('p',TABLES['historical_place'],'historical_place')]:
    got=sorted(set(re.findall(r'\b'+alias+r'\.([a-z_0-9]+)',t)))
    bad=[c for c in got if c not in allowed]
    print(f"  {alias}.* ({len(got)}): {got}")
    print(f"      不在 {label} -> {bad if bad else '无 ✅'}")
    if bad: ok=False
print("\n### B. v_place_evidence：分支别名列可见性 ###")
t=S['v_place_evidence'][2]
for alias,own in [('p','historical_place'),('sr','source_record'),('n','historical_place_name'),('l','historical_place_location')]:
    got=sorted(set(re.findall(r'\b'+alias+r'\.([a-z_0-9]+)',t)))
    bad=[c for c in got if c not in TABLES[own]]
    print(f"  {alias}.* ({own}): {got} -> 不在表内 {bad if bad else '无 ✅'}")
    if bad: ok=False
got=sorted(set(re.findall(r'\bu\.([a-z_0-9]+)',t)))
bad=[c for c in got if c not in VIEWS['v_place_evidence']]
print(f"  u.* (11列): {got} -> 超出 {bad if bad else '无 ✅'}")

print("\n### C. v_place_time_span：CTE 列一致性 ###")
t=S['v_place_time_span'][2]
print("  child CTE 输出列:", re.findall(r'AS\s+f\b|AS\s+t\b|valid_from_year_astro|valid_to_year_astro',t)[:10])
print("  e.* 引用:",sorted(set(re.findall(r'\be\.([a-z_0-9]+)',t))))
print("  c.* 引用:",sorted(set(re.findall(r'\bc\.([a-z_0-9]+)',t))))
print("  eff CTE: SELECT c.*, sr.is_active -> 提供 f/t/record_status/place_id/source_record_id/is_active")
print("  'record_status <> \\'rejected\\'' 出现:", "record_status <> 'rejected'" in t)
print("  'published' 出现:", "'published'" in t)
print("  count(e.place_id):", "count(e.place_id)" in t)
print("  裸 count(*) 无 FILTER:", len(re.findall(r'count\(\*\)(?!\s*FILTER)',t)))

print("\n### D. v_place_evidence 窗口定序 6 键 ###")
t1=S['v_place_evidence'][2]
m=re.search(r'ORDER BY(.*?)\)\s*=\s*1',t1,re.S)
print(m.group(0)[:700] if m else "未找到")

print("\n### E. v_place_liveness 8 值枚举 ###")
t2=S['v_place_liveness'][2]
vals=sorted(set(re.findall(r"THEN '([a-z_]+)'",t2)))
print("  CASE 输出值:",vals)
print("\nALL_COLS_VISIBLE =",ok)
