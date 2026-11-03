# -*- coding: utf-8 -*-
"""D4-1/D4-2：隔离算法脚本代入四种排列 + 旧规则对照"""
from itertools import groupby

def isolate(seq):
    """同一 hash 子组内：最小 ordinal 保留、后续相同 hash 隔离、不同 hash 均保留。
       等价实现：每个 hash 在组内按 ordinal 排序后，仅保留第一条（最小 ordinal）。"""
    keep=[]; quar=[]
    for i,(h,o) in enumerate(seq):
        pass
    # 规则：按 hash 分组，取组内最小 ordinal 的那一条保留（多行同 hash 时），其余隔离
    from collections import defaultdict
    grp=defaultdict(list)
    for idx,(h,o) in enumerate(seq): grp[h].append(idx)
    for h,idxs in grp.items():
        idxs_sorted=sorted(idxs,key=lambda i: seq[i][1])
        keep.append(idxs_sorted[0])
        quar+= idxs_sorted[1:]
    return sorted(keep), sorted(quar)

def old_rule(seq):
    """旧（已禁用）规则：以 ordinal==1 的 hash 为比较基准 —— 只隔离 ordinal>1 且 hash 与 ordinal=1 相同者"""
    base=set()
    for h,o in seq:
        if o==1: base.add(h)
    quar=[i for i,(h,o) in enumerate(seq) if o>1 and h in base]
    return quar

CASES={
 'A,B,B':[('A',1),('B',1),('B',2)],
 'B,A,B':[('B',1),('A',1),('B',2)],
 'A,B,C':[('A',1),('B',1),('C',1)],
 'A,A,B,B':[('A',1),('A',2),('B',1),('B',2)],
}
EXP={'A,B,B':1,'B,A,B':1,'A,B,C':0,'A,A,B,B':2}
print("### 四种排列隔离数（脚本代入，现行规则） ###")
allok=True
for name,seq in CASES.items():
    keep,quar=isolate(seq)
    ok = len(quar)==EXP[name]
    allok &= ok
    print(f"  {name:10s} 序列={seq}")
    print(f"     保留 idx={keep} -> {[seq[i] for i in keep]}")
    print(f"     隔离 idx={quar} -> {[seq[i] for i in quar]}   隔离数={len(quar)}  期望={EXP[name]}  {'✅' if ok else '❌'}")
print(f"\n  四排列全对 = {allok}  {'PASS ✅' if allok else 'FAIL ❌'}")

print("\n### 旧规则（ordinal=1 为基准）对照 —— 应能复现判据禁止的行为 ###")
for name,seq in CASES.items():
    o=old_rule(seq)
    print(f"  {name:10s} 旧规则隔离数={len(o)} idx={o}   现行规则={len(isolate(seq)[1])}")

print("\n### 附加：⑤ 真实混合组 A,A,B ###")
seq=[('A',1),('A',2),('B',1)]
k,q=isolate(seq); print(f"  A,A,B -> 隔离 {len(q)} 行 {q}（文档称 1 行）")
