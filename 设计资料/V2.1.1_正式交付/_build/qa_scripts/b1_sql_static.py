# -*- coding: utf-8 -*-
"""三视图 SQL 静态可执行性：列引用可见性 + 占位符 + count(e.place_id)"""
import os,re,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE=os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md")
L=open(CORE,encoding='utf-8').read().split('\n')

# --- 1) 从 §5 各表定义抽取列名（形如 | `col` | type | ...） ---
SECTIONS={}
cur=None
for i,l in enumerate(L,1):
    m=re.match(r'^###\s+5\.\d+\s+`([a-z_]+)`',l)
    if m: cur=m.group(1); SECTIONS.setdefault(cur,{'start':i,'cols':[]}); continue
    if re.match(r'^#{2,4}\s',l) and cur and not re.match(r'^####\s',l):
        if re.match(r'^####',l) is None and re.match(r'^###\s+5\.\d+\s+`',l) is None:
            cur=None
    if cur and re.match(r'^\|\s*`([a-z_0-9]+)`\s*\|',l):
        SECTIONS[cur]['cols'].append(re.match(r'^\|\s*`([a-z_0-9]+)`\s*\|',l).group(1))
# 只保留 9 张表
TABLES={k:v['cols'] for k,v in SECTIONS.items() if k in
 ['data_source','data_dataset','import_batch','source_record','historical_place',
  'historical_place_location','historical_place_name','candidate_match','data_quality_issue']}
print("### 抽取到的表列名（来自 CORE §5 表格） ###")
for k,v in TABLES.items():
    print(f"  {k:32s} ({len(v):2d}): {v}")

# --- 2) 视图对外列（手工从 §5.10 列清单取，与 SQL SELECT 交叉验证） ---
VIEWS={
 'v_place_evidence':['place_id','source_record_id','evidence_role','source_is_active',
   'source_inactive_reason','child_table','child_row_id','child_record_status',
   'child_rejected_by','is_anchor','is_canonical_row'],
 'v_place_liveness':['place_id','dataset_id','grain_key','record_status',
   'manual_rejected_rows','distinct_inactive_reasons','liveness'],
 'v_place_time_span':['place_id','span_from_astro','span_to_astro','from_evidence_rows',
   'to_evidence_rows','staging_evidence_rows','valid_child_rows','child_rows_total',
   'derivation_kind','all_children_rejected'],
}
print()
print("### 视图对外列数 ###")
for k,v in VIEWS.items(): print(f"  {k:22s} {len(v)} 列")

# --- 3) 视图 SQL 提取 ---
def get_block(start_hint, name):
    # 在 start_hint 之后找第一个 ```sql 块
    idx=None
    for i in range(start_hint, len(L)):
        if L[i].strip().startswith('```sql'): idx=i; break
    if idx is None: return None,None,None
    j=idx+1
    while j<len(L) and not L[j].strip().startswith('```'): j+=1
    return idx+1, j+1, L[idx+1:j]   # start,end(1-based),lines
HDR={}
for i,l in enumerate(L,1):
    for v in VIEWS:
        if l.strip().startswith('#### 5.10') and '`'+v+'`' in l: HDR[v]=i

SQL={}
for v,h in HDR.items():
    s,e,lines=get_block(h,v)
    SQL[v]=dict(start=s,end=e,text='\n'.join(lines))
    print(f"\n{v}: SQL 块 L{s}–L{e}")

# --- 4) 校验 A：v_place_liveness 中 e.xxx 是否都在 v_place_evidence 11 列；sr.xxx 是否都在 source_record ---
print("\n### 校验 A：v_place_liveness 列可见性 ###")
txt=SQL['v_place_liveness']['text']
e_cols=set(re.findall(r'\be\.([a-z_0-9]+)', txt))
sr_cols=set(re.findall(r'\bsr\.([a-z_0-9]+)', txt))
p_cols=set(re.findall(r'\bp\.([a-z_0-9]+)', txt))
print("  e.* 引用:",sorted(e_cols))
bad=[c for c in e_cols if c not in VIEWS['v_place_evidence']]
print("  不在 v_place_evidence 11 列内:", bad if bad else "无 ✅")
print("  sr.* 引用:",sorted(sr_cols))
bad2=[c for c in sr_cols if c not in TABLES['source_record']]
print("  不在 source_record 列内:", bad2 if bad2 else "无 ✅")
print("  p.* 引用:",sorted(p_cols))
bad3=[c for c in p_cols if c not in TABLES['historical_place']]
print("  不在 historical_place 列内:", bad3 if bad3 else "无 ✅")

print("\n### 校验 B：v_place_evidence 列可见性 ###")
t1=SQL['v_place_evidence']['text']
refs={'p':set(re.findall(r'\bp\.([a-z_0-9]+)',t1)),
      'sr':set(re.findall(r'\bsr\.([a-z_0-9]+)',t1)),
      'n':set(re.findall(r'\bn\.([a-z_0-9]+)',t1)),
      'l':set(re.findall(r'\bl\.([a-z_0-9]+)',t1)),
      'u':set(re.findall(r'\bu\.([a-z_0-9]+)',t1))}
owner={'p':'historical_place','sr':'source_record','n':'historical_place_name','l':'historical_place_location'}
for k,v in refs.items():
    if k=='u':
        bad=[c for c in v if c not in VIEWS['v_place_evidence']]
        print(f"  u.* ({len(v)}): 不在对外11列内 -> {bad if bad else '无 ✅'}   {sorted(v)}")
        continue
    bad=[c for c in v if c not in TABLES[owner[k]]]
    print(f"  {k}.*= {owner[k]:26s} 不在表内 -> {bad if bad else '无 ✅'}  ({sorted(v)})")

print("\n### 校验 C：v_place_time_span 列可见性 ###")
t3=SQL['v_place_time_span']['text']
for k,own in [('p','historical_place'),('sr','source_record'),('c','__child_union__'),('e','__eff__')]:
    got=set(re.findall(r'\b'+k+r'\.([a-z_0-9]+)',t3))
    if own.startswith('__'):
        print(f"  {k}.* 引用: {sorted(got)}  （CTE 别名，人工核对）")
    else:
        bad=[c for c in got if c not in TABLES[own]]
        print(f"  {k}.*= {own:24s} 不在表内 -> {bad if bad else '无 ✅'}  ({sorted(got)})")

print("\n### 校验 D：裸 count(*) vs count(e.place_id) ###")
for v in VIEWS:
    t=SQL[v]['text']
    n_all=len(re.findall(r'count\(\*\)(?!\s*FILTER)',t,re.I))
    n_col=len(re.findall(r'count\(\s*[a-z]+\.[a-z_0-9]+\s*\)',t,re.I))
    print(f"  {v:22s} 裸count(*)={n_all}  count(col)={n_col}")
print("  v_place_time_span 是否含 count(e.place_id):", 'count(e.place_id)' in t3)
print("  v_place_time_span 是否含 'published':", "'published'" in t3)

print("\n### 校验 E：三视图 SQL 内含占位符 ###")
for v in VIEWS:
    t=SQL[v]['text']
    print(f"  {v:22s} '<'占位符={len(re.findall(r'<[^=><!-]',t))}  '<...>'={t.count('<...>')}  '...'={t.count('...')}")
