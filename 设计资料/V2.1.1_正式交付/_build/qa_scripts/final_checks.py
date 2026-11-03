# -*- coding: utf-8 -*-
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
print("### D4-5 两组恒等式 + 七种反例（逐项 5 件事核对） ###")
R=L("ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md")
for name in ['反例 ① 正常新增后回滚','反例 ② 新增后重复隔离','反例 ③ 之前已失效的记录再次导入','反例 ④ 已锁定记录','反例 ⑤ 人工修改保护记录','反例 ⑥ 写入失败但未落库','反例 ⑦ 混合批次']:
    print(f"  [{name}] 存在={'✅' if any(name in l for l in R) else '❌'}")
# 五种要素
FIVE=['属哪个集合','是否参与回滚','是否产生台账','是否计入统计','SQL 复算']
print("\n  五要素覆盖检查（在 4.1-4.7 区间内）：")
seg="\n".join(R[387:672])
for f in FIVE:
    print(f"    {f:14s} 命中次数={seg.count(f)}")
print("\n### D4-6 is_active=false OR inactive_reason -> N_noop 禁止 ###")
for i,l in enumerate(R,1):
    if 'N_noop' in l and ('禁止' in l or '必须禁止' in l or '不得' in l):
        print(f"  L{i} {l.strip()[:190]}")
print("\n### D4-10 canonical 三条判定式 ###")
C=L("CORE_DATA_MODEL_V2.1.1.md")
print("  ① creator 分支不得写死 FALSE AS is_canonical_row（SQL 块内）: 见 codeblock_scan 结果（code=0）")
print("  ② 视图 SQL 不得有不可执行占位符: 见 codeblock_scan（<canonical code=0）")
print("  ③ ORDER BY 引用列必须可见: 见 b1_sql_static3（全 ✅）")
print("  315 追溯 / 不补造名称行：")
for i,l in enumerate(C,1):
    if '315' in l and ('不补造' in l or '不需要也不允许' in l or 'creator' in l) and i<1300 and i>1260:
        print(f"    CORE:L{i} {l.strip()[:190]}")
print("\n### D3-5 source_record UNIQUE 五段键在 ER 图 ###")
S=L("ER_DIAGRAM_V2.1.1.svg")
for i,l in enumerate(S,1):
    if 'UQ' in l and 'parent_external_id' in l:
        print(f"  L{i} {l.strip()[:200]}")
print("\n### D3-4 行数口径词 ###")
for i,l in enumerate(S,1):
    if re.search(r'\d{1,3},\d{3}',l) and ('预计入库' in l or '暂存' in l or '隔离后' in l):
        print(f"  L{i} {re.sub(r'<[^>]+>','',l).strip()[:170]}")
