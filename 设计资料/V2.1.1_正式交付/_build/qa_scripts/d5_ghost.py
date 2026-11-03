# -*- coding: utf-8 -*-
"""D5-1 FIELD_MAPPING 幽灵列：每个 staging_column 必须在实测 CSV 中真实存在"""
import csv,os,io,collections
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(BASE))))  # 上溯到项目根附近
print("BASE=",BASE)
# 定位 WB-002/normalized
cands=[]
p=BASE
for _ in range(8):
    p=os.path.dirname(p)
    t=os.path.join(p,"WB-002","normalized")
    if os.path.isdir(t): cands.append(t)
    t2=os.path.join(p,"WB-002")
    if os.path.isdir(t2): cands.append(t2)
print("候选 WB-002 目录:",cands[:5])
