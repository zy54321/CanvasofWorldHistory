# -*- coding: utf-8 -*-
"""D6-1 第三轮：严格排除 hash 子串 / 算术闭合 / 已定义特殊集合，找真正"孤立行数" """
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES=["CORE_DATA_MODEL_V2.1.1.md","IMPORT_RULES_V2.1.1.md","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md","DATA_PROVENANCE_V2.1.1.md","V2.1_TO_V2.1.1_CHANGELOG.md"]
# 只查"行数级"权威数字（排除 315/643 这类已定义特殊集合与数值片段）
TARGET=['19,039','47,503','18,103','12,631','29,391','12,831','47,499','18,101','29,388','17,469','8,682','8,218']
QUALS=['暂存原始','暂存态','隔离后','预计入库','入库','活性','暂存','干跑']
def L(f): return open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
issues=[]
for f in FILES:
    for i,l in enumerate(L(f),1):
        s=l.strip()
        if not s or s.startswith('|') or s.startswith('```') or s.startswith('#'): continue
        for n in TARGET:
            for m in re.finditer(re.escape(n),s):
                # 排除 hash 片段
                pre=s[max(0,m.start()-1):m.start()]
                if pre.isalnum(): continue
                win=s[max(0,m.start()-100):m.end()+100]
                if any(q in win for q in QUALS): continue
                # 算术闭合 / 对比 / 比率豁免
                if re.search(r'[−\-+×/⇒=]|vs|→|与|对',win): continue
                issues.append((f,i,n,s[:190]))
print("### D6-1 严格判定：真·孤立行数（无口径词、无算术关系） ###")
for x in issues: print(f"  {x[0]}:L{x[1]} [{x[2]}] {x[3]}")
print(f"\n  命中 = {len(issues)}")
if not issues: print("  ⇒ D6-1 正文叙述无孤立行数 ✅")
