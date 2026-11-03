# -*- coding: utf-8 -*-
"""D5-1 幽灵列 + D5-6 七张 CSV 行数（来源层级 ①原始 CSV 逐行算）"""
import csv,os,io,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NORM=r"E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/设计资料/P0收敛/WB-002/normalized"
print("### 来源层级 ①：真实 CSV 表头与行数（逐行算） ###")
real={}
for fn in sorted(os.listdir(NORM)):
    if not fn.endswith('.csv'): continue
    p=os.path.join(NORM,fn)
    with open(p,'r',encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f); hdr=next(r); n=sum(1 for _ in r)
    real[fn]=dict(hdr=hdr,n=n,size=os.path.getsize(p))
    print(f"  {fn:38s} 行={n:7d} 列={len(hdr):4d} 字节={os.path.getsize(p):,}")

print("\n### D5-6 七张 CSV 行数 vs 权威（29,391 / 19,039 / 47,503 / 18,103 / 12,631） ###")
EXP={'source_records.csv':29391,'historical_places.csv':19039,'historical_place_names.csv':47503,
     'historical_place_locations.csv':18103,'data_quality_issues.csv':12631}
for k,v in EXP.items():
    got=real.get(k,{}).get('n')
    print(f"  {k:34s} 实测={got:7d} 权威={v:7d} {'✅' if got==v else '❌ 差 '+str(got-v)}")
for k in ['data_datasets.csv','candidate_matches.csv']:
    print(f"  {k:34s} 实测={real.get(k,{}).get('n')}（无判据基线）")

print("\n### D5-1 幽灵列：FIELD_MAPPING.staging_column 是否真实存在 ###")
rows=list(csv.DictReader(open(os.path.join(BASE,"FIELD_MAPPING_V2.1.1.csv"),encoding='utf-8-sig')))
print(f"  FIELD_MAPPING 数据行 = {len(rows)}")
ghost=[]; derived_ok=[]; notfound_table=[]
for r in rows:
    st=(r['staging_table'] or '').strip(); sc=(r['staging_column'] or '').strip()
    if st not in real:
        notfound_table.append((st,sc,r['target_column'],r['transform']))
        continue
    hdr=real[st]['hdr']
    if sc in hdr: continue
    note=(r['notes'] or '')+(r['transform'] or '')
    if sc in ('(derived)','(generated)','(dropped)') or 'derived' in (r['transform'] or '') or '(dropped)' in (r['target_column'] or '') or '(generated)' in (r['target_column'] or ''):
        derived_ok.append((st,sc,r['target_column'],r['transform']))
    else:
        ghost.append((st,sc,r['target_column'],r['transform'],(r['notes'] or '')[:100]))
print(f"  标记 derived/generated/dropped（合规）= {len(derived_ok)}")
print(f"  staging_table 不在实测目录 = {len(notfound_table)}")
for x in notfound_table[:10]: print("     ",x)
print(f"  幽灵列（既不存在也无 derived 标记）= {len(ghost)}  {'✅' if not ghost else '❌'}")
for g in ghost: print("     ",g)
json.dump({'real50':{k:{'n':v['n'],'hdr':v['hdr']} for k,v in real.items()}},open(os.path.join(BASE,'_build','qa_scripts','_real_csv.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
