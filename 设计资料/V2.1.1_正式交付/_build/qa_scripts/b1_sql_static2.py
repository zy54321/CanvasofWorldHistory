# -*- coding: utf-8 -*-
"""修正版：稳健抽取 §5 表列（支持 **`col`**、`a` / `b` 合并格、跳过 §5.x.y 子节示例表）"""
import os,re,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L=open(os.path.join(BASE,"CORE_DATA_MODEL_V2.1.1.md"),encoding='utf-8').read().split('\n')

TABLES={}
cur=None; level=None
for i,l in enumerate(L,1):
    m=re.match(r'^(###|####)\s+5\.\d+(\.\d+)?\s+`([a-z_]+)`',l)
    if m:
        if m.group(1)=='###':
            cur=m.group(3); TABLES.setdefault(cur,[])
        else:
            cur=None           # 子节里的示例表不是列定义
        continue
    if re.match(r'^##\s',l) or (re.match(r'^###\s',l) and not re.match(r'^###\s+5\.\d+',l)):
        if re.match(r'^##\s',l): cur=None
    if cur:
        cell=l.split('|')
        if len(cell)>=3:
            c=cell[1].strip()
            c=re.sub(r'^\*\*|\*\*$','',c).strip()
            c=c.strip('`').strip()
            # 合并格 `a` / `b`
            for part in re.split(r'\s*/\s*',c):
                part=re.sub(r'^\*\*|\*\*$','',part).strip().strip('`').strip()
                if re.fullmatch(r'[a-z][a-z_0-9]*',part) and part not in TABLES[cur]:
                    TABLES[cur].append(part)
        # 处理 **`a`** / **`b`** 形式的合并格
        for mm in re.finditer(r'\*\*`([a-z_0-9]+)`\*\*\s*/\s*\*\*`([a-z_0-9]+)`\*\*',l):
            for g in mm.groups():
                if g not in TABLES[cur]: TABLES[cur].append(g)

KEEP=['data_source','data_dataset','import_batch','source_record','historical_place',
      'historical_place_location','historical_place_name','candidate_match','data_quality_issue']
print("### §5 九表列名（修正抽取） ###")
for k in KEEP:
    v=TABLES.get(k,[])
    print(f"  {k:30s} ({len(v):2d}): {v}")
print()
print("### 是否含三个关键新增列 ###")
for k in ['historical_place','historical_place_name','historical_place_location','source_record','data_quality_issue']:
    v=TABLES.get(k,[])
    print(f"  {k:28s} dataset_id={'dataset_id' in v} grain_key={'grain_key' in v} record_status={'record_status' in v} rejected_by={'rejected_by' in v} inactive_at={'inactive_at' in v} inactive_in_batch_id={'inactive_in_batch_id' in v} parent_external_id={'parent_external_id' in v} duplicate_ordinal={'duplicate_ordinal' in v}")
