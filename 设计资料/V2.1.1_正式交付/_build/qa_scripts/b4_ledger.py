# -*- coding: utf-8 -*-
"""B-4：逐行核实 data_quality_issues.csv 中 6 行空 source_record_id —— 来源层级 ①原始 CSV 逐行算"""
import csv,os,collections
NORM=r"E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/设计资料/P0收敛/WB-002/normalized"
p=os.path.join(NORM,"data_quality_issues.csv")
rows=list(csv.DictReader(open(p,encoding='utf-8-sig')))
print("列头:",list(rows[0].keys()))
print("总行数:",len(rows))
empty=[r for r in rows if (r.get('source_record_id') or '').strip()=='']
print("\n### source_record_id 为空的记录数 =",len(empty),"###")
for r in empty:
    print(f"  issue_id={r.get('issue_id')!r:16} source_dataset={r.get('source_dataset')!r:30} issue_type={r.get('issue_type')!r:26} action_taken={r.get('action_taken')!r:24} field_name={r.get('field_name')!r}")

print("\n### source_dataset 值域分布（全表） ###")
c=collections.Counter((r.get('source_dataset') or '').strip() for r in rows)
for k,v in c.most_common(): print(f"   {k!r:34} {v}")

print("\n### 断言：2 chgis_pref/nonstandard_field_name + 4 pleiades/truncated_slice_tail ###")
a=[r for r in empty if (r.get('source_dataset')=='chgis_pref' and r.get('issue_type')=='nonstandard_field_name')]
b=[r for r in empty if (r.get('source_dataset')=='pleiades_gis_4_1_slice' and r.get('issue_type')=='truncated_slice_tail')]
print(f"   2 条 chgis_pref + nonstandard_field_name 实测 = {len(a)} {'✅' if len(a)==2 else '❌'}")
for r in a: print("      ",r.get('issue_id'),r.get('field_name'))
print(f"   4 条 pleiades + truncated_slice_tail 实测 = {len(b)} {'✅' if len(b)==4 else '❌'}")
for r in b: print("      ",r.get('issue_id'))
print(f"   合计 = {len(a)+len(b)} / {len(empty)}  {'✅ 完全覆盖' if len(a)+len(b)==len(empty) else '❌'}")

print("\n### 是否含 place_id 列 ###")
print("   place_id in header:", 'place_id' in rows[0])
print("   raw_file in header:", 'raw_file' in rows[0])
print("   dataset_id in header:", 'dataset_id' in rows[0])
