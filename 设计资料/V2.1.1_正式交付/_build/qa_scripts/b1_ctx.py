# -*- coding: utf-8 -*-
import re,os
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def ctx(f, target_lines, before=1, after=1):
    L=open(os.path.join(BASE,f),encoding='utf-8').read().split('\n')
    for t in target_lines:
        print(f"--- {f}:{t} ---")
        for i in range(max(1,t-before), min(len(L),t+after)+1):
            print(f"{i:5d}| {L[i-1]}")
        print()
ctx("CORE_DATA_MODEL_V2.1.1.md",[996,997,998,999,1000,1001,1318,1319,1320,1321])
